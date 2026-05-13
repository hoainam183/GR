"""Unit tests for Week 4 MongoLogger agent trace features."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models.mongo_logger import MongoLogger


class _FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    def sort(self, key: str, direction: int):
        reverse = direction == -1
        self._docs = sorted(self._docs, key=lambda doc: doc.get(key), reverse=reverse)
        return self

    def limit(self, count: int):
        self._docs = self._docs[:count]
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeAgentTraceCollection:
    def __init__(self, docs: list[dict] | None = None, should_fail: bool = False):
        self.docs = docs or []
        self.should_fail = should_fail

    def insert_one(self, doc: dict):
        if self.should_fail:
            raise RuntimeError("Mongo unavailable")
        self.docs.append(doc)
        return {"inserted_id": "fake-id"}

    def find(self, _query: dict, _projection: dict):
        return _FakeCursor(list(self.docs))


def _make_logger_with_collection(collection: _FakeAgentTraceCollection) -> MongoLogger:
    logger_obj = MongoLogger.__new__(MongoLogger)
    logger_obj._agent_traces = collection
    return logger_obj


def test_log_agent_trace_does_not_raise_when_collection_fails() -> None:
    logger_obj = _make_logger_with_collection(_FakeAgentTraceCollection(should_fail=True))

    # Must not raise; logging failures are non-fatal by design.
    logger_obj.log_agent_trace("session-1", {"iterations": 2, "tool_names_sequence": ["rag_search"]})


def test_log_agent_trace_persists_expected_fields() -> None:
    collection = _FakeAgentTraceCollection()
    logger_obj = _make_logger_with_collection(collection)

    logger_obj.log_agent_trace(
        "session-abc",
        {
            "query": "So sánh học bổng K65 và K70",
            "iterations": 3,
            "tool_names_sequence": ["compare_cohorts"],
            "error": None,
        },
    )

    assert len(collection.docs) == 1
    saved = collection.docs[0]
    assert saved["session_id"] == "session-abc"
    assert saved["iterations"] == 3
    assert saved["tool_names_sequence"] == ["compare_cohorts"]
    assert isinstance(saved["created_at"], datetime)


def test_get_agent_stats_aggregates_recent_traces() -> None:
    now = datetime.now(timezone.utc)
    docs = [
        {
            "created_at": now - timedelta(minutes=2),
            "iterations": 2,
            "tool_names_sequence": ["rag_search", "web_search"],
            "error": None,
        },
        {
            "created_at": now - timedelta(minutes=1),
            "iterations": 4,
            "tool_names_sequence": ["compare_cohorts"],
            "error": "timeout",
        },
        {
            "created_at": now,
            "iterations": 3,
            "tool_names_sequence": ["multi_rag_search", "rag_search"],
            "error": None,
        },
    ]
    logger_obj = _make_logger_with_collection(_FakeAgentTraceCollection(docs=docs))

    stats = logger_obj.get_agent_stats(limit=2)

    # limit=2 keeps the two most recent docs: iterations 3 and 4.
    assert stats["total_traces"] == 2
    assert stats["avg_iterations"] == 3.5
    assert stats["error_rate"] == 0.5
    assert stats["tool_frequency"]["multi_rag_search"] == 1
    assert stats["tool_frequency"]["rag_search"] == 1
    assert stats["tool_frequency"]["compare_cohorts"] == 1


def test_get_agent_stats_returns_empty_for_invalid_or_empty_input() -> None:
    logger_obj = _make_logger_with_collection(_FakeAgentTraceCollection(docs=[]))
    assert logger_obj.get_agent_stats(limit=100) == {}
    assert logger_obj.get_agent_stats(limit=0) == {}
