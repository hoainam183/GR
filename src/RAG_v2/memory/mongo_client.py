"""MongoDB Connection Client — singleton-style connection manager."""

from __future__ import annotations

import logging
from typing import Optional

from pymongo import MongoClient as PyMongoClient
from pymongo.database import Database

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_DB = "rag_chatbot"


# ═══════════════════════════════════════════════════════════════════════════════
class MongoClient:
    """Thin wrapper around ``pymongo.MongoClient`` with connection pooling.

    Parameters:
        uri: MongoDB connection string.
        database: Database name to use.
        max_pool_size: Max connections in the pool.
    """

    def __init__(
        self,
        uri: str = DEFAULT_URI,
        database: str = DEFAULT_DB,
        max_pool_size: int = 10,
    ) -> None:
        self._uri = uri
        self._database_name = database
        logger.info("Connecting to MongoDB at %s (db=%s)", uri, database)
        self._client: PyMongoClient = PyMongoClient(
            uri,
            maxPoolSize=max_pool_size,
            serverSelectionTimeoutMS=5000,
        )
        self._db: Database = self._client[database]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def db(self) -> Database:
        """Return the active database handle."""
        return self._db

    def ping(self) -> bool:
        """Check connectivity. Returns *True* if the server responds."""
        try:
            self._client.admin.command("ping")
            return True
        except Exception:
            logger.warning("MongoDB ping failed for %s", self._uri)
            return False

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._client.close()
        logger.info("MongoDB connection closed.")
