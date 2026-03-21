"""MongoLogger — session & query logging to MongoDB."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
class MongoLogger:
    """Persist chat sessions and query logs to MongoDB.

    Parameters:
        uri: MongoDB connection URI.
        database: Database name.
    """

    def __init__(self, uri: str, database: str) -> None:
        self._client: MongoClient = MongoClient(uri)
        self._db = self._client[database]
        self._sessions = self._db["sessions"]
        self._query_logs = self._db["query_logs"]
        self._ensure_indexes()
        logger.info("MongoLogger connected to %s / %s", uri, database)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_session(self, user_id: Optional[str] = None) -> str:
        """Create a new session document and return its ``session_id``."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        self._sessions.insert_one(
            {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
                "turn_count": 0,
                "turns": [],
            }
        )
        return session_id

    def log_turn(
        self,
        session_id: str,
        question: str,
        result: Dict[str, Any],
        *,
        reflected_question: Optional[str] = None,
        latency_ms: int = 0,
    ) -> int:
        """Append a turn to the session and insert a flat query_log entry.

        Returns:
            The 1-based ``turn_id`` of the newly logged turn.
        """
        now = datetime.now(timezone.utc)

        # Compute next turn_id from current turn_count
        session = self._sessions.find_one({"session_id": session_id})
        turn_id = (session["turn_count"] + 1) if session else 1

        intent = result.get("intent", "rag")
        answer = result.get("answer", "")
        num_sources = result.get("num_sources", 0)
        model_name = result.get("model_name", "")

        turn_doc = {
            "turn_id": turn_id,
            "question": question,
            "answer": answer,
            "intent": intent,
            "reflected_question": reflected_question,
            "num_sources": num_sources,
            "latency_ms": latency_ms,
            "timestamp": now,
        }

        # Push turn into session and bump counters
        self._sessions.update_one(
            {"session_id": session_id},
            {
                "$push": {"turns": turn_doc},
                "$inc": {"turn_count": 1},
                "$set": {"updated_at": now},
            },
        )

        # Flat analytics entry
        self._query_logs.insert_one(
            {
                "session_id": session_id,
                "user_id": session["user_id"] if session else None,
                "turn_id": turn_id,
                "question": question,
                "answer": answer,
                "intent": intent,
                "reflected_question": reflected_question,
                "num_sources": num_sources,
                "model_name": model_name,
                "latency_ms": latency_ms,
                "timestamp": now,
            }
        )

        return turn_id

    def get_history(
        self, session_id: str, max_turns: int = 10
    ) -> List[Dict[str, str]]:
        """Return recent turns as ``[{"role": ..., "content": ...}]``."""
        session = self._sessions.find_one({"session_id": session_id})
        if not session:
            return []

        turns = session.get("turns", [])[-max_turns:]
        history: List[Dict[str, str]] = []
        for t in turns:
            history.append({"role": "user", "content": t["question"]})
            history.append({"role": "assistant", "content": t["answer"]})
        return history

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the full session document (or *None*)."""
        return self._sessions.find_one({"session_id": session_id}, {"_id": 0})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        """Create indexes if they don't already exist."""
        self._sessions.create_index("session_id", unique=True)
        self._sessions.create_index(
            [("user_id", ASCENDING), ("updated_at", DESCENDING)]
        )
        self._query_logs.create_index("session_id")
        self._query_logs.create_index("timestamp")
        self._query_logs.create_index("user_id")
