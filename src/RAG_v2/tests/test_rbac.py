"""Tests for Phase 1: Role System & RBAC.

Covers:
  - Student denied access to admin endpoints (403)
  - Admin allowed access to admin-protected routes (200)
  - Superadmin can create admin accounts
  - JWT includes role claim
  - role field default migration (existing users → "student")

Requires MongoDB running at localhost:27017.
Mark: integration
"""

# NOTE: intentionally NOT using `from __future__ import annotations` here
# because FastAPI needs real annotation evaluation for Depends() resolution
# when routes are defined inside test functions.

import os
from datetime import datetime, timezone
from typing import Annotated

import pytest
from bson import ObjectId
from fastapi import Depends, FastAPI
from pymongo import MongoClient

from auth.jwt_handler import create_access_token, get_current_user, verify_token
from auth.password import hash_password
from auth.rbac import require_admin
from models.user import UserDocument

TEST_DB = "rag_chatbot_test_rbac"
MONGO_URI = "mongodb://localhost:27017"
JWT_SECRET = "test-secret-key-for-rbac-tests"


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


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set env vars needed for JWT and database."""
    monkeypatch.setenv("JWT_SECRET_KEY", JWT_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("MONGODB_URI", MONGO_URI)
    monkeypatch.setenv("MONGODB_DATABASE", TEST_DB)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("SUPERADMIN_USER_IDS", "")


@pytest.fixture(autouse=True)
def _clean_db_and_motor():
    """Drop the test database before each test and reset Motor client."""
    import models.database as db_module

    db_module._motor_client = None

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.drop_database(TEST_DB)
    yield
    db_module._motor_client = None
    client.drop_database(TEST_DB)
    client.close()


def _create_user_in_db(
    username: str,
    password: str,
    role: str = "student",
    is_active: bool = True,
    omit_role: bool = False,
) -> str:
    """Insert a user directly into MongoDB and return their ObjectId string."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    db = client[TEST_DB]
    now = datetime.now(timezone.utc)
    doc = {
        "username": username,
        "password_hash": hash_password(password),
        "full_name": f"Test {username}",
        "student_id": "test-001",
        "cohort": "K69",
        "major": "CNTT",
        "major_code": "IT1",
        "is_profile_complete": True,
        "is_active": is_active,
        "created_at": now,
        "updated_at": now,
        "last_login_at": now,
    }
    if not omit_role:
        doc["role"] = role
    result = db["users"].insert_one(doc)
    client.close()
    return str(result.inserted_id)


def _get_token(user_id: str, role: str = "student") -> str:
    """Create a JWT for the given user_id and role."""
    return create_access_token(user_id=user_id, email="test@test.com", role=role)


def _make_auth_app() -> FastAPI:
    """Create a minimal FastAPI app with the auth router."""
    from routers.auth import router

    app = FastAPI()
    app.include_router(router, prefix="/auth")
    return app


# Pre-build the admin-test app at module level so FastAPI resolves
# Annotated[..., Depends(...)] with access to module-level symbols.
_rbac_test_app = FastAPI()


