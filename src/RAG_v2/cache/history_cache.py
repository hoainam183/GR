"""Conversation history cache backed by Redis List.

Provides instant retrieval of recent chat turns to avoid MongoDB aggregation.
Uses LPUSH + LTRIM to keep the last 20 messages (10 turns) in Redis.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, cast

import redis

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 20
_HISTORY_TTL = 3600 * 2  # 2 hours idle expiration


class ConversationHistoryCache:
    """Redis-backed conversation history cache using LPUSH + LTRIM.

    Parameters:
        redis_client: A ``redis.Redis`` instance.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self._r = redis_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_history(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        """Return the recent conversation history, oldest first.

        Returns ``None`` on Redis miss (so the caller can fall back to MongoDB).
        """
        key = f"history:{session_id}"
        try:
            # Check if key exists to distinguish empty history vs cache miss
            if not self._r.exists(key):
                return None

            # LRANGE returns elements starting from index 0 (newest if LPUSH was used)
            raw_msgs: list = cast(list, self._r.lrange(key, 0, _HISTORY_LIMIT - 1))
            history = []
            for m in raw_msgs:
                try:
                    history.append(json.loads(m))
                except (json.JSONDecodeError, TypeError):
                    continue

            # Since we LPUSH'ed (newest at index 0), we reverse to get oldest first
            history.reverse()
            return history

        except redis.RedisError:
            logger.warning("Redis get_history failed", exc_info=True)
            return None

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a single message to the history list with LPUSH and LTRIM.

        Refreshes TTL to 2 hours.
        """
        key = f"history:{session_id}"
        payload = json.dumps({"role": role, "content": content})
        try:
            pipe = self._r.pipeline()
            pipe.lpush(key, payload)
            pipe.ltrim(key, 0, _HISTORY_LIMIT - 1)
            pipe.expire(key, _HISTORY_TTL)
            pipe.execute()
        except redis.RedisError:
            logger.warning("Redis add_message failed", exc_info=True)

    def warm_history(self, session_id: str, history: List[Dict[str, str]]) -> None:
        """Warm the cache with history fetched from MongoDB.

        Input history is expected to be oldest first.
        """
        key = f"history:{session_id}"
        try:
            # Delete old key if any
            self._r.delete(key)
            if not history:
                return

            pipe = self._r.pipeline()
            # Since history is oldest first, we LPUSH them in order so the oldest
            # ends up at the end of the list, and the newest is at the front (index 0).
            for msg in history:
                pipe.lpush(key, json.dumps(msg))
            pipe.ltrim(key, 0, _HISTORY_LIMIT - 1)
            pipe.expire(key, _HISTORY_TTL)
            pipe.execute()
        except redis.RedisError:
            logger.debug("Failed to warm history cache for %s", session_id)

    def delete_history(self, session_id: str) -> None:
        """Delete history cache for a session."""
        try:
            self._r.delete(f"history:{session_id}")
        except redis.RedisError:
            pass
