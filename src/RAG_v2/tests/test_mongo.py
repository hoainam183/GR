"""Test MongoDB integration — MongoLogger CRUD operations (turns in separate collection)."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure RAG_v2 root is on path
RAG_V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAG_V2_ROOT))

PASSED = 0
FAILED = 0

TEST_DB = "rag_chatbot_test"
MONGO_URI = "mongodb://localhost:27017"


def report(name: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    status = "PASS" if ok else "FAIL"
    if ok:
        PASSED += 1
    else:
        FAILED += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")


# ═══════════════════════════════════════════════════════════════════════════════
# Setup — connect and clean test DB
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== MongoDB Integration Tests ===\n")

try:
    from pymongo import MongoClient

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    # Force connection check
    client.admin.command("ping")
    print("  MongoDB connection OK\n")
except Exception as exc:
    print(f"  MongoDB not available at {MONGO_URI}: {exc}")
    print("  Skipping all MongoDB tests (start MongoDB first).\n")
    sys.exit(0)

# Clean test DB before running
client.drop_database(TEST_DB)

from pipeline.mongo_logger import MongoLogger

mongo_logger = MongoLogger(uri=MONGO_URI, database=TEST_DB)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. test_new_session
# ═══════════════════════════════════════════════════════════════════════════════
print("--- test_new_session ---")

try:
    sid = mongo_logger.new_session()
    # UUID4 format: 8-4-4-4-12 hex
    report("session_id is string", isinstance(sid, str) and len(sid) == 36)

    session = mongo_logger.get_session(sid)
    report("session document exists", session is not None)
    report("session_id matches", session["session_id"] == sid)
    report("turn_count is 0", session["turn_count"] == 0)
    report("no embedded turns field", "turns" not in session)
    report("user_id is None", session["user_id"] is None)
    report("title is None", session["title"] is None)
except Exception as exc:
    report("test_new_session", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. test_log_turn_rag
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- test_log_turn_rag ---")

try:
    sid = mongo_logger.new_session()
    result = {
        "answer": "Câu trả lời RAG",
        "intent": "rag",
        "num_sources": 5,
        "model_name": "gemini-2.5-flash",
    }
    turn_id = mongo_logger.log_turn(
        session_id=sid,
        question="Câu hỏi test?",
        result=result,
        latency_ms=1234,
    )
    report("turn_id is 1", turn_id == 1)

    turns = mongo_logger.get_turns(sid)
    report("turns has 1 entry", len(turns) == 1)

    turn = turns[0]
    report("turn intent is rag", turn["intent"] == "rag")
    report("turn latency_ms", turn["latency_ms"] == 1234)
    report("turn num_sources", turn["num_sources"] == 5)
    report("turn model_name", turn["model_name"] == "gemini-2.5-flash")

    # Auto-title from first question
    session = mongo_logger.get_session(sid)
    report("session title set", session["title"] == "Câu hỏi test?")

    # Check query_logs collection
    db = client[TEST_DB]
    ql = db["query_logs"].find_one({"session_id": sid})
    report("query_log exists", ql is not None)
    report("query_log model_name", ql["model_name"] == "gemini-2.5-flash")
except Exception as exc:
    report("test_log_turn_rag", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. test_log_turn_chitchat
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- test_log_turn_chitchat ---")

try:
    sid = mongo_logger.new_session()
    result = {
        "answer": "Xin chào!",
        "intent": "chitchat",
        "num_sources": 0,
        "model_name": "gemini-2.5-flash",
    }
    turn_id = mongo_logger.log_turn(
        session_id=sid,
        question="Hello",
        result=result,
        latency_ms=100,
    )
    report("turn_id is 1", turn_id == 1)

    turns = mongo_logger.get_turns(sid)
    report("intent is chitchat", turns[0]["intent"] == "chitchat")
    report("num_sources is 0", turns[0]["num_sources"] == 0)
except Exception as exc:
    report("test_log_turn_chitchat", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. test_get_history
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- test_get_history ---")

try:
    sid = mongo_logger.new_session()
    for i in range(3):
        mongo_logger.log_turn(
            session_id=sid,
            question=f"Question {i}",
            result={
                "answer": f"Answer {i}",
                "intent": "rag",
                "num_sources": 1,
                "model_name": "test",
            },
            latency_ms=100,
        )

    history = mongo_logger.get_history(sid)
    report("history has 6 messages", len(history) == 6, str(len(history)))
    report("first is user role", history[0]["role"] == "user")
    report("first content is Q0", history[0]["content"] == "Question 0")
    report("second is assistant role", history[1]["role"] == "assistant")
    report("second content is A0", history[1]["content"] == "Answer 0")
    report("last content is A2", history[-1]["content"] == "Answer 2")
except Exception as exc:
    report("test_get_history", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. test_session_turn_count
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- test_session_turn_count ---")

try:
    sid = mongo_logger.new_session()
    for i in range(2):
        mongo_logger.log_turn(
            session_id=sid,
            question=f"Q{i}",
            result={
                "answer": f"A{i}",
                "intent": "rag",
                "num_sources": 0,
                "model_name": "test",
            },
            latency_ms=50,
        )

    session = mongo_logger.get_session(sid)
    report("turn_count is 2", session["turn_count"] == 2)

    turns = mongo_logger.get_turns(sid)
    report("turns length is 2", len(turns) == 2)
    report("turn_id sequence", turns[1]["turn_id"] == 2)
except Exception as exc:
    report("test_session_turn_count", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 6. test_list_sessions
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- test_list_sessions ---")

try:
    uid = "test-user-123"
    sid1 = mongo_logger.new_session(user_id=uid)
    sid2 = mongo_logger.new_session(user_id=uid)
    # Another user
    mongo_logger.new_session(user_id="other-user")

    sessions = mongo_logger.list_sessions(user_id=uid)
    report("2 sessions for user", len(sessions) == 2, str(len(sessions)))
    # Newest first
    report("newest first", sessions[0]["session_id"] == sid2)
except Exception as exc:
    report("test_list_sessions", False, str(exc))
# Cleanup & Summary
# ═══════════════════════════════════════════════════════════════════════════════
client.drop_database(TEST_DB)

print(f"\n{'='*60}")
total = PASSED + FAILED
print(f"MongoDB Tests: {PASSED}/{total} passed, {FAILED} failed")
if FAILED == 0:
    print("All tests PASSED!")
else:
    print(f"WARNING: {FAILED} test(s) FAILED")
print(f"{'='*60}")
sys.exit(1 if FAILED else 0)