@_rbac_test_app.get("/admin/test")
async def _admin_only_endpoint(
    user: Annotated[UserDocument, Depends(require_admin)],
):
    return {"user_id": str(user.id), "role": user.role}


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: JWT role claim
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestJWTRoleClaim:
    """Verify that the JWT includes the role claim."""

    def test_jwt_contains_role_claim(self):
        token = create_access_token(
            user_id="abc123def456abc123def456",
            email="test@sis.hust.edu.vn",
            role="admin",
        )
        payload = verify_token(token)
        assert payload["role"] == "admin"

    def test_jwt_default_role_is_student(self):
        token = create_access_token(
            user_id="abc123def456abc123def456",
            email="test@sis.hust.edu.vn",
        )
        payload = verify_token(token)
        assert payload["role"] == "student"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Model / Schema unit tests
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestRBACDependencies:
    """Test model and schema role fields."""

    def test_user_model_default_role_is_student(self):
        user = UserDocument(
            full_name="Test User",
            student_id="20200001",
            cohort="K65",
        )
        assert user.role == "student"

    def test_user_model_admin_role(self):
        user = UserDocument(
            full_name="Admin User",
            student_id="admin-001",
            cohort="K65",
            role="admin",
        )
        assert user.role == "admin"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Login returns role in JWT and UserPublic
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestLoginRole:
    """Verify login endpoint returns role in JWT and user response."""

    @pytest.mark.asyncio
    async def test_student_login_returns_student_role(self):
        from httpx import ASGITransport, AsyncClient

        _create_user_in_db(username="login_student", password="password123", role="student")
        app = _make_auth_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/login",
                json={"username": "login_student", "password": "password123"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["user"]["role"] == "student"
            payload = verify_token(data["access_token"])
            assert payload["role"] == "student"

    @pytest.mark.asyncio
    async def test_admin_login_returns_admin_role(self):
        from httpx import ASGITransport, AsyncClient

        _create_user_in_db(username="login_admin", password="password123", role="admin")
        app = _make_auth_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/login",
                json={"username": "login_admin", "password": "password123"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["user"]["role"] == "admin"
            payload = verify_token(data["access_token"])
            assert payload["role"] == "admin"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Admin create endpoint
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestAdminCreate:
    """Test POST /auth/admin/create endpoint."""

    @pytest.mark.asyncio
    async def test_superadmin_can_create_admin(self, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        superadmin_id = _create_user_in_db(
            username="sa_superadmin", password="superpass123", role="admin"
        )
        monkeypatch.setenv("SUPERADMIN_USER_IDS", superadmin_id)

        app = _make_auth_app()
        token = _get_token(superadmin_id, role="admin")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/admin/create",
                json={
                    "username": "new_admin",
                    "password": "adminpass123",
                    "full_name": "New Admin User",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["role"] == "admin"
            assert data["full_name"] == "New Admin User"

    @pytest.mark.asyncio
    async def test_student_cannot_create_admin(self, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        student_id = _create_user_in_db(
            username="sa_student", password="password123", role="student"
        )
        superadmin_id = _create_user_in_db(
            username="sa_superadmin2", password="superpass123", role="admin"
        )
        monkeypatch.setenv("SUPERADMIN_USER_IDS", superadmin_id)

        app = _make_auth_app()
        token = _get_token(student_id, role="student")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/admin/create",
                json={
                    "username": "should_fail",
                    "password": "adminpass123",
                    "full_name": "Should Not Exist",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_non_superadmin_admin_cannot_create_admin(self, monkeypatch):
        """An admin who is NOT in SUPERADMIN_USER_IDS gets 403."""
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db(
            username="sa_regular_admin", password="password123", role="admin"
        )
        superadmin_id = _create_user_in_db(
            username="sa_real_super", password="superpass123", role="admin"
        )
        monkeypatch.setenv("SUPERADMIN_USER_IDS", superadmin_id)

        app = _make_auth_app()
        token = _get_token(admin_id, role="admin")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/admin/create",
                json={
                    "username": "another_fail",
                    "password": "adminpass123",
                    "full_name": "Should Not Exist",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_duplicate_username_returns_409(self, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        superadmin_id = _create_user_in_db(
            username="sa_dup_super", password="superpass123", role="admin"
        )
        monkeypatch.setenv("SUPERADMIN_USER_IDS", superadmin_id)

        app = _make_auth_app()
        token = _get_token(superadmin_id, role="admin")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/admin/create",
                json={
                    "username": "sa_dup_super",  # already exists
                    "password": "adminpass123",
                    "full_name": "Duplicate",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self):
        from httpx import ASGITransport, AsyncClient

        app = _make_auth_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/admin/create",
                json={
                    "username": "no_auth_admin",
                    "password": "adminpass123",
                    "full_name": "No Auth",
                },
            )
            assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: RBAC require_admin dependency (integration via module-level app)
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestRequireAdminEndpoint:
    """Test require_admin as a route dependency."""

    @pytest.mark.asyncio
    async def test_admin_gets_200(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db(
            username="rbac_admin", password="password123", role="admin"
        )
        token = _get_token(admin_id, role="admin")

        async with AsyncClient(
            transport=ASGITransport(app=_rbac_test_app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/admin/test",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
            assert resp.json()["role"] == "admin"

    @pytest.mark.asyncio
    async def test_student_gets_403(self):
        from httpx import ASGITransport, AsyncClient

        student_id = _create_user_in_db(
            username="rbac_student", password="password123", role="student"
        )
        token = _get_token(student_id, role="student")

        async with AsyncClient(
            transport=ASGITransport(app=_rbac_test_app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/admin/test",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_no_token_gets_401(self):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=_rbac_test_app), base_url="http://test"
        ) as client:
            resp = await client.get("/admin/test")
            assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Backward compatibility — existing users without role field
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestBackwardCompatibility:
    """Ensure users without a role field default to 'student'."""

    @pytest.mark.asyncio
    async def test_legacy_user_defaults_to_student_role(self):
        from httpx import ASGITransport, AsyncClient

        _create_user_in_db(
            username="legacy_user", password="password123", omit_role=True
        )
        app = _make_auth_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/login",
                json={"username": "legacy_user", "password": "password123"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["user"]["role"] == "student"

    @pytest.mark.asyncio
    async def test_legacy_user_gets_student_role_in_jwt(self):
        from httpx import ASGITransport, AsyncClient

        _create_user_in_db(
            username="legacy_jwt_user", password="password123", omit_role=True
        )
        app = _make_auth_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/auth/login",
                json={"username": "legacy_jwt_user", "password": "password123"},
            )
            assert resp.status_code == 200
            payload = verify_token(resp.json()["access_token"])
            assert payload["role"] == "student"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestSettings:
    """Verify new settings fields exist with correct defaults."""

    def test_superadmin_user_ids_default(self):
        from config.settings import Settings

        s = Settings(
            google_api_key="test",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.superadmin_user_ids == ""

    def test_upload_settings_defaults(self):
        from config.settings import Settings

        s = Settings(
            google_api_key="test",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.upload_dir == "uploads"
        assert s.max_upload_size_mb == 50
        assert s.max_upload_batch == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Schema validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemas:
    """Verify schema changes for Phase 1."""

    def test_user_public_has_role_field(self):
        from schemas.user import UserPublic

        now = datetime.now(timezone.utc)
        user = UserPublic(
            full_name="Test",
            student_id="001",
            cohort="K65",
            major="CNTT",
            role="admin",
            is_profile_complete=True,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=now,
        )
        assert user.role == "admin"

    def test_user_public_role_defaults_to_student(self):
        from schemas.user import UserPublic

        now = datetime.now(timezone.utc)
        user = UserPublic(
            full_name="Test",
            student_id="001",
            cohort="K65",
            major="CNTT",
            is_profile_complete=True,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=now,
        )
        assert user.role == "student"

    def test_admin_create_request_validation(self):
        from schemas.user import AdminCreateRequest

        req = AdminCreateRequest(
            username="admin1",
            password="longpassword",
            full_name="Admin One",
        )
        assert req.username == "admin1"
        assert req.student_id == "admin"  # default
        assert req.cohort == "N/A"  # default

    def test_admin_create_request_short_username_fails(self):
        from schemas.user import AdminCreateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AdminCreateRequest(
                username="ab",  # too short (min_length=3)
                password="longpassword",
                full_name="Admin",
            )

    def test_admin_create_request_short_password_fails(self):
        from schemas.user import AdminCreateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AdminCreateRequest(
                username="admin1",
                password="short",  # too short (min_length=8)
                full_name="Admin",
            )
