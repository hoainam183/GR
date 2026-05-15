"""Focused tests for mobile API contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.dependencies import sync_redis_session_from_mongo
from api.routes.chat import chat_v3
from api.routes.session import list_my_sessions
from schemas.chat import ChatRequest, UserContext


class _FakePipeline:
    def __init__(self) -> None:
        self.agent = None
        self.last_user_context = None
        self.last_session_id = None

    def query_v3(
        self,
        question: str,
        history=None,
        top_k=None,
        session_id=None,
        user_context=None,
    ):
        self.last_user_context = user_context
        self.last_session_id = session_id
        return {
            "question": question,
            "answer": "ok",
            "sources": [],
            "num_sources": 0,
            "model_name": "fake",
            "intent": "rag",
            "mode": "rag_v2",
            "route": "simple",
        }


class _FakeMongo:
    def __init__(self) -> None:
        self.sessions = {}
        self.list_calls = []

    def new_session(self, user_id=None):
        sid = f"session-{len(self.sessions) + 1}"
        self.sessions[sid] = {"session_id": sid, "user_id": user_id}
        return sid

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def list_sessions(self, user_id: str, limit: int = 50):
        self.list_calls.append((user_id, limit))
        return [{"session_id": "s1", "user_id": user_id, "turn_count": 0}]


class _FakeRedisSession:
    def __init__(self) -> None:
        self.synced = []

    def sync_from_mongo(self, session_id: str) -> None:
        self.synced.append(session_id)


def _request(*, pipeline=None, mongo=None, redis=None):
    state = SimpleNamespace(
        pipeline=pipeline,
        mongo_logger=mongo,
        redis_session=redis,
    )
    return SimpleNamespace(app=SimpleNamespace(state=state))


def _user(user_id: str = "auth-user"):
    return SimpleNamespace(
        id=user_id,
        student_id="20210001",
        cohort="K68",
        major="CNTT",
        major_code="IT1",
        full_name="Nguyen Van A",
    )


@pytest.mark.anyio
async def test_chat_v3_authenticated_profile_overrides_spoofed_body_context():
    pipeline = _FakePipeline()
    mongo = _FakeMongo()
    body = ChatRequest(
        question="Quy định tốt nghiệp?",
        user_id="spoofed-user",
        user_context=UserContext(cohort="K00", major="Spoofed"),
    )

    response = await chat_v3(
        _request(pipeline=pipeline, mongo=mongo),
        body,
        current_user=_user(),
    )

    assert response["session_id"] == "session-1"
    assert mongo.sessions["session-1"]["user_id"] == "auth-user"
    assert pipeline.last_user_context == {
        "student_id": "20210001",
        "cohort": "K68",
        "major": "CNTT",
        "major_code": "IT1",
        "full_name": "Nguyen Van A",
    }


@pytest.mark.anyio
async def test_sessions_me_uses_authenticated_user_id():
    mongo = _FakeMongo()
    response = await list_my_sessions(
        _request(mongo=mongo),
        current_user=_user("user-123"),
        limit=10,
    )

    assert response["count"] == 1
    assert response["sessions"][0]["user_id"] == "user-123"
    assert mongo.list_calls == [("user-123", 10)]


def test_sync_redis_session_from_mongo_calls_store_sync():
    redis = _FakeRedisSession()
    sync_redis_session_from_mongo(
        redis_session=redis,
        mongo_logger=object(),
        session_id="session-1",
    )
    assert redis.synced == ["session-1"]
