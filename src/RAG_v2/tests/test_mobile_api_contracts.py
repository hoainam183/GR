"""Focused tests for mobile API contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.dependencies import sync_redis_session_from_mongo
from api.routes.bookmark import create_bookmark_folder, rename_bookmark_folder
from api.routes.chat import chat_v3
from api.routes.notification import subscribe_notifications, unsubscribe_notifications
from api.routes.session import SessionUpdateRequest, delete_session, list_my_sessions, update_session
from schemas.chat import ChatRequest, UserContext
from schemas.mobile import (
    BookmarkFolderCreate,
    BookmarkFolderRename,
    NotificationSubscribe,
    NotificationUnsubscribe,
)
from schemas.user import TokenResponse, UserPublic


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
        self.deleted = []
        self.updated = []

    def new_session(self, user_id=None):
        sid = f"session-{len(self.sessions) + 1}"
        self.sessions[sid] = {"session_id": sid, "user_id": user_id}
        return sid

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def list_sessions(self, user_id: str, limit: int = 50):
        self.list_calls.append((user_id, limit))
        return [{"session_id": "s1", "user_id": user_id, "turn_count": 0}]

    def delete_session(self, session_id: str):
        self.deleted.append(session_id)
        return self.sessions.pop(session_id, None) is not None

    def update_session_title(self, session_id: str, title: str):
        self.updated.append((session_id, title))
        session = self.sessions.get(session_id)
        if not session:
            return False
        session["title"] = title
        return True


class _FakeRedisSession:
    def __init__(self) -> None:
        self.synced = []

    def sync_from_mongo(self, session_id: str) -> None:
        self.synced.append(session_id)


class _FakeAsyncCollection:
    def __init__(self) -> None:
        self.update_one_calls = []
        self.delete_one_calls = []

    async def update_one(self, query, update, *, upsert=False):
        self.update_one_calls.append((query, update, upsert))
        return SimpleNamespace()

    async def delete_one(self, query):
        self.delete_one_calls.append(query)
        return SimpleNamespace(deleted_count=1)


class _FakeAsyncDb(dict):
    def __missing__(self, key):
        value = _FakeAsyncCollection()
        self[key] = value
        return value


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
        email=None,
        username=None,
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
    assert ("user-123", 10) in mongo.list_calls
    assert ("20210001", 10) in mongo.list_calls


def test_mobile_token_response_allows_refresh_token():
    user = UserPublic(
        full_name="Nguyen Van A",
        student_id="20210001",
        cohort="K68",
        major="CNTT",
        major_code="IT1",
        role="student",
        is_profile_complete=True,
        is_active=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        last_login_at="2026-01-01T00:00:00Z",
    )
    token = TokenResponse(
        access_token="access",
        token_type="bearer",
        expires_in=900,
        refresh_token="refresh",
        user=user,
    )

    assert token.expires_in == 900
    assert token.refresh_token == "refresh"


@pytest.mark.anyio
async def test_session_update_requires_owner_alias():
    mongo = _FakeMongo()
    mongo.sessions["s1"] = {"session_id": "s1", "user_id": "20210001", "title": "Old"}

    response = await update_session(
        _request(mongo=mongo),
        "s1",
        SessionUpdateRequest(title=" New title "),
        current_user=_user("user-123"),
    )

    assert response == {"updated": True, "session_id": "s1", "title": "New title"}
    assert mongo.sessions["s1"]["title"] == "New title"


@pytest.mark.anyio
async def test_session_delete_requires_owner_alias():
    mongo = _FakeMongo()
    mongo.sessions["s1"] = {"session_id": "s1", "user_id": "user-123"}

    response = await delete_session(
        _request(mongo=mongo),
        "s1",
        current_user=_user("user-123"),
    )

    assert response == {"deleted": True, "session_id": "s1"}
    assert "s1" not in mongo.sessions


def test_sync_redis_session_from_mongo_calls_store_sync():
    redis = _FakeRedisSession()
    sync_redis_session_from_mongo(
        redis_session=redis,
        mongo_logger=object(),
        session_id="session-1",
    )
    assert redis.synced == ["session-1"]


@pytest.mark.anyio
async def test_bookmark_folder_create_trims_and_persists_explicit_folder():
    db = _FakeAsyncDb()

    response = await create_bookmark_folder(
        BookmarkFolderCreate(name="  Kế hoạch  "),
        current_user=_user("user-folder"),
        db=db,
    )

    assert response == {"folder": {"name": "Kế hoạch", "count": 0}}
    query, update, upsert = db["bookmark_folders"].update_one_calls[0]
    assert query == {"user_id": "user-folder", "name": "Kế hoạch"}
    assert update["$setOnInsert"]["name"] == "Kế hoạch"
    assert upsert is True


@pytest.mark.anyio
async def test_bookmark_default_folder_cannot_be_renamed():
    with pytest.raises(HTTPException) as exc:
        await rename_bookmark_folder(
            "Chung",
            BookmarkFolderRename(new_name="Khác"),
            current_user=_user("user-folder"),
            db=_FakeAsyncDb(),
        )

    assert exc.value.status_code == 422


@pytest.mark.anyio
async def test_notification_broadcast_subscription_and_unsubscribe_contract():
    db = _FakeAsyncDb()
    token = "ExponentPushToken[test]"

    subscribed = await subscribe_notifications(
        NotificationSubscribe(topics=[], expo_push_token=token),
        current_user=_user("user-push"),
        db=db,
    )
    unsubscribed = await unsubscribe_notifications(
        NotificationUnsubscribe(expo_push_token=token),
        current_user=_user("user-push"),
        db=db,
    )

    assert subscribed == {"subscribed_topics": []}
    query, update, upsert = db["notification_subscriptions"].update_one_calls[0]
    assert query == {"user_id": "user-push", "expo_push_token": token}
    assert update["$set"]["topics"] == []
    assert upsert is True
    assert unsubscribed == {"remaining_topics": []}
    assert db["notification_subscriptions"].delete_one_calls == [
        {"user_id": "user-push", "expo_push_token": token}
    ]
