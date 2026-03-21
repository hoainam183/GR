"""Chat History Store — CRUD operations for chat messages in MongoDB."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.collection import Collection

from .mongo_client import MongoClient

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
COLLECTION_NAME = "chat_messages"


# ═══════════════════════════════════════════════════════════════════════════════
class ChatHistoryStore:
    """Persists chat messages per session in MongoDB.

    Parameters:
        mongo_client: A connected :class:`MongoClient` instance.
        collection_name: MongoDB collection used for messages.
    """

    def __init__(
        self,
        mongo_client: MongoClient,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self._collection: Collection = mongo_client.db[collection_name]
        self._ensure_indexes()

    # ------------------------------------------------------------------
    # Index setup
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        self._collection.create_index(
            [("session_id", 1), ("timestamp", 1)],
            name="session_timestamp_idx",
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> str:
        """Save a single chat message.

        Args:
            session_id: Conversation session identifier.
            role: Message role (``"user"`` or ``"assistant"``).
            content: Message text.

        Returns:
            The inserted document's ``_id`` as a string.
        """
        doc = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
        }
        result = self._collection.insert_one(doc)
        logger.debug(
            "Saved message [%s/%s] id=%s", session_id, role, result.inserted_id
        )
        return str(result.inserted_id)

    def get_history(
        self,
        session_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Retrieve the most recent messages for a session.

        Args:
            session_id: Conversation session identifier.
            limit: Maximum number of messages to return.

        Returns:
            List of message dicts sorted oldest → newest, each containing
            ``session_id``, ``role``, ``content``, ``timestamp``.
        """
        cursor = (
            self._collection.find(
                {"session_id": session_id},
                {
                    "_id": 0,
                    "session_id": 1,
                    "role": 1,
                    "content": 1,
                    "timestamp": 1,
                },
            )
            .sort("timestamp", -1)
            .limit(limit)
        )
        messages = list(cursor)
        messages.reverse()  # oldest first
        return messages

    def clear_history(self, session_id: str) -> int:
        """Delete all messages for a session.

        Args:
            session_id: Conversation session identifier.

        Returns:
            Number of documents deleted.
        """
        result = self._collection.delete_many({"session_id": session_id})
        logger.info(
            "Cleared %d messages for session %s",
            result.deleted_count,
            session_id,
        )
        return result.deleted_count
