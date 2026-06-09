"""Exact-match LLM response cache backed by Redis.

Caches final synthesized answers from the LLM based on a fingerprint of the
normalized user question, retrieved document IDs, and the LLM model name.
This avoids repeating expensive LLM calls for identical questions grounded
in the same retrieval context.

Supports automatic FAQ promotion (increases TTL from 1 hour to 24 hours
for high-frequency hits) and explicit invalidation when new document data
is crawled.

Redis Schema::

    llm_cache:{sha256_hex}   → Hash  {answer, sources_summary, model, created_at, hit_count}
    llm_cache:stats          → Hash  {hits, misses, total_saved_ms}
    doc_cache_tag:{doc_id}   → Set   {cache_key, ...}   TTL 24h
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, cast

import redis

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 3600  # 1 hour
_FAQ_TTL = 86400    # 24 hours
_FAQ_HIT_THRESHOLD = 5
_TAG_TTL = 86400    # doc→cache reverse-index tag TTL (24h)

# Pre-retrieval query-level cache TTL.
# Shorter than the main cache because doc_ids are not tracked for invalidation.
_QUERY_CACHE_TTL = 300  # 5 minutes


class LLMResponseCache:
    """Exact-match LLM response cache.

    Parameters:
        redis_client: A ``redis.Redis`` instance.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self._r = redis_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        query: str,
        doc_ids: List[str],
        model: str,
        profile: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a cached response if present.

        Increments hit_count on hit and auto-promotes to FAQ TTL if
        the hit threshold is crossed. ``profile`` scopes the key to the asking
        student's major|cohort to prevent cross-profile answer leaks.
        """
        key = self._build_key(query, doc_ids, model, profile)
        try:
            # Atomic fetch + increment hit count using pipeline
            pipe = self._r.pipeline()
            pipe.hgetall(key)
            pipe.hincrby(key, "hit_count", 1)
            results = pipe.execute()

            data = results[0]
            if not data:
                self._record_miss()
                return None

            hit_count = results[1]
            # Promote to FAQ TTL if highly popular
            if hit_count == _FAQ_HIT_THRESHOLD:
                logger.info("Cache key %s promoted to FAQ (TTL 24h)", key)
                self._r.expire(key, _FAQ_TTL)

            self._record_hit()
            return {
                "answer": data.get("answer", ""),
                "sources": json.loads(data.get("sources_json", "[]")),
                "model_name": data.get("model", model),
                "cached_at": data.get("created_at", ""),
                "hit_count": hit_count,
            }

        except redis.RedisError:
            logger.warning("Redis LLM cache get failed", exc_info=True)
            return None

    def put(
        self,
        query: str,
        doc_ids: List[str],
        model: str,
        answer: str,
        sources: List[Dict[str, Any]],
        profile: str = "",
    ) -> None:
        """Cache a newly generated response.

        Also creates reverse-index tags (``doc_cache_tag:{doc_id}`` → Set)
        so that when a specific document is updated by the crawler, only
        cache entries derived from that document are invalidated. ``profile``
        scopes the key to the asking student's major|cohort.
        """
        key = self._build_key(query, doc_ids, model, profile)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        payload = {
            "answer": answer,
            "sources_json": json.dumps(sources),
            "model": model,
            "created_at": now_iso,
            "hit_count": "0",
        }

        try:
            pipe = self._r.pipeline()
            pipe.hset(key, mapping=payload)
            pipe.expire(key, _DEFAULT_TTL)

            # Reverse-index: doc_id → set of cache keys that used this doc
            for doc_id in doc_ids:
                if doc_id:
                    tag_key = f"doc_cache_tag:{doc_id}"
                    pipe.sadd(tag_key, key)
                    pipe.expire(tag_key, _TAG_TTL)

            pipe.execute()
        except redis.RedisError:
            logger.warning("Redis LLM cache put failed", exc_info=True)

    def invalidate_by_docs(self, doc_ids: List[str]) -> int:
        """Invalidate only cache entries that reference the given documents.

        Uses the reverse-index tags (``doc_cache_tag:{doc_id}``) created
        during :meth:`put` to surgically remove affected entries instead
        of wiping the entire cache.

        Args:
            doc_ids: List of document/chunk IDs that were updated.

        Returns:
            The number of cache entries removed.
        """
        if not doc_ids:
            return 0

        removed = 0
        try:
            for doc_id in doc_ids:
                tag_key = f"doc_cache_tag:{doc_id}"
                raw_keys: set = cast(set, self._r.smembers(tag_key))
                cache_keys: set[str] = set(raw_keys) if raw_keys else set()
                if not cache_keys:
                    continue

                pipe = self._r.pipeline()
                for ck in cache_keys:
                    pipe.unlink(ck)          # async DEL — non-blocking
                pipe.delete(tag_key)
                pipe.execute()
                removed += len(cache_keys)

            if removed:
                logger.info(
                    "Tag-based invalidation: removed %d cache entries for %d docs",
                    removed, len(doc_ids),
                )
        except redis.RedisError:
            logger.error("Redis tag-based invalidation failed", exc_info=True)

        return removed

    def invalidate_all(self) -> int:
        """Delete ALL cached LLM responses and their doc tags.

        Use sparingly — only when a full reset is needed (e.g. model
        change, full reindex).  Prefer :meth:`invalidate_by_docs` for
        incremental crawler updates.

        Returns:
            The number of cache entries cleared.
        """
        try:
            keys = []
            for key in self._r.scan_iter(match="llm_cache:[0-9a-f]*"):
                keys.append(key)
            # Also clean up orphan doc tags
            for key in self._r.scan_iter(match="doc_cache_tag:*"):
                keys.append(key)

            if keys:
                count = cast(int, self._r.delete(*keys))
                logger.warning("Full cache invalidation: removed %d keys", count)
                return count
            return 0
        except redis.RedisError:
            logger.error("Redis LLM cache invalidation failed", exc_info=True)
            return 0

    def get_stats(self) -> Dict[str, int]:
        """Return cache hits and misses stats."""
        try:
            stats: dict = cast(dict, self._r.hgetall("llm_cache:stats"))
            return {
                "hits": int(stats.get("hits", 0)),
                "misses": int(stats.get("misses", 0)),
            }
        except redis.RedisError:
            return {"hits": 0, "misses": 0}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_key(query: str, doc_ids: List[str], model: str, profile: str = "") -> str:
        """Generate a deterministic SHA256 cache key from input params.

        ``profile`` (normalized major|cohort of the asking student) is mixed in so
        that a profile-specific answer is never served to a student with a different
        profile. Empty ``profile`` (anonymous / no profile) keeps the legacy key
        space, so callers that pass nothing are unaffected.
        """
        normalized_q = query.strip().lower()
        sorted_docs = sorted(str(d).strip() for d in doc_ids if d)
        fingerprint = f"{normalized_q}||{','.join(sorted_docs)}||{model}||{profile}"
        sha = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
        return f"llm_cache:{sha}"

    @staticmethod
    def _build_query_only_key(query: str, model: str, profile: str = "") -> str:
        """SHA256 cache key from normalized query + model (+ student profile).

        Used by the pre-retrieval cache path so identical queries hit the cache
        *before* reflection and retrieval run, saving 13-25 s per request.

        ``profile`` (normalized major|cohort) MUST be included: this key has no
        doc_ids, so without the profile a personal answer generated for one student
        ("điều kiện tốt nghiệp của tôi") would be served verbatim to any other
        student asking the same words — a cross-student data leak.
        """
        normalized_q = query.strip().lower()
        fingerprint = f"llm_qcache:{normalized_q}||{model}||{profile}"
        sha = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
        return f"llm_cache:q:{sha}"

    # ------------------------------------------------------------------
    # Pre-retrieval query-level cache  (no doc_ids — checked before retrieval)
    # ------------------------------------------------------------------

    def get_by_query(
        self,
        query: str,
        model: str,
        profile: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Look up a cached response using only the normalized query + model.

        This check runs *before* reflection and retrieval, so a cache hit saves
        the full pipeline cost (~13-25 s).  TTL is shorter than the main cache
        (``_QUERY_CACHE_TTL`` = 5 min) because doc-level invalidation is not
        tracked here. ``profile`` (major|cohort) scopes the key so a personal
        answer is never returned to a student with a different profile.
        """
        key = self._build_query_only_key(query, model, profile)
        try:
            data = cast(dict, self._r.hgetall(key))
            if not data:
                return None
            logger.info("Pre-retrieval query cache HIT: %r", query[:80])
            self._r.hincrby(key, "hit_count", 1)
            return {
                "answer": data.get("answer", ""),
                "sources": json.loads(data.get("sources_json", "[]")),
                "model_name": data.get("model", model),
                "cached_at": data.get("created_at", ""),
            }
        except redis.RedisError:
            logger.warning("Redis query cache get failed", exc_info=True)
            return None

    def put_by_query(
        self,
        query: str,
        model: str,
        answer: str,
        sources: List[Dict[str, Any]],
        profile: str = "",
    ) -> None:
        """Store a response in the pre-retrieval query-only cache.

        Does NOT create doc-level reverse-index tags; use :meth:`put` for
        invalidation-aware caching after retrieval. ``profile`` (major|cohort)
        scopes the key to the asking student.
        """
        key = self._build_query_only_key(query, model, profile)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = {
            "answer": answer,
            "sources_json": json.dumps(sources),
            "model": model,
            "created_at": now_iso,
            "hit_count": "0",
        }
        try:
            pipe = self._r.pipeline()
            pipe.hset(key, mapping=payload)
            pipe.expire(key, _QUERY_CACHE_TTL)
            pipe.execute()
        except redis.RedisError:
            logger.warning("Redis query cache put failed", exc_info=True)

    def _record_hit(self) -> None:
        try:
            self._r.hincrby("llm_cache:stats", "hits", 1)
        except redis.RedisError:
            pass

    def _record_miss(self) -> None:
        try:
            self._r.hincrby("llm_cache:stats", "misses", 1)
        except redis.RedisError:
            pass
