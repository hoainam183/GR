"""Motor (async MongoDB) client setup and FastAPI dependency injection.

Usage in a FastAPI route:
    from models.database import get_database, USERS_COLLECTION
    from motor.motor_asyncio import AsyncIOMotorDatabase

    @router.get("/users/{user_id}")
    async def get_user(db: AsyncIOMotorDatabase = Depends(get_database)):
        doc = await db[USERS_COLLECTION].find_one({"_id": user_id})
        ...

Index creation is handled once at application startup via
``create_indexes()``, which should be called from the FastAPI
``lifespan`` context manager (or ``@app.on_event("startup")``).
"""

from __future__ import annotations

import logging
import os
from typing import AsyncGenerator

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
)
from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Collection name constants
# ═══════════════════════════════════════════════════════════════════════════════

USERS_COLLECTION: str = "users"
SESSIONS_COLLECTION: str = "sessions"
TURNS_COLLECTION: str = "turns"
QUERY_LOGS_COLLECTION: str = "query_logs"


# ═══════════════════════════════════════════════════════════════════════════════
# Motor client — module-level singleton (initialised lazily)
# ═══════════════════════════════════════════════════════════════════════════════

_motor_client: AsyncIOMotorClient | None = None


def _get_settings() -> tuple[str, str]:
    """Read MongoDB connection settings from environment variables.

    Returns:
        (uri, database_name) tuple.

    Environment variables:
        MONGODB_URI       — defaults to ``mongodb://localhost:27017``
        MONGODB_DATABASE  — defaults to ``rag_chatbot``
    """
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database = os.getenv("MONGODB_DATABASE", "rag_chatbot")
    return uri, database


def get_motor_client() -> AsyncIOMotorClient:
    """Return (and lazily create) the module-level Motor client singleton.

    The client is intentionally kept as a singleton to reuse the
    underlying connection pool across requests.
    """
    global _motor_client
    if _motor_client is None:
        uri, _ = _get_settings()
        _motor_client = AsyncIOMotorClient(uri)
        logger.info("AsyncIOMotorClient created for URI: %s", uri)
    return _motor_client


async def close_motor_client() -> None:
    """Close the Motor client and release all connections.

    Call this from the FastAPI ``lifespan`` shutdown hook.
    """
    global _motor_client
    if _motor_client is not None:
        _motor_client.close()
        _motor_client = None
        logger.info("AsyncIOMotorClient closed")


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI dependency
# ═══════════════════════════════════════════════════════════════════════════════

async def get_database() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """FastAPI dependency that yields the Motor database handle.

    Example::

        @router.post("/users")
        async def create_user(
            payload: UserCreate,
            db: AsyncIOMotorDatabase = Depends(get_database),
        ):
            ...
    """
    _, database_name = _get_settings()
    client = get_motor_client()
    yield client[database_name]


# ═══════════════════════════════════════════════════════════════════════════════
# Index creation — call once at startup
# ═══════════════════════════════════════════════════════════════════════════════

async def create_indexes() -> None:
    """Create all required indexes for the HUST Assistant collections.

    Indexes created:
        users:
            - unique index on ``email``
            - unique index on ``microsoft_id``
        sessions:
            - index on ``user_id``  (non-unique, supports per-user queries)
            - index on ``updated_at`` DESCENDING  (already expected by MongoLogger)
        turns:
            - index on ``session_id`` (fast turn lookup per session)
        query_logs:
            - index on ``session_id``

    This function is idempotent — calling it multiple times is safe.
    """
    _, database_name = _get_settings()
    db: AsyncIOMotorDatabase = get_motor_client()[database_name]

    # ── users collection ─────────────────────────────────────────────────────
    users = db[USERS_COLLECTION]
    await users.create_index(
        [("email", ASCENDING)],
        unique=True,
        name="email_unique",
    )
    await users.create_index(
        [("microsoft_id", ASCENDING)],
        unique=True,
        name="microsoft_id_unique",
    )
    logger.info(
        "Indexes ensured on collection '%s': email_unique, microsoft_id_unique",
        USERS_COLLECTION,
    )

    # ── sessions collection ───────────────────────────────────────────────────
    sessions = db[SESSIONS_COLLECTION]
    await sessions.create_index(
        [("user_id", ASCENDING)],
        name="user_id_asc",
    )
    await sessions.create_index(
        [("updated_at", DESCENDING)],
        name="updated_at_desc",
    )
    logger.info(
        "Indexes ensured on collection '%s': user_id_asc, updated_at_desc",
        SESSIONS_COLLECTION,
    )

    # ── turns collection ─────────────────────────────────────────────────────
    turns = db[TURNS_COLLECTION]
    await turns.create_index(
        [("session_id", ASCENDING)],
        name="session_id_asc",
    )
    logger.info(
        "Index ensured on collection '%s': session_id_asc",
        TURNS_COLLECTION,
    )

    # ── query_logs collection ────────────────────────────────────────────────
    query_logs = db[QUERY_LOGS_COLLECTION]
    await query_logs.create_index(
        [("session_id", ASCENDING)],
        name="session_id_asc",
    )
    logger.info(
        "Index ensured on collection '%s': session_id_asc",
        QUERY_LOGS_COLLECTION,
    )
