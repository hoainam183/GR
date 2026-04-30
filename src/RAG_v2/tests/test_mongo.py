"""Tests for MongoDB integration — MongoLogger CRUD operations.

Refactored from script-style to proper pytest module.
Requires MongoDB running at localhost:27017.
Mark: integration
"""

from __future__ import annotations

import pytest
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

TEST_DB = "rag_chatbot_test"
MONGO_URI = "mongodb://localhost:27017"


def _mongo_available() -> bool:
    """Return True only if MongoDB is reachable."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


requires_mongo = pytest.mark.skipif(
    not _mongo_available(),
    reason="MongoDB not available at localhost:27017 — start MongoDB first",
)


@pytest.fixture(scope="module")
def mongo_logger():
    """Shared MongoLogger instance for the test module."""
    from pipeline.mongo_logger import MongoLogger

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.drop_database(TEST_DB)
    logger = MongoLogger(uri=MONGO_URI, database=TEST_DB)
    yield logger
    client.drop_database(TEST_DB)
    client.close()


@requires_mongo
class TestNewSession:
    def test_session_id_is_uuid_string(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        assert isinstance(sid, str)
        assert len(sid) == 36  # UUID4 format: 8-4-4-4-12 hex

    def test_session_document_exists(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        session = mongo_logger.get_session(sid)
        assert session is not None
        assert session["session_id"] == sid

    def test_session_defaults(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        session = mongo_logger.get_session(sid)
        assert session["turn_count"] == 0
        assert "turns" not in session
        assert session["user_id"] is None
        assert session["title"] is None


@requires_mongo
class TestLogTurnRag:
    def test_turn_id_is_1_for_first_turn(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        result = {
            "answer": "Câu trả lời RAG",
            "intent": "rag",
            "num_sources": 5,
            "model_name": "gemini-3.1-flash-lite-preview",
        }
        turn_id = mongo_logger.log_turn(
            session_id=sid, question="Câu hỏi test?", result=result, latency_ms=1234
        )
        assert turn_id == 1

    def test_turn_fields_logged_correctly(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        result = {
            "answer": "Câu trả lời RAG",
            "intent": "rag",
            "num_sources": 5,
            "model_name": "gemini-3.1-flash-lite-preview",
        }
        mongo_logger.log_turn(
            session_id=sid, question="Câu hỏi test?", result=result, latency_ms=1234
        )
        turns = mongo_logger.get_turns(sid)
        assert len(turns) == 1
        turn = turns[0]
        assert turn["intent"] == "rag"
        assert turn["latency_ms"] == 1234
        assert turn["num_sources"] == 5
        assert turn["model_name"] == "gemini-3.1-flash-lite-preview"

    def test_session_title_auto_set_from_first_question(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        mongo_logger.log_turn(
            session_id=sid,
            question="Câu hỏi test?",
            result={"answer": "A", "intent": "rag", "num_sources": 0, "model_name": "test"},
            latency_ms=100,
        )
        session = mongo_logger.get_session(sid)
        assert session["title"] == "Câu hỏi test?"

    def test_query_log_collection_entry(self, mongo_logger) -> None:
        from pymongo import MongoClient as MC
        client = MC(MONGO_URI, serverSelectionTimeoutMS=2000)
        db = client[TEST_DB]
        sid = mongo_logger.new_session()
        mongo_logger.log_turn(
            session_id=sid,
            question="Test?",
            result={"answer": "A", "intent": "rag", "num_sources": 0, "model_name": "gemini-3.1-flash-lite-preview"},
            latency_ms=100,
        )
        ql = db["query_logs"].find_one({"session_id": sid})
        assert ql is not None
        assert ql["model_name"] == "gemini-3.1-flash-lite-preview"
        client.close()


@requires_mongo
class TestLogTurnChitchat:
    def test_chitchat_turn_fields(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        result = {"answer": "Xin chào!", "intent": "chitchat", "num_sources": 0, "model_name": "gemini-3.1-flash-lite-preview"}
        turn_id = mongo_logger.log_turn(session_id=sid, question="Hello", result=result, latency_ms=100)
        assert turn_id == 1
        turns = mongo_logger.get_turns(sid)
        assert turns[0]["intent"] == "chitchat"
        assert turns[0]["num_sources"] == 0


@requires_mongo
class TestGetHistory:
    def test_history_format(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        for i in range(3):
            mongo_logger.log_turn(
                session_id=sid,
                question=f"Question {i}",
                result={"answer": f"Answer {i}", "intent": "rag", "num_sources": 1, "model_name": "test"},
                latency_ms=100,
            )
        history = mongo_logger.get_history(sid)
        assert len(history) == 6
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Question 0"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Answer 0"
        assert history[-1]["content"] == "Answer 2"


@requires_mongo
class TestSessionTurnCount:
    def test_turn_count_increments(self, mongo_logger) -> None:
        sid = mongo_logger.new_session()
        for i in range(2):
            mongo_logger.log_turn(
                session_id=sid,
                question=f"Q{i}",
                result={"answer": f"A{i}", "intent": "rag", "num_sources": 0, "model_name": "test"},
                latency_ms=50,
            )
        session = mongo_logger.get_session(sid)
        assert session["turn_count"] == 2
        turns = mongo_logger.get_turns(sid)
        assert len(turns) == 2
        assert turns[1]["turn_id"] == 2


@requires_mongo
class TestListSessions:
    def test_list_sessions_by_user(self, mongo_logger) -> None:
        uid = "test-user-list-sessions"
        sid1 = mongo_logger.new_session(user_id=uid)
        sid2 = mongo_logger.new_session(user_id=uid)
        mongo_logger.new_session(user_id="other-user")

        sessions = mongo_logger.list_sessions(user_id=uid)
        session_ids = [s["session_id"] for s in sessions]
        assert sid1 in session_ids
        assert sid2 in session_ids

    def test_list_sessions_newest_first(self, mongo_logger) -> None:
        uid = "test-user-newest-first"
        sid1 = mongo_logger.new_session(user_id=uid)
        sid2 = mongo_logger.new_session(user_id=uid)
        sessions = mongo_logger.list_sessions(user_id=uid)
        # Newest first
        assert sessions[0]["session_id"] == sid2
