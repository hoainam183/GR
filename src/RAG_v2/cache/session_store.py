"""RedisSessionStore — drop-in replacement for MongoLogger session operations.

Stores session metadata in Redis Hash + Sorted Set for fast O(1) lookup and
O(log N) ordered listing.  Supports dual-write mode for safe migration from
MongoDB: when a ``mongo_logger`` is provided, every write also goes to
MongoDB so the system can fall back at any time.

Redis Schema::

    session:{session_id}       → Hash  {user_id, title, created_at, updated_at, turn_count}
    user_sessions:{user_id}    → Sorted Set  (member=session_id, score=updated_at_ts)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import redis
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

# Sessions without activity expire after 7 days.
_SESSION_TTL_SECONDS = 7 * 24 * 3600  # 604 800
_MAX_SESSIONS_PER_USER = 100


class RedisSessionStore:
    """Session management backed by Redis with optional MongoDB dual-write.

    Parameters:
        redis_client: A ``redis.Redis`` instance (from :class:`RedisManager`).
        mongo_logger: Optional ``MongoLogger`` for dual-write during migration.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        mongo_logger: Any = None,
    ) -> None:
        self._r = redis_client
        self._mongo = mongo_logger

    # ------------------------------------------------------------------
    # Public API — sessions
    # ------------------------------------------------------------------

    def new_session(self, user_id: Optional[str] = None) -> str:
        """Create a new session and return its ``session_id``.

        Writes to both Redis and MongoDB (dual-write) when ``mongo_logger``
        is configured.
        """
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()
        now_iso = now.isoformat()

        session_data = {
            "session_id": session_id,
            "user_id": user_id or "",
            "title": "",
            "created_at": now_iso,
            "updated_at": now_iso,
            "turn_count": "0",
        }

        pipe = self._r.pipeline()
        key = f"session:{session_id}"
        pipe.hset(key, mapping=session_data)
        pipe.expire(key, _SESSION_TTL_SECONDS)

        # Index by user for list_sessions
        if user_id:
            user_key = f"user_sessions:{user_id}"
            pipe.zadd(user_key, {session_id: now_ts})
            # Trim to keep only the most recent sessions
            pipe.zremrangebyrank(user_key, 0, -(_MAX_SESSIONS_PER_USER + 1))

        try:
            pipe.execute()
        except redis.RedisError:
            logger.error("Redis new_session failed", exc_info=True)
            # Fall through to MongoDB if available
            if self._mongo:
                return self._mongo.new_session(user_id=user_id)
            raise

        # Dual-write to MongoDB using the same session_id. MongoDB remains the
        # durable source of truth for turns and analytics.
        if self._mongo:
            try:
                self._mongo._sessions.insert_one({
                    "session_id": session_id,
                    "user_id": user_id,
                    "title": None,
                    "created_at": now,
                    "updated_at": now,
                    "turn_count": 0,
                })
            except DuplicateKeyError:
                logger.warning("MongoDB session_id collision during Redis dual-write")
            except Exception:
                logger.warning("Dual-write new_session to MongoDB failed", exc_info=True)

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return session metadata or ``None`` if not found.

        Falls back to MongoDB when Redis miss occurs (cold cache).
        """
        try:
            key = f"session:{session_id}"
            data: dict = cast(dict, self._r.hgetall(key))
            if data:
                return self._deserialize_session(data)
        except redis.RedisError:
            logger.warning("Redis get_session failed", exc_info=True)

        # Fallback to MongoDB
        if self._mongo:
            session = self._mongo.get_session(session_id)
            if session:
                # Warm cache
                self._warm_session(session_id, session)
            return session
        return None

    def list_sessions(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return sessions for a user, newest first.

        Uses Redis Sorted Set for O(log N + M) retrieval.
        Cleans up zombie session IDs (hash expired but ID still in set).
        Falls back to MongoDB on Redis failure.
        """
        try:
            user_key = f"user_sessions:{user_id}"
            # Fetch extra IDs to compensate for potential zombies
            session_ids: List[str] = list(
                self._r.zrevrange(user_key, 0, limit + 19)  # type: ignore[arg-type]
            )

            if not session_ids:
                # Try MongoDB fallback — user may have sessions from before migration
                if self._mongo:
                    return self._mongo.list_sessions(user_id=user_id, limit=limit)
                return []

            pipe = self._r.pipeline()
            for sid in session_ids:
                pipe.hgetall(f"session:{sid}")

            raw_results: List[Dict[str, str]] = list(pipe.execute())
            sessions = []
            zombie_ids: List[str] = []

            for sid, data in zip(session_ids, raw_results):
                if data:
                    sessions.append(self._deserialize_session(data))
                else:
                    zombie_ids.append(sid)

            # Remove zombie IDs from sorted set (best-effort)
            if zombie_ids:
                try:
                    self._r.zrem(user_key, *zombie_ids)
                    logger.debug(
                        "Cleaned %d zombie session IDs for user %s",
                        len(zombie_ids), user_id[:20],
                    )
                except redis.RedisError:
                    pass

            return sessions[:limit]

        except redis.RedisError:
            logger.warning("Redis list_sessions failed", exc_info=True)
            if self._mongo:
                return self._mongo.list_sessions(user_id=user_id, limit=limit)
            return []

    def update_session_on_turn(
        self,
        session_id: str,
        question: str,
        turn_id: int,
    ) -> None:
        """Update session metadata after a new turn is logged.

        Increments turn_count, sets title from first question, and
        refreshes updated_at timestamp.
        """
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()
        now_iso = now.isoformat()

        key = f"session:{session_id}"
        try:
            pipe = self._r.pipeline()
            pipe.hincrby(key, "turn_count", 1)
            pipe.hset(key, "updated_at", now_iso)

            # Auto-set title from first question
            if turn_id == 1:
                title = question[:80] + ("…" if len(question) > 80 else "")
                pipe.hset(key, "title", title)

            # Refresh TTL
            pipe.expire(key, _SESSION_TTL_SECONDS)

            # Update sorted set score for ordering
            user_id = self._r.hget(key, "user_id")
            if user_id:
                pipe.zadd(f"user_sessions:{user_id}", {session_id: now_ts})

            pipe.execute()
        except redis.RedisError:
            logger.warning("Redis update_session_on_turn failed", exc_info=True)

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """Delete session metadata and cached history from Redis and MongoDB."""
        key = f"session:{session_id}"
        redis_deleted = False
        try:
            owner_id = user_id or self._r.hget(key, "user_id")
            pipe = self._r.pipeline()
            pipe.delete(key)
            pipe.delete(f"history:{session_id}")
            if owner_id:
                pipe.zrem(f"user_sessions:{owner_id}", session_id)
            results = pipe.execute()
            redis_deleted = bool(results[0]) if results else False
        except redis.RedisError:
            logger.warning("Redis delete_session failed", exc_info=True)

        if self._mongo:
            return bool(self._mongo.delete_session(session_id)) or redis_deleted
        return redis_deleted

    def update_session_title(self, session_id: str, title: str) -> bool:
        """Update a session title without creating partial Redis metadata."""
        key = f"session:{session_id}"
        redis_matched = False
        try:
            if self._r.exists(key):
                pipe = self._r.pipeline()
                pipe.hset(key, "title", title)
                pipe.expire(key, _SESSION_TTL_SECONDS)
                pipe.execute()
                redis_matched = True
        except redis.RedisError:
            logger.warning("Redis update_session_title failed", exc_info=True)

        if self._mongo:
            updated = bool(self._mongo.update_session_title(session_id, title))
            if updated:
                self.sync_from_mongo(session_id)
            return updated
        return redis_matched

    def sync_from_mongo(self, session_id: str) -> None:
        """Refresh Redis metadata for a session from MongoDB.

        The RAG pipeline logs turns through ``MongoLogger``. Calling this after
        a chat request keeps Redis list views consistent with MongoDB title,
        updated_at, and turn_count without coupling MongoLogger to Redis.
        """
        if self._mongo is None:
            return
        try:
            session = self._mongo.get_session(session_id)
        except Exception:
            logger.warning("Failed to read MongoDB session for Redis sync", exc_info=True)
            return
        if session:
            self._warm_session(session_id, session)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _warm_session(self, session_id: str, session: Dict[str, Any]) -> None:
        """Write a MongoDB session into Redis for future lookups."""
        try:
            key = f"session:{session_id}"
            created_at = session.get("created_at")
            updated_at = session.get("updated_at")

            data = {
                "session_id": session_id,
                "user_id": session.get("user_id") or "",
                "title": session.get("title") or "",
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or ""),
                "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at or ""),
                "turn_count": str(session.get("turn_count", 0)),
            }
            pipe = self._r.pipeline()
            pipe.hset(key, mapping=data)
            pipe.expire(key, _SESSION_TTL_SECONDS)

            user_id = session.get("user_id")
            if user_id and updated_at:
                ts = updated_at.timestamp() if isinstance(updated_at, datetime) else 0
                pipe.zadd(f"user_sessions:{user_id}", {session_id: ts})

            pipe.execute()
        except redis.RedisError:
            logger.debug("Failed to warm session cache: %s", session_id)

    @staticmethod
    def _deserialize_session(data: Dict[str, str]) -> Dict[str, Any]:
        """Convert Redis hash strings back to a session dict."""
        turn_count_raw = data.get("turn_count", "0")
        try:
            turn_count = int(turn_count_raw)
        except (ValueError, TypeError):
            turn_count = 0

        return {
            "session_id": data.get("session_id", ""),
            "user_id": data.get("user_id") or None,
            "title": data.get("title") or None,
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "turn_count": turn_count,
        }
