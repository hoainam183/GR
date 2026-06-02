"""Focused tests for mobile API contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.dependencies import sync_redis_session_from_mongo
from api.routes.bookmark import create_bookmark, create_bookmark_folder, rename_bookmark_folder
from api.routes.chat import chat_v3
from api.routes.notification import subscribe_notifications, unsubscribe_notifications
from api.services.notification_delivery import broadcast_user_notification
from api.routes.session import SessionUpdateRequest, delete_session, list_my_sessions, update_session
from schemas.chat import ChatRequest, UserContext
from schemas.mobile import (
    BookmarkCreate,
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
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = docs or []
        self.update_one_calls = []
        self.delete_one_calls = []
        self.insert_many_calls = []
        self.delete_many_calls = []

    async def update_one(self, query, update, *, upsert=False):
        self.update_one_calls.append((query, update, upsert))
        match = next((doc for doc in self.docs if _matches_query(doc, query)), None)
        if match is not None:
            match.update(update.get("$set", {}))
        elif upsert:
            inserted = {"_id": f"fake-{len(self.docs) + 1}", **query}
            inserted.update(update.get("$setOnInsert", {}))
            inserted.update(update.get("$set", {}))
            self.docs.append(inserted)
        return SimpleNamespace()

    async def update_many(self, query, update):
        matched = 0
        for doc in self.docs:
            if _matches_query(doc, query):
                doc.update(update.get("$set", {}))
                matched += 1
        return SimpleNamespace(modified_count=matched)

    async def delete_one(self, query):
        self.delete_one_calls.append(query)
        return SimpleNamespace(deleted_count=1)

    async def delete_many(self, query):
        self.delete_many_calls.append(query)
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not _matches_query(doc, query)]
        return SimpleNamespace(deleted_count=before - len(self.docs))

    async def find_one(self, query):
        return next((doc for doc in self.docs if _matches_query(doc, query)), None)

    def find(self, query=None, _projection=None):
        query = query or {}
        return _FakeAsyncCursor([doc for doc in self.docs if _matches_query(doc, query)])

    async def insert_many(self, docs):
        docs = list(docs)
        self.insert_many_calls.append(docs)
        inserted_ids = []
        for doc in docs:
            inserted = {"_id": f"fake-{len(self.docs) + 1}", **doc}
            inserted_ids.append(inserted["_id"])
            self.docs.append(inserted)
        return SimpleNamespace(inserted_ids=inserted_ids)

    async def count_documents(self, query):
        return sum(1 for doc in self.docs if _matches_query(doc, query))

    def aggregate(self, _pipeline):
        return _FakeAsyncCursor([])


class _FakeAsyncCursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._docs):
            raise StopAsyncIteration
        item = self._docs[self._index]
        self._index += 1
        return item


def _matches_query(doc: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


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
async def test_bookmark_create_accepts_legacy_session_owner_alias():
    db = _FakeAsyncDb()
    db["sessions"].docs.append({"session_id": "s-legacy", "user_id": "20210001"})
    db["turns"].docs.append(
        {
            "session_id": "s-legacy",
            "turn_id": 1,
            "question": "Điều kiện tốt nghiệp?",
            "answer": "Cần hoàn thành chương trình đào tạo.",
            "sources": [{"metadata": {"source": "quy_dinh"}}],
        }
    )

    response = await create_bookmark(
        BookmarkCreate(session_id="s-legacy", turn_id=1, folder="  Quan trọng  "),
        current_user=_user("auth-user"),
        db=db,
    )

    assert response["bookmark"]["session_id"] == "s-legacy"
    assert response["bookmark"]["folder"] == "Quan trọng"
    assert response["bookmark"]["answer_snapshot"] == "Cần hoàn thành chương trình đào tạo."
    query, _update, upsert = db["bookmarks"].update_one_calls[0]
    assert query["user_id"] == "auth-user"
    assert upsert is True


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


@pytest.mark.anyio
async def test_notification_broadcast_creates_db_notifications_and_sends_expo(monkeypatch):
    db = _FakeAsyncDb()
    db["users"].docs.append({"_id": "user-push"})
    db["notification_subscriptions"].docs.append(
        {"user_id": "user-push", "expo_push_token": "ExponentPushToken[test]"}
    )
    sent_batches = []

    def fake_post(endpoint, messages, timeout_s):
        sent_batches.append((endpoint, messages, timeout_s))
        return {"data": [{"status": "ok"} for _ in messages]}

    monkeypatch.setattr(
        "api.services.notification_delivery._post_expo_push_batch",
        fake_post,
    )

    response = await broadcast_user_notification(
        db,
        title="Crawler updated",
        body="Có dữ liệu mới.",
        notification_type="crawler_update",
        push_enabled=True,
    )

    assert response["created_count"] == 1
    assert response["push_sent_count"] == 1
    assert response["push_error_count"] == 0
    assert db["notifications"].docs[0]["user_id"] == "user-push"
    assert db["notifications"].docs[0]["type"] == "crawler_update"
    assert sent_batches[0][1][0]["to"] == "ExponentPushToken[test]"
