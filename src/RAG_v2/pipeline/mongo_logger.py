"""MongoLogger — session, turn & query logging to MongoDB.

Schema (3 collections):
    sessions  — one doc per conversation (no embedded turns)
    turns     — one doc per turn (separated for scalability)
    query_logs — flat analytics entry per turn
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
class MongoLogger:
    """Persist chat sessions, turns, and query logs to MongoDB.

    Collections:
        sessions   — lightweight session metadata (no embedded turns).
        turns      — one document per turn, linked by ``session_id``.
        query_logs — flat analytics, one doc per turn.

    Parameters:
        uri: MongoDB connection URI.
        database: Database name.
    """

    def __init__(self, uri: str, database: str) -> None:
        self._client: MongoClient = MongoClient(uri)
        self._db = self._client[database]
        self._sessions = self._db["sessions"]
        self._turns = self._db["turns"]
        self._query_logs = self._db["query_logs"]
        self._ensure_indexes()
        logger.info("MongoLogger connected to %s / %s", uri, database)

    # ------------------------------------------------------------------
    # Public API — sessions
    # ------------------------------------------------------------------

    def new_session(self, user_id: Optional[str] = None) -> str:
        """Create a new session document and return its ``session_id``."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        self._sessions.insert_one(
            {
                "session_id": session_id,
                "user_id": user_id,
                "title": None,
                "created_at": now,
                "updated_at": now,
                "turn_count": 0,
            }
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the session metadata (or *None*)."""
        return self._sessions.find_one({"session_id": session_id}, {"_id": 0})

    def list_sessions(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return sessions for a user, newest first."""
        cursor = (
            self._sessions.find({"user_id": user_id}, {"_id": 0})
            .sort("updated_at", DESCENDING)
            .limit(limit)
        )
        return list(cursor)

    # ------------------------------------------------------------------
    # Public API — turns
    # ------------------------------------------------------------------

    def log_turn(
        self,
        session_id: str,
        question: str,
        result: Dict[str, Any],
        *,
        reflected_question: Optional[str] = None,
        latency_ms: int = 0,
        timings_ms: Optional[Dict[str, float]] = None,
    ) -> int:
        """Insert a turn document and a flat query_log entry.

        Returns:
            The 1-based ``turn_id`` of the newly logged turn.
        """
        now = datetime.now(timezone.utc)

        # Atomically increment turn_count and get updated session
        session = self._sessions.find_one_and_update(
            {"session_id": session_id},
            {
                "$inc": {"turn_count": 1},
                "$set": {"updated_at": now},
            },
            return_document=True,  # return AFTER update
        )
        turn_id = session["turn_count"] if session else 1

        intent = result.get("intent", "rag")
        answer = result.get("answer", "")
        num_sources = result.get("num_sources", 0)
        model_name = result.get("model_name", "")
        if timings_ms is None:
            raw_timings = result.get("timings_ms")
            if isinstance(raw_timings, dict):
                timings_ms = raw_timings

        # Auto-set session title from first question
        if session and turn_id == 1:
            title = question[:80] + ("…" if len(question) > 80 else "")
            self._sessions.update_one(
                {"session_id": session_id},
                {"$set": {"title": title}},
            )

        # Insert into turns collection
        turn_doc: Dict[str, Any] = {
            "session_id": session_id,
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
        if timings_ms is not None:
            turn_doc["timings_ms"] = timings_ms

        # Persist retrieval context so history can be restored with full detail
        raw_sources = result.get("sources", [])
        if raw_sources:
            turn_doc["sources"] = [
                {
                    "rank": i,
                    "content": doc.get("text", ""),
                    "score": float(doc.get("rerank_score", doc.get("score", 0.0))),
                    "metadata": doc.get("metadata", {}),
                }
                for i, doc in enumerate(raw_sources, 1)
            ]
        raw_collection_scores = result.get("collection_scores")
        if raw_collection_scores:
            turn_doc["collection_scores"] = raw_collection_scores
        raw_target_collections = result.get("target_collections")
        if raw_target_collections:
            turn_doc["target_collections"] = raw_target_collections

        self._turns.insert_one(turn_doc)

        # Flat analytics entry
        query_log_doc: Dict[str, Any] = {
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
        if timings_ms is not None:
            query_log_doc["timings_ms"] = timings_ms
        self._query_logs.insert_one(query_log_doc)

        return turn_id

    def get_turns(
        self, session_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Return turns for a session, oldest first."""
        cursor = (
            self._turns.find({"session_id": session_id}, {"_id": 0})
            .sort("turn_id", ASCENDING)
            .limit(limit)
        )
        return list(cursor)

    def get_history(
        self, session_id: str, max_turns: int = 10
    ) -> List[Dict[str, str]]:
        """Return recent turns as ``[{"role": ..., "content": ...}]``."""
        # Fetch the last N turns (sorted ascending so oldest is first)
        pipeline = [
            {"$match": {"session_id": session_id}},
            {"$sort": {"turn_id": DESCENDING}},
            {"$limit": max_turns},
            {"$sort": {"turn_id": ASCENDING}},
            {"$project": {"_id": 0, "question": 1, "answer": 1}},
        ]
        turns = list(self._turns.aggregate(pipeline))
        history: List[Dict[str, str]] = []
        for t in turns:
            history.append({"role": "user", "content": t["question"]})
            history.append({"role": "assistant", "content": t["answer"]})
        return history

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        """Create indexes if they don't already exist."""
        # sessions
        self._sessions.create_index("session_id", unique=True)
        self._sessions.create_index(
            [("user_id", ASCENDING), ("updated_at", DESCENDING)]
        )
        # turns
        self._turns.create_index(
            [("session_id", ASCENDING), ("turn_id", ASCENDING)], unique=True
        )
        self._turns.create_index(
            [("session_id", ASCENDING), ("timestamp", ASCENDING)]
        )
        # query_logs
        self._query_logs.create_index("session_id")
        self._query_logs.create_index("timestamp")
        self._query_logs.create_index("user_id")
