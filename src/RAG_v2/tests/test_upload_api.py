"""Tests for Phase 2: Document Model, Upload API & Storage.

Covers:
  - DocumentRecord and DocumentChunk models
  - All 15 admin document API endpoints
  - Pagination, filtering, error codes
  - LocalStorage backend
  - Background pipeline steps (convert, clean, chunk)
  - Delete + cleanup
  - Status transitions and conflict detection

Requires MongoDB running at localhost:27017.
"""

import asyncio
import io
import json
import os
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from pymongo import MongoClient

from auth.jwt_handler import create_access_token
from auth.password import hash_password
from models.database import (
    DOCUMENTS_COLLECTION,
    DOCUMENT_CHUNKS_COLLECTION,
    USERS_COLLECTION,
)

TEST_DB = "rag_chatbot_test_upload"
MONGO_URI = "mongodb://localhost:27017"
JWT_SECRET = "test-secret-key-for-upload-tests"


def _mongo_available() -> bool:
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


requires_mongo = pytest.mark.skipif(
    not _mongo_available(),
    reason="MongoDB not available at localhost:27017",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _set_env(monkeypatch, tmp_path):
    """Set env vars for JWT, database, and uploads."""
    monkeypatch.setenv("JWT_SECRET_KEY", JWT_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("MONGODB_URI", MONGO_URI)
    monkeypatch.setenv("MONGODB_DATABASE", TEST_DB)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("SUPERADMIN_USER_IDS", "")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))


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


@pytest.fixture(autouse=True)
def _reset_storage():
    """Reset the module-level storage and pipeline singletons between tests."""
    import api.routes.upload as upload_module

    upload_module._storage = None
    upload_module._pipeline = None
    yield
    upload_module._storage = None
    upload_module._pipeline = None


def _create_user_in_db(
    username: str,
    password: str,
    role: str = "admin",
    is_active: bool = True,
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
        "role": role,
        "is_profile_complete": True,
        "is_active": is_active,
        "created_at": now,
        "updated_at": now,
        "last_login_at": now,
    }
    result = db[USERS_COLLECTION].insert_one(doc)
    client.close()
    return str(result.inserted_id)


def _get_token(user_id: str, role: str = "admin") -> str:
    return create_access_token(user_id=user_id, email="test@test.com", role=role)


def _make_upload_app() -> FastAPI:
    """Create a minimal FastAPI app with the upload router."""
    from api.routes.upload import router

    app = FastAPI()
    app.include_router(router)
    return app


def _create_test_pdf() -> bytes:
    """Create a minimal valid PDF byte string for testing."""
    # Minimal PDF structure
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n206\n%%EOF\n"
    )


