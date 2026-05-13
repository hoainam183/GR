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
DOCUMENTS_COLLECTION: str = "documents"
DOCUMENT_CHUNKS_COLLECTION: str = "document_chunks"


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

    Each ``create_index`` call is wrapped individually so that a pre-existing
    index with a conflicting name (OperationFailure code 85) only emits a
    warning rather than aborting the whole startup.

    Indexes created:
        users:
            - sparse unique index on ``email``
            - sparse unique index on ``microsoft_id``
            - sparse unique index on ``username``
        sessions:
            - index on ``user_id``
            - index on ``updated_at`` DESCENDING
        turns:
            - index on ``session_id``
        query_logs:
            - index on ``session_id``
    """
    from pymongo.errors import OperationFailure

    _, database_name = _get_settings()
    db: AsyncIOMotorDatabase = get_motor_client()[database_name]

    async def safe_create(collection, keys, **kwargs):
        try:
            await collection.create_index(keys, **kwargs)
        except OperationFailure as exc:
            if exc.code == 85:  # IndexOptionsConflict — already exists differently
                logger.warning(
                    "Index on %s already exists with different options, skipping: %s",
                    collection.name,
                    (exc.details or {}).get("errmsg", str(exc)) if hasattr(exc, 'details') else str(exc),
                )
            else:
                raise

    async def drop_if_exists(collection, name: str):
        """Drop an index by name, silently ignore if it doesn't exist."""
        try:
            await collection.drop_index(name)
            logger.info("Dropped old index '%s' on '%s'", name, collection.name)
        except OperationFailure:
            pass  # index does not exist — fine

    # ── users collection ─────────────────────────────────────────────────────
    users = db[USERS_COLLECTION]
    # Drop old non-sparse unique indexes if they exist (migration: email/microsoft_id
    # are now Optional so the indexes need sparse=True to allow multiple nulls).
    await drop_if_exists(users, "email_unique")
    await drop_if_exists(users, "microsoft_id_unique")
    await safe_create(users, [("email", ASCENDING)],
                      unique=True, sparse=True, name="email_unique")
    await safe_create(users, [("microsoft_id", ASCENDING)],
                      unique=True, sparse=True, name="microsoft_id_unique")
    await safe_create(users, [("username", ASCENDING)],
                      unique=True, sparse=True, name="username_unique")
    logger.info(
        "Indexes ensured on collection '%s': email_unique, microsoft_id_unique, username_unique",
        USERS_COLLECTION,
    )

    # ── sessions collection ───────────────────────────────────────────────────
    sessions = db[SESSIONS_COLLECTION]
    await safe_create(sessions, [("user_id", ASCENDING)], name="user_id_asc")
    await safe_create(sessions, [("updated_at", DESCENDING)], name="updated_at_desc")
    logger.info(
        "Indexes ensured on collection '%s': user_id_asc, updated_at_desc",
        SESSIONS_COLLECTION,
    )

    # ── turns collection ─────────────────────────────────────────────────────
    turns = db[TURNS_COLLECTION]
    await safe_create(turns, [("session_id", ASCENDING)], name="session_id_asc")
    logger.info("Index ensured on collection '%s': session_id_asc", TURNS_COLLECTION)

    # ── query_logs collection ────────────────────────────────────────────────
    query_logs = db[QUERY_LOGS_COLLECTION]
    await safe_create(query_logs, [("session_id", ASCENDING)], name="session_id_asc")
    logger.info("Index ensured on collection '%s': session_id_asc", QUERY_LOGS_COLLECTION)

    # ── documents collection ─────────────────────────────────────────────────
    documents = db[DOCUMENTS_COLLECTION]
    await safe_create(documents, [("uploaded_by", ASCENDING)], name="uploaded_by_asc")
    await safe_create(documents, [("status", ASCENDING)], name="status_asc")
    await safe_create(documents, [("collection", ASCENDING)], name="collection_asc")
    logger.info(
        "Indexes ensured on collection '%s': uploaded_by_asc, status_asc, collection_asc",
        DOCUMENTS_COLLECTION,
    )

    # ── document_chunks collection ───────────────────────────────────────────
    doc_chunks = db[DOCUMENT_CHUNKS_COLLECTION]
    await safe_create(doc_chunks, [("document_id", ASCENDING)], name="document_id_asc")
    await safe_create(
        doc_chunks,
        [("document_id", ASCENDING), ("chunk_index", ASCENDING)],
        name="document_id_chunk_index",
    )
    logger.info(
        "Indexes ensured on collection '%s': document_id_asc, document_id_chunk_index",
        DOCUMENT_CHUNKS_COLLECTION,
    )
