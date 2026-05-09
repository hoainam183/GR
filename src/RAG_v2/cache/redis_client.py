"""Redis client singleton — shared across session, cache, and rate limiting.

Provides a thread-safe connection pool manager with health checking and
graceful shutdown.  All Redis-dependent modules should obtain their client
via ``RedisManager.get_client()`` rather than creating their own connection.
"""

from __future__ import annotations

import logging
from typing import Optional

import redis

from config.settings import Settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Thread-safe Redis connection manager.

    Uses a connection pool internally so multiple callers can share the
    same set of TCP connections without contention.

    Usage::

        manager = RedisManager.from_settings(settings)
        r = manager.get_client()
        r.set("key", "value")

    Parameters:
        url: Redis connection URL (e.g. ``redis://localhost:6379/0``).
    """

    _instance: Optional["RedisManager"] = None

    def __init__(self, url: str) -> None:
        self._url = url
        self._pool = redis.ConnectionPool.from_url(
            url,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)
        logger.info("RedisManager created for URL: %s", self._redact_url(url))

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Settings) -> "RedisManager":
        """Create (or reuse) a manager from application settings.

        Returns the existing singleton if one was already created.
        """
        if cls._instance is not None:
            return cls._instance
        instance = cls(url=settings.redis_url)
        cls._instance = instance
        return instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_client(self) -> redis.Redis:
        """Return the shared Redis client backed by the connection pool."""
        return self._client

    def ping(self) -> bool:
        """Return ``True`` if the Redis server responds to PING."""
        try:
            return self._client.ping()
        except redis.RedisError as exc:
            logger.warning("Redis ping failed: %s", exc)
            return False

    def close(self) -> None:
        """Close all connections in the pool.

        Should be called from the FastAPI lifespan shutdown hook.
        """
        try:
            self._client.close()
            self._pool.disconnect()
            logger.info("RedisManager closed")
        except Exception:
            logger.warning("Error closing Redis connections", exc_info=True)
        finally:
            RedisManager._instance = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _redact_url(url: str) -> str:
        """Redact password from URL for safe logging."""
        if "@" in url:
            # redis://:password@host:port/db → redis://***@host:port/db
            scheme_end = url.index("://") + 3
            at_pos = url.index("@")
            return url[:scheme_end] + "***" + url[at_pos:]
        return url