def _insert_document(
    collection: str = "quydinh",
    status: str = "uploaded",
    filename: str = "test.pdf",
    uploaded_by: Optional[str] = None,
    markdown_path: Optional[str] = None,
    cleaned_path: Optional[str] = None,
    chunk_ids: Optional[list] = None,
) -> str:
    """Insert a document record directly into MongoDB."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    db = client[TEST_DB]
    now = datetime.now(timezone.utc)
    doc_id = ObjectId()
    doc = {
        "_id": doc_id,
        "filename": filename,
        "file_size": 1024,
        "file_path": f"{doc_id}/original.pdf",
        "collection": collection,
        "status": status,
        "uploaded_by": ObjectId(uploaded_by) if uploaded_by else ObjectId(),
        "uploaded_at": now,
        "markdown_path": markdown_path,
        "cleaned_path": cleaned_path,
        "chunk_count": len(chunk_ids) if chunk_ids else None,
        "chunk_ids": chunk_ids,
        "chunking_strategy": "recursive",
        "markdown_reviewed": False,
        "cleaned_reviewed": False,
        "chunks_reviewed": False,
        "metadata_overrides": {},
        "error_message": None,
        "converted_at": None,
        "cleaned_at": None,
        "chunked_at": None,
        "indexed_at": None,
        "audit_log": [],
    }
    db[DOCUMENTS_COLLECTION].insert_one(doc)
    client.close()
    return str(doc_id)


def _insert_chunks(doc_id: str, count: int = 3) -> list[str]:
    """Insert test chunks into MongoDB."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    db = client[TEST_DB]
    chunk_ids = []
    for i in range(count):
        cid = ObjectId()
        db[DOCUMENT_CHUNKS_COLLECTION].insert_one(
            {
                "_id": cid,
                "document_id": ObjectId(doc_id),
                "chunk_index": i,
                "content": f"Test chunk content {i}. This is some sample text.",
                "metadata": {"strategy": "recursive", "document_id": doc_id},
            }
        )
        chunk_ids.append(str(cid))
    client.close()
    return chunk_ids


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: DocumentRecord model
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocumentRecordModel:
    """Test the DocumentRecord Pydantic model."""

    def test_default_values(self):
        from models.document import DocumentRecord

        doc = DocumentRecord(
            filename="test.pdf",
            file_size=1024,
            file_path="abc/original.pdf",
            collection="quydinh",
            uploaded_by="507f1f77bcf86cd799439011",
        )
        assert doc.status == "uploaded"
        assert doc.markdown_reviewed is False
        assert doc.cleaned_reviewed is False
        assert doc.chunks_reviewed is False
        assert doc.metadata_overrides == {}
        assert doc.audit_log == []
        assert doc.error_message is None

    def test_from_mongo(self):
        from models.document import DocumentRecord

        now = datetime.now(timezone.utc)
        raw = {
            "_id": ObjectId(),
            "filename": "test.pdf",
            "file_size": 2048,
            "file_path": "abc/original.pdf",
            "collection": "ctdt",
            "status": "converted",
            "uploaded_by": str(ObjectId()),
            "uploaded_at": now,
            "markdown_path": "abc/markdown.md",
            "cleaned_path": None,
            "chunk_count": None,
            "chunk_ids": None,
            "chunking_strategy": "recursive",
            "markdown_reviewed": True,
            "cleaned_reviewed": False,
            "chunks_reviewed": False,
            "metadata_overrides": {"cohort": "K70"},
            "error_message": None,
            "converted_at": now,
            "cleaned_at": None,
            "chunked_at": None,
            "indexed_at": None,
            "audit_log": [],
        }
        doc = DocumentRecord.from_mongo(raw)
        assert doc.filename == "test.pdf"
        assert doc.status == "converted"
        assert doc.markdown_reviewed is True


class TestDocumentChunkModel:
    """Test the DocumentChunk Pydantic model."""

    def test_create_chunk(self):
        from models.document_chunk import DocumentChunk

        chunk = DocumentChunk(
            document_id="507f1f77bcf86cd799439011",
            chunk_index=0,
            content="Some chunk text",
        )
        assert chunk.chunk_index == 0
        assert chunk.metadata == {}

    def test_from_mongo(self):
        from models.document_chunk import DocumentChunk

        raw = {
            "_id": ObjectId(),
            "document_id": str(ObjectId()),
            "chunk_index": 2,
            "content": "chunk content",
            "metadata": {"strategy": "recursive"},
        }
        chunk = DocumentChunk.from_mongo(raw)
        assert chunk.chunk_index == 2
        assert chunk.metadata["strategy"] == "recursive"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: DocumentDetail schema
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocumentSchemas:
    """Test document API schemas."""

    def test_document_detail_from_document(self):
        from schemas.document import DocumentDetail

        now = datetime.now(timezone.utc)
        doc = {
            "_id": ObjectId(),
            "filename": "test.pdf",
            "file_size": 1024,
            "status": "uploaded",
            "collection": "quydinh",
            "chunking_strategy": "recursive",
            "chunk_count": None,
            "markdown_reviewed": False,
            "cleaned_reviewed": False,
            "chunks_reviewed": False,
            "metadata_overrides": {},
            "uploaded_by": ObjectId(),
            "uploaded_at": now,
            "error_message": None,
        }
        detail = DocumentDetail.from_document(doc)
        assert detail.status == "uploaded"
        assert detail.collection == "quydinh"

    def test_upload_request_valid_collection(self):
        from schemas.document import DocumentUploadRequest

        req = DocumentUploadRequest(collection="ctdt")
        assert req.collection == "ctdt"

    def test_upload_request_invalid_collection(self):
        from schemas.document import DocumentUploadRequest

        with pytest.raises(Exception):
            DocumentUploadRequest(collection="invalid_collection")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: LocalStorage
# ═══════════════════════════════════════════════════════════════════════════════


