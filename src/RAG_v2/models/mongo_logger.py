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
        self._agent_traces = self._db["agent_traces"]
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

        # Persist agent/routing metadata for UI debug replay.
        mode = result.get("mode")
        if mode is not None:
            turn_doc["mode"] = str(mode)

        route = result.get("route")
        if route is not None:
            turn_doc["route"] = str(route)

        iterations = result.get("iterations")
        if isinstance(iterations, (int, float)):
            turn_doc["iterations"] = int(iterations)

        tools_used = result.get("tools_used")
        if isinstance(tools_used, list):
            turn_doc["tools_used"] = [str(tool) for tool in tools_used]

        tool_calls = result.get("tool_calls")
        if isinstance(tool_calls, list):
            turn_doc["tool_calls"] = tool_calls

        agent_error = result.get("agent_error")
        if agent_error is not None:
            turn_doc["agent_error"] = str(agent_error)

        generic_error = result.get("error")
        if generic_error is not None:
            turn_doc["error"] = str(generic_error)

        agent_trace = result.get("agent_trace")
        if isinstance(agent_trace, dict):
            turn_doc["agent_trace"] = agent_trace

        routing_probabilities = result.get("routing_probabilities")
        if isinstance(routing_probabilities, dict):
            turn_doc["routing_probabilities"] = routing_probabilities

        applied_filters = result.get("applied_filters")
        if isinstance(applied_filters, list):
            turn_doc["applied_filters"] = applied_filters

        collection_results = result.get("collection_results")
        if isinstance(collection_results, list):
            turn_doc["collection_results"] = collection_results

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

        if mode is not None:
            query_log_doc["mode"] = str(mode)
        if route is not None:
            query_log_doc["route"] = str(route)
        if isinstance(iterations, (int, float)):
            query_log_doc["iterations"] = int(iterations)
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
    # Public API — agent traces (Week 4)
    # ------------------------------------------------------------------

    def log_agent_trace(self, session_id: str, trace_dict: Dict[str, Any]) -> None:
        """Persist one LangGraph agent trace document.

        This method is intentionally best-effort: database errors are logged
        but never raised so chat requests are not interrupted by logging issues.
        """
        now = datetime.now(timezone.utc)
        doc: Dict[str, Any] = {
            **(trace_dict or {}),
            "session_id": session_id or str((trace_dict or {}).get("session_id", "")),
            "created_at": now,
        }
        try:
            self._agent_traces.insert_one(doc)
        except Exception as exc:
            logger.error("Failed to log agent trace: %s", exc)

    def get_agent_stats(self, limit: int = 100) -> Dict[str, Any]:
        """Return summary metrics from recent agent traces."""
        if limit <= 0:
            return {}

        traces = list(
            self._agent_traces.find({}, {"_id": 0})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        if not traces:
            return {}

        avg_iterations = sum(t.get("iterations", 0) for t in traces) / len(traces)
        tool_freq: Dict[str, int] = {}
        for trace in traces:
            for tool_name in trace.get("tool_names_sequence", []):
                tool_freq[tool_name] = tool_freq.get(tool_name, 0) + 1

        error_count = sum(1 for trace in traces if trace.get("error"))
        return {
            "total_traces": len(traces),
            "avg_iterations": round(avg_iterations, 2),
            "tool_frequency": tool_freq,
            "error_rate": round(error_count / len(traces), 3),
        }

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

        # agent_traces
        self._agent_traces.create_index("session_id")
        self._agent_traces.create_index([("created_at", DESCENDING)])
        self._agent_traces.create_index("tool_names_sequence")
