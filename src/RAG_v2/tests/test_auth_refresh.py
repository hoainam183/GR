from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from auth.password import hash_password
from auth.refresh_tokens import hash_refresh_token
from models.database import REFRESH_TOKENS_COLLECTION, USERS_COLLECTION, get_database
from routers.auth import router


class _FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    async def insert_one(self, doc: dict[str, Any]):
        stored = deepcopy(doc)
        stored.setdefault("_id", ObjectId())
        self.docs.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def find_one(self, query: dict[str, Any]):
        for doc in self.docs:
            if self._matches(doc, query):
                return deepcopy(doc)
        return None

    async def update_one(self, query: dict[str, Any], update: dict[str, Any], **_: Any):
        for doc in self.docs:
            if self._matches(doc, query):
                self._apply_update(doc, update)
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    async def update_many(self, query: dict[str, Any], update: dict[str, Any], **_: Any):
        modified = 0
        for doc in self.docs:
            if self._matches(doc, query):
                self._apply_update(doc, update)
                modified += 1
        return SimpleNamespace(modified_count=modified)

    def find_by_hash(self, token: str) -> dict[str, Any] | None:
        token_hash = hash_refresh_token(token)
        for doc in self.docs:
            if doc.get("token_hash") == token_hash:
                return doc
        return None

    @staticmethod
    def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            if doc.get(key) != expected:
                return False
        return True

    @staticmethod
    def _apply_update(doc: dict[str, Any], update: dict[str, Any]) -> None:
        for key, value in update.get("$set", {}).items():
            doc[key] = value


class _FakeDb(dict):
    def __missing__(self, key: str):
        value = _FakeCollection()
        self[key] = value
        return value


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-refresh-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_ACCESS_EXPIRE_MINUTES", "15")
    monkeypatch.setenv("JWT_REFRESH_EXPIRE_DAYS", "30")
    monkeypatch.setenv("JWT_REFRESH_IDLE_DAYS", "7")
    monkeypatch.setenv("AUTH_REFRESH_COOKIE_SECURE", "false")


@pytest.fixture
def fake_db() -> _FakeDb:
    return _FakeDb()


@pytest.fixture
def app(fake_db: _FakeDb) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/auth")

    async def _override_db():
        yield fake_db

    app.dependency_overrides[get_database] = _override_db
    return app


async def _create_user(fake_db: _FakeDb, username: str = "student") -> str:
    now = datetime.now(timezone.utc)
    result = await fake_db[USERS_COLLECTION].insert_one(
        {
            "username": username,
            "password_hash": hash_password("password123"),
            "full_name": "Test User",
            "student_id": "20210001",
            "cohort": "K68",
            "major": "CNTT",
            "major_code": "IT1",
            "role": "student",
            "is_profile_complete": True,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login_at": now,
        }
    )
    return str(result.inserted_id)


@pytest.mark.anyio
async def test_web_login_sets_refresh_cookie_and_refresh_rotates(app: FastAPI, fake_db: _FakeDb):
    await _create_user(fake_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={"username": "student", "password": "password123"},
        )
        assert login.status_code == 200
        login_data = login.json()
        assert login_data["expires_in"] == 900
        assert login_data["refresh_token"] is None
        assert "refresh_token=" in login.headers["set-cookie"]
        assert "HttpOnly" in login.headers["set-cookie"]

        refreshed = await client.post("/auth/refresh")
        assert refreshed.status_code == 200
        refresh_data = refreshed.json()
        assert refresh_data["access_token"] != login_data["access_token"]
        assert refresh_data["refresh_token"] is None
        assert "refresh_token=" in refreshed.headers["set-cookie"]


@pytest.mark.anyio
async def test_mobile_login_returns_refresh_token(app: FastAPI, fake_db: _FakeDb):
    await _create_user(fake_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/login",
            json={
                "username": "student",
                "password": "password123",
                "client_type": "mobile",
            },
        )

    data = response.json()
    assert response.status_code == 200
    assert data["expires_in"] == 900
    assert data["refresh_token"]
    assert "set-cookie" not in response.headers


@pytest.mark.anyio
async def test_refresh_reuse_revokes_family(app: FastAPI, fake_db: _FakeDb):
    await _create_user(fake_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={
                "username": "student",
                "password": "password123",
                "client_type": "mobile",
            },
        )
        first_refresh = login.json()["refresh_token"]

        rotated = await client.post(
            "/auth/refresh",
            json={"refresh_token": first_refresh, "client_type": "mobile"},
        )
        second_refresh = rotated.json()["refresh_token"]
        assert rotated.status_code == 200
        assert second_refresh != first_refresh

        reused = await client.post(
            "/auth/refresh",
            json={"refresh_token": first_refresh, "client_type": "mobile"},
        )
        assert reused.status_code == 401

        family_revoked = await client.post(
            "/auth/refresh",
            json={"refresh_token": second_refresh, "client_type": "mobile"},
        )
        assert family_revoked.status_code == 401


@pytest.mark.anyio
async def test_logout_revokes_refresh_token(app: FastAPI, fake_db: _FakeDb):
    await _create_user(fake_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={
                "username": "student",
                "password": "password123",
                "client_type": "mobile",
            },
        )
        refresh_token = login.json()["refresh_token"]

        logout = await client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token, "client_type": "mobile"},
        )
        assert logout.status_code == 200

        refreshed = await client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token, "client_type": "mobile"},
        )
        assert refreshed.status_code == 401


@pytest.mark.anyio
async def test_expired_refresh_token_is_rejected(app: FastAPI, fake_db: _FakeDb):
    await _create_user(fake_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={
                "username": "student",
                "password": "password123",
                "client_type": "mobile",
            },
        )
        refresh_token = login.json()["refresh_token"]

        token_doc = fake_db[REFRESH_TOKENS_COLLECTION].find_by_hash(refresh_token)
        assert token_doc is not None
        token_doc["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)

        refreshed = await client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token, "client_type": "mobile"},
        )
        assert refreshed.status_code == 401