class TestLocalStorage:
    """Test file storage backend."""

    @pytest.mark.asyncio
    async def test_save_and_read_text(self, tmp_path):
        from utils.storage import LocalStorage

        storage = LocalStorage(base_dir=str(tmp_path / "storage"))
        doc_id = str(ObjectId())

        path = await storage.save_text("hello world", doc_id, "test.md")
        content = await storage.read_text(path)
        assert content == "hello world"

    @pytest.mark.asyncio
    async def test_delete_all(self, tmp_path):
        from utils.storage import LocalStorage

        storage = LocalStorage(base_dir=str(tmp_path / "storage"))
        doc_id = str(ObjectId())

        await storage.save_text("content", doc_id, "file.md")
        assert (tmp_path / "storage" / doc_id / "file.md").exists()

        await storage.delete_all(doc_id)
        assert not (tmp_path / "storage" / doc_id).exists()

    @pytest.mark.asyncio
    async def test_read_nonexistent(self, tmp_path):
        from utils.storage import LocalStorage

        storage = LocalStorage(base_dir=str(tmp_path / "storage"))
        with pytest.raises(FileNotFoundError):
            await storage.read_text("nonexistent/file.md")

    @pytest.mark.asyncio
    async def test_save_upload(self, tmp_path):
        from unittest.mock import AsyncMock

        from utils.storage import LocalStorage

        storage = LocalStorage(base_dir=str(tmp_path / "storage"))
        doc_id = str(ObjectId())

        # Mock UploadFile
        mock_file = AsyncMock()
        mock_file.read.return_value = b"PDF content"

        path = await storage.save_upload(mock_file, doc_id)
        assert "original.pdf" in path


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Upload API — POST /admin/documents
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestUploadDocuments:
    """Test document upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_single_pdf(self, tmp_path, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        admin_id = _create_user_in_db("upload_admin", "pass123", role="admin")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        pdf_content = _create_test_pdf()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/admin/documents",
                files=[("files", ("test.pdf", pdf_content, "application/pdf"))],
                data={"collection": "quydinh"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201, f"Got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert len(data) == 1
            assert data[0]["filename"] == "test.pdf"
            assert data[0]["status"] == "uploaded"
            assert data[0]["collection"] == "quydinh"

    @pytest.mark.asyncio
    async def test_upload_invalid_collection(self, tmp_path, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        admin_id = _create_user_in_db("upload_admin2", "pass123", role="admin")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/admin/documents",
                files=[("files", ("test.pdf", b"data", "application/pdf"))],
                data={"collection": "invalid"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_non_pdf_rejected(self, tmp_path, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        admin_id = _create_user_in_db("upload_admin3", "pass123", role="admin")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/admin/documents",
                files=[("files", ("test.txt", b"not a pdf", "text/plain"))],
                data={"collection": "quydinh"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_student_cannot_upload(self, tmp_path, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        student_id = _create_user_in_db("student_user", "pass123", role="student")
        token = _get_token(student_id, role="student")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/admin/documents",
                files=[("files", ("test.pdf", _create_test_pdf(), "application/pdf"))],
                data={"collection": "quydinh"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_upload_401(self, tmp_path, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/admin/documents",
                files=[("files", ("test.pdf", _create_test_pdf(), "application/pdf"))],
                data={"collection": "quydinh"},
            )
            assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: List documents — GET /admin/documents
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestListDocuments:
    """Test document listing with pagination and filters."""

    @pytest.mark.asyncio
    async def test_list_empty(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("list_admin", "pass123", role="admin")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/admin/documents",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["documents"] == []

    @pytest.mark.asyncio
    async def test_list_with_documents(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("list_admin2", "pass123", role="admin")
        _insert_document(collection="quydinh", uploaded_by=admin_id)
        _insert_document(collection="ctdt", uploaded_by=admin_id)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/admin/documents",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("list_admin3", "pass123", role="admin")
        _insert_document(status="uploaded", uploaded_by=admin_id)
        _insert_document(status="converted", uploaded_by=admin_id)
        _insert_document(status="indexed", uploaded_by=admin_id)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/admin/documents?status=uploaded",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["documents"][0]["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_list_filter_by_collection(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("list_admin4", "pass123", role="admin")
        _insert_document(collection="quydinh", uploaded_by=admin_id)
        _insert_document(collection="ctdt", uploaded_by=admin_id)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/admin/documents?collection=ctdt",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["documents"][0]["collection"] == "ctdt"

    @pytest.mark.asyncio
    async def test_list_pagination(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("list_admin5", "pass123", role="admin")
        for _ in range(5):
            _insert_document(uploaded_by=admin_id)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/admin/documents?page=1&limit=2",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 5
            assert len(data["documents"]) == 2
            assert data["page"] == 1
            assert data["limit"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Get document detail — GET /admin/documents/{id}
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestGetDocument:
    """Test document detail endpoint."""

    @pytest.mark.asyncio
    async def test_get_existing_document(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("detail_admin", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, filename="detail.pdf")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/admin/documents/{doc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == doc_id
            assert data["filename"] == "detail.pdf"

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("detail_admin2", "pass123", role="admin")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()
        fake_id = str(ObjectId())

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/admin/documents/{fake_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_invalid_id(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("detail_admin3", "pass123", role="admin")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/admin/documents/invalid-id",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Delete document — DELETE /admin/documents/{id}
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestDeleteDocument:
    """Test document deletion and cleanup."""

    @pytest.mark.asyncio
    async def test_delete_document(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("del_admin", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/admin/documents/{doc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            assert resp.json()["id"] == doc_id

            # Verify document is gone
            resp2 = await client.get(
                f"/admin/documents/{doc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_with_chunks(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("del_admin2", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id)
        chunk_ids = _insert_chunks(doc_id, count=3)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/admin/documents/{doc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200

        # Verify chunks are deleted too
        client_sync = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        db = client_sync[TEST_DB]
        remaining = db[DOCUMENT_CHUNKS_COLLECTION].count_documents(
            {"document_id": ObjectId(doc_id)}
        )
        assert remaining == 0
        client_sync.close()

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("del_admin3", "pass123", role="admin")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()
        fake_id = str(ObjectId())

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/admin/documents/{fake_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Markdown review — GET/PUT /admin/documents/{id}/markdown
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestMarkdownReview:
    """Test markdown get/edit/approve."""

    @pytest.mark.asyncio
    async def test_get_markdown_not_available(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("md_admin", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/admin/documents/{doc_id}/markdown",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_markdown_available(self, tmp_path, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        upload_dir = tmp_path / "uploads"
        monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

        admin_id = _create_user_in_db("md_admin2", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id)

        # Write markdown file
        doc_dir = upload_dir / doc_id
        doc_dir.mkdir(parents=True)
        (doc_dir / "markdown.md").write_text("# Hello", encoding="utf-8")

        # Update doc to have markdown_path
        client_sync = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client_sync[TEST_DB][DOCUMENTS_COLLECTION].update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"markdown_path": f"{doc_id}/markdown.md", "status": "converted"}},
        )
        client_sync.close()

        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/admin/documents/{doc_id}/markdown",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            assert resp.json()["content"] == "# Hello"

    @pytest.mark.asyncio
    async def test_put_markdown_approve(self, tmp_path, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        upload_dir = tmp_path / "uploads"
        monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

        admin_id = _create_user_in_db("md_admin3", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="converted")

        # Create doc dir
        doc_dir = upload_dir / doc_id
        doc_dir.mkdir(parents=True)

        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"/admin/documents/{doc_id}/markdown",
                json={"content": "# Edited markdown"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200

        # Verify in DB
        client_sync = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        doc = client_sync[TEST_DB][DOCUMENTS_COLLECTION].find_one(
            {"_id": ObjectId(doc_id)}
        )
        assert doc["markdown_reviewed"] is True
        assert doc["markdown_path"] is not None
        client_sync.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Cleaned review — GET/PUT /admin/documents/{id}/cleaned
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestCleanedReview:
    """Test cleaned content get/edit/approve."""

    @pytest.mark.asyncio
    async def test_get_cleaned_not_available(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("cl_admin", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/admin/documents/{doc_id}/cleaned",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_put_cleaned_approve(self, tmp_path, monkeypatch):
        from httpx import ASGITransport, AsyncClient

        upload_dir = tmp_path / "uploads"
        monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

        admin_id = _create_user_in_db("cl_admin2", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="cleaned")

        doc_dir = upload_dir / doc_id
        doc_dir.mkdir(parents=True)

        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"/admin/documents/{doc_id}/cleaned",
                json={"content": "Cleaned content here"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200

        # Verify in DB
        client_sync = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        doc = client_sync[TEST_DB][DOCUMENTS_COLLECTION].find_one(
            {"_id": ObjectId(doc_id)}
        )
        assert doc["cleaned_reviewed"] is True
        client_sync.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Chunks — GET/PUT /admin/documents/{id}/chunks
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestChunksEndpoints:
    """Test chunk listing and approval."""

    @pytest.mark.asyncio
    async def test_get_chunks_empty(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("chunk_admin", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/admin/documents/{doc_id}/chunks",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["chunks"] == []

    @pytest.mark.asyncio
    async def test_get_chunks_with_data(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("chunk_admin2", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="chunked")
        _insert_chunks(doc_id, count=5)
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/admin/documents/{doc_id}/chunks?page=1&limit=3",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 5
            assert len(data["chunks"]) == 3
            assert data["strategy"] == "recursive"
            assert "avg_size" in data["stats"]

    @pytest.mark.asyncio
    async def test_approve_chunks(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("chunk_admin3", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="chunked")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"/admin/documents/{doc_id}/chunks",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200

        # Verify in DB
        client_sync = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        doc = client_sync[TEST_DB][DOCUMENTS_COLLECTION].find_one(
            {"_id": ObjectId(doc_id)}
        )
        assert doc["chunks_reviewed"] is True
        client_sync.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Status transition / conflict detection
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestStatusTransitions:
    """Test that pipeline steps enforce correct status transitions."""

    @pytest.mark.asyncio
    async def test_convert_requires_uploaded_status(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("status_admin", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="converted")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/admin/documents/{doc_id}/convert",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_clean_requires_converted_status(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("status_admin2", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="uploaded")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/admin/documents/{doc_id}/clean",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_chunk_requires_cleaned_or_converted(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("status_admin3", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="uploaded")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/admin/documents/{doc_id}/chunk",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_index_requires_chunked_status(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("status_admin4", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="uploaded")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/admin/documents/{doc_id}/index",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_pipeline_requires_uploaded_status(self):
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("status_admin5", "pass123", role="admin")
        doc_id = _insert_document(uploaded_by=admin_id, status="indexed")
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/admin/documents/{doc_id}/pipeline",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_failed_status_allows_retry(self):
        """Documents with status 'failed' should allow retrying convert."""
        from httpx import ASGITransport, AsyncClient

        admin_id = _create_user_in_db("status_admin6", "pass123", role="admin")
        doc_id = _insert_document(
            uploaded_by=admin_id, status="failed"
        )
        token = _get_token(admin_id, role="admin")
        app = _make_upload_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/admin/documents/{doc_id}/convert",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 202


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Background chunk task
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestBackgroundChunk:
    """Test the background chunking task directly."""

    @pytest.mark.asyncio
    async def test_bg_chunk_creates_chunks(self, tmp_path, monkeypatch):
        """Test that _bg_chunk creates chunks in document_chunks collection."""
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

        from api.routes.upload import _bg_chunk

        admin_id = _create_user_in_db("bg_admin", "pass123", role="admin")
        doc_id = _insert_document(
            uploaded_by=admin_id,
            status="cleaned",
        )

        # Write cleaned content
        upload_dir = tmp_path / "uploads"
        doc_dir = upload_dir / doc_id
        doc_dir.mkdir(parents=True)
        text = "Paragraph one. Some content.\n\nParagraph two. More content.\n\nParagraph three."
        (doc_dir / "cleaned.md").write_text(text, encoding="utf-8")

        # Update document with cleaned_path
        client_sync = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client_sync[TEST_DB][DOCUMENTS_COLLECTION].update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"cleaned_path": f"{doc_id}/cleaned.md"}},
        )
        client_sync.close()

        # Run background task
        from models.database import get_motor_client

        motor_client = get_motor_client()
        db = motor_client[TEST_DB]

        await _bg_chunk(doc_id, "recursive", db)

        # Verify
        doc = await db[DOCUMENTS_COLLECTION].find_one({"_id": ObjectId(doc_id)})
        assert doc["status"] == "chunked"
        assert doc["chunk_count"] > 0

        chunk_count = await db[DOCUMENT_CHUNKS_COLLECTION].count_documents(
            {"document_id": ObjectId(doc_id)}
        )
        assert chunk_count > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Database indexes
# ═══════════════════════════════════════════════════════════════════════════════


@requires_mongo
class TestDatabaseIndexes:
    """Test that index creation works for document collections."""

    @pytest.mark.asyncio
    async def test_create_indexes(self):
        from models.database import create_indexes, get_motor_client

        await create_indexes()

        motor_client = get_motor_client()
        db = motor_client[TEST_DB]

        # Check documents collection indexes
        doc_indexes = await db[DOCUMENTS_COLLECTION].index_information()
        assert "uploaded_by_asc" in doc_indexes
        assert "status_asc" in doc_indexes
        assert "collection_asc" in doc_indexes

        # Check document_chunks indexes
        chunk_indexes = await db[DOCUMENT_CHUNKS_COLLECTION].index_information()
        assert "document_id_asc" in chunk_indexes
        assert "document_id_chunk_index" in chunk_indexes
