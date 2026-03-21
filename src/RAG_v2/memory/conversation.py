"""Conversation State — tracks sessions and persists final answers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.collection import Collection

from .mongo_client import MongoClient

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
CONVERSATIONS_COLLECTION = "conversations"
ANSWERS_COLLECTION = "answers"


# ═══════════════════════════════════════════════════════════════════════════════
class ConversationState:
    """Manages conversation lifecycle and stores final answers.

    Parameters:
        mongo_client: A connected :class:`MongoClient` instance.
    """

    def __init__(self, mongo_client: MongoClient) -> None:
        self._conversations: Collection = mongo_client.db[
            CONVERSATIONS_COLLECTION
        ]
        self._answers: Collection = mongo_client.db[ANSWERS_COLLECTION]
        self._ensure_indexes()

    # ------------------------------------------------------------------
    # Index setup
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient lookups."""
        self._conversations.create_index(
            "session_id", unique=True, name="session_idx"
        )
        self._answers.create_index(
            [("session_id", 1), ("timestamp", -1)],
            name="session_answer_idx",
        )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, session_id: str) -> None:
        """Register a new conversation session.

        If a session with the same id already exists, this is a no-op
        (upsert on ``session_id``).
        """
        now = datetime.now(timezone.utc)
        self._conversations.update_one(
            {"session_id": session_id},
            {
                "$setOnInsert": {
                    "session_id": session_id,
                    "status": "active",
                    "created_at": now,
                },
                "$set": {"last_active": now},
            },
            upsert=True,
        )
        logger.debug("Session created/touched: %s", session_id)

    def update_status(self, session_id: str, status: str) -> None:
        """Update session status (e.g. ``"active"`` → ``"closed"``)."""
        self._conversations.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "status": status,
                    "last_active": datetime.now(timezone.utc),
                },
            },
        )

    def touch(self, session_id: str) -> None:
        """Bump ``last_active`` timestamp for a session."""
        self._conversations.update_one(
            {"session_id": session_id},
            {"$set": {"last_active": datetime.now(timezone.utc)}},
        )

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return session metadata or *None* if not found."""
        return self._conversations.find_one(
            {"session_id": session_id}, {"_id": 0}
        )

    # ------------------------------------------------------------------
    # Final answers
    # ------------------------------------------------------------------

    def save_answer(
        self,
        session_id: str,
        query: str,
        answer: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        scores: Optional[Dict[str, float]] = None,
    ) -> str:
        """Persist a final answer with its provenance.

        Args:
            session_id: Owning session.
            query: Original user question.
            answer: Generated answer text.
            sources: List of source dicts used for the answer.
            scores: Quality/evaluation scores (e.g. faithfulness, relevance).

        Returns:
            Inserted document ``_id`` as a string.
        """
        doc = {
            "session_id": session_id,
            "query": query,
            "answer": answer,
            "sources": sources or [],
            "scores": scores or {},
            "timestamp": datetime.now(timezone.utc),
        }
        result = self._answers.insert_one(doc)
        self.touch(session_id)
        logger.debug(
            "Saved answer for session %s (id=%s)",
            session_id,
            result.inserted_id,
        )
        return str(result.inserted_id)

    def get_answers(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent answers for a session (newest first).

        Args:
            session_id: Conversation session identifier.
            limit: Maximum number of answers to return.

        Returns:
            List of answer dicts.
        """
        cursor = (
            self._answers.find(
                {"session_id": session_id},
                {"_id": 0},
            )
            .sort("timestamp", -1)
            .limit(limit)
        )
        return list(cursor)
