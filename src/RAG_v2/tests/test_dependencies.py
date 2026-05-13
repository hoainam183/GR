"""Tests for api/dependencies — resolve_session and parse_history helpers.

Run:
    pytest tests/test_dependencies.py -v
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class _FakeMongoLogger:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}
        self._counter = 0

    def new_session(self, user_id: str | None = None) -> str:
        self._counter += 1
        sid = f"session-{self._counter}"
        self._sessions[sid] = {"session_id": sid}
        return sid

    def get_session(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)


class TestResolveSession:
    def test_creates_new_session_when_none(self) -> None:
        from api.dependencies import resolve_session

        mongo = _FakeMongoLogger()
        sid = resolve_session(session_id=None, user_id=None, mongo_logger=mongo)
        assert sid == "session-1"

    def test_creates_new_session_when_unknown(self) -> None:
        from api.dependencies import resolve_session

        mongo = _FakeMongoLogger()
        sid = resolve_session(session_id="ghost-id", user_id=None, mongo_logger=mongo)
        assert sid == "session-1"

    def test_returns_existing_valid_session(self) -> None:
        from api.dependencies import resolve_session

        mongo = _FakeMongoLogger()
        existing = mongo.new_session()  # "session-1"
        sid = resolve_session(session_id=existing, user_id=None, mongo_logger=mongo)
        assert sid == existing

    def test_returns_none_when_no_mongo_and_no_session(self) -> None:
        from api.dependencies import resolve_session

        sid = resolve_session(session_id=None, user_id=None, mongo_logger=None)
        assert sid is None

    def test_returns_provided_session_when_no_mongo(self) -> None:
        from api.dependencies import resolve_session

        sid = resolve_session(
            session_id="my-session", user_id=None, mongo_logger=None
        )
        assert sid == "my-session"

    def test_passes_user_id_to_new_session(self) -> None:
        from api.dependencies import resolve_session

        created: list[str | None] = []
        mongo = _FakeMongoLogger()
        original_new_session = mongo.new_session

        def spy_new_session(user_id: str | None = None) -> str:
            created.append(user_id)
            return original_new_session(user_id=user_id)

        mongo.new_session = spy_new_session  # type: ignore[method-assign]
        resolve_session(session_id=None, user_id="user-42", mongo_logger=mongo)
        assert created == ["user-42"]


class TestParseHistory:
    def test_empty_history_returns_empty_list(self) -> None:
        from api.dependencies import parse_history

        assert parse_history(None) == []
        assert parse_history([]) == []

    def test_converts_history_message_objects(self) -> None:
        from api.dependencies import parse_history
        from schemas.chat import HistoryMessage

        history = [
            HistoryMessage(role="user", content="Hello"),
            HistoryMessage(role="assistant", content="Hi there"),
        ]
        result = parse_history(history)
        assert result == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

    def test_preserves_order(self) -> None:
        from api.dependencies import parse_history
        from schemas.chat import HistoryMessage

        history = [
            HistoryMessage(role="user", content="Q1"),
            HistoryMessage(role="assistant", content="A1"),
            HistoryMessage(role="user", content="Q2"),
        ]
        result = parse_history(history)
        assert [m["role"] for m in result] == ["user", "assistant", "user"]
