"""Tests for Phase 4: File Storage — LocalStorage backend.

Covers:
  - save_upload: save an uploaded file, return relative path
  - save_text: save text content (markdown, cleaned), return relative path
  - read_text: read stored text content
  - read_text: raises FileNotFoundError for missing path
  - delete_all: remove entire document directory
  - delete_all: no-op when doc directory does not exist (idempotent)
  - File-size boundary: large content round-trips correctly
  - Multiple documents isolated (different doc_ids)

All tests run against a real temp directory (no mocking of disk I/O).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import UploadFile

from utils.storage import LocalStorage


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_upload_file(content: bytes, filename: str = "test.pdf") -> UploadFile:
    """Create a FastAPI UploadFile backed by an in-memory buffer."""
    return UploadFile(filename=filename, file=io.BytesIO(content))


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def storage(tmp_path: Path) -> LocalStorage:
    """Fresh LocalStorage rooted at a pytest tmp directory."""
    return LocalStorage(base_dir=str(tmp_path / "uploads"))


@pytest.fixture()
def doc_id() -> str:
    return "507f1f77bcf86cd799439011"


# ═══════════════════════════════════════════════════════════════════════════════
# save_upload
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_save_upload_returns_relative_path(storage: LocalStorage, doc_id: str):
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    upload = _make_upload_file(pdf_bytes)

    rel_path = await storage.save_upload(upload, doc_id)

    assert rel_path == f"{doc_id}/original.pdf"


@pytest.mark.asyncio
async def test_save_upload_file_exists_on_disk(storage: LocalStorage, doc_id: str):
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    upload = _make_upload_file(pdf_bytes)

    await storage.save_upload(upload, doc_id)

    dest = storage.base_dir / doc_id / "original.pdf"
    assert dest.is_file()
    assert dest.read_bytes() == pdf_bytes


@pytest.mark.asyncio
async def test_save_upload_creates_doc_directory(storage: LocalStorage, doc_id: str):
    upload = _make_upload_file(b"content", filename="doc.pdf")

    await storage.save_upload(upload, doc_id)

    assert (storage.base_dir / doc_id).is_dir()


@pytest.mark.asyncio
async def test_save_upload_large_file(storage: LocalStorage, doc_id: str):
    """Round-trip 5 MB of binary content."""
    large_content = b"A" * (5 * 1024 * 1024)
    upload = _make_upload_file(large_content)

    rel_path = await storage.save_upload(upload, doc_id)
    dest = storage.base_dir / rel_path

    assert dest.read_bytes() == large_content


# ═══════════════════════════════════════════════════════════════════════════════
# save_text
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_save_text_markdown(storage: LocalStorage, doc_id: str):
    content = "# Heading\nSome markdown content."

    rel_path = await storage.save_text(content, doc_id, "markdown.md")

    assert rel_path == f"{doc_id}/markdown.md"
    dest = storage.base_dir / doc_id / "markdown.md"
    assert dest.read_text(encoding="utf-8") == content


@pytest.mark.asyncio
async def test_save_text_cleaned(storage: LocalStorage, doc_id: str):
    content = "Cleaned markdown without noise."

    rel_path = await storage.save_text(content, doc_id, "cleaned.md")

    assert rel_path == f"{doc_id}/cleaned.md"


@pytest.mark.asyncio
async def test_save_text_unicode(storage: LocalStorage, doc_id: str):
    content = "Tiếng Việt: Đại học Bách khoa Hà Nội"

    rel_path = await storage.save_text(content, doc_id, "markdown.md")
    dest = storage.base_dir / rel_path

    assert dest.read_text(encoding="utf-8") == content


@pytest.mark.asyncio
async def test_save_text_overwrites_existing(storage: LocalStorage, doc_id: str):
    await storage.save_text("original", doc_id, "markdown.md")
    await storage.save_text("revised", doc_id, "markdown.md")

    dest = storage.base_dir / doc_id / "markdown.md"
    assert dest.read_text(encoding="utf-8") == "revised"


# ═══════════════════════════════════════════════════════════════════════════════
# read_text
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_read_text_round_trip(storage: LocalStorage, doc_id: str):
    content = "# Hello\nWorld"
    rel_path = await storage.save_text(content, doc_id, "markdown.md")

    result = await storage.read_text(rel_path)

    assert result == content


@pytest.mark.asyncio
async def test_read_text_missing_file_raises(storage: LocalStorage, doc_id: str):
    with pytest.raises(FileNotFoundError):
        await storage.read_text(f"{doc_id}/nonexistent.md")


@pytest.mark.asyncio
async def test_read_text_after_upload(storage: LocalStorage, doc_id: str):
    """After saving an upload, reading it via relative path works."""
    pdf_bytes = b"binary pdf data"
    upload = _make_upload_file(pdf_bytes)
    rel_path = await storage.save_upload(upload, doc_id)

    # write a text file and read it back (upload is binary, not text)
    text_path = await storage.save_text("# doc", doc_id, "markdown.md")
    result = await storage.read_text(text_path)

    assert result == "# doc"
    assert rel_path == f"{doc_id}/original.pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# delete_all
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_delete_all_removes_directory(storage: LocalStorage, doc_id: str):
    await storage.save_text("some content", doc_id, "markdown.md")
    assert (storage.base_dir / doc_id).is_dir()

    await storage.delete_all(doc_id)

    assert not (storage.base_dir / doc_id).exists()


@pytest.mark.asyncio
async def test_delete_all_removes_all_files(storage: LocalStorage, doc_id: str):
    upload = _make_upload_file(b"pdf data")
    await storage.save_upload(upload, doc_id)
    await storage.save_text("markdown", doc_id, "markdown.md")
    await storage.save_text("cleaned", doc_id, "cleaned.md")

    await storage.delete_all(doc_id)

    assert not (storage.base_dir / doc_id).exists()


@pytest.mark.asyncio
async def test_delete_all_is_idempotent(storage: LocalStorage, doc_id: str):
    """Deleting a non-existent doc_id should not raise."""
    await storage.delete_all("nonexistent-doc-id")  # no error


@pytest.mark.asyncio
async def test_delete_all_does_not_affect_other_docs(storage: LocalStorage):
    doc_id_a = "aaaaaaaaaaaaaaaaaaaaaa01"
    doc_id_b = "bbbbbbbbbbbbbbbbbbbbbb02"

    await storage.save_text("doc A content", doc_id_a, "markdown.md")
    await storage.save_text("doc B content", doc_id_b, "markdown.md")

    await storage.delete_all(doc_id_a)

    assert not (storage.base_dir / doc_id_a).exists()
    assert (storage.base_dir / doc_id_b / "markdown.md").is_file()


# ═══════════════════════════════════════════════════════════════════════════════
# Settings integration
# ═══════════════════════════════════════════════════════════════════════════════


def test_settings_upload_fields():
    """Settings exposes upload-related fields with correct defaults."""
    import os

    # Strip any env overrides to check pure defaults
    env_backup = {k: os.environ.pop(k, None) for k in
                  ("UPLOAD_DIR", "MAX_UPLOAD_SIZE_MB", "MAX_UPLOAD_BATCH", "SUPERADMIN_USER_IDS")}
    try:
        # Re-import with clean env
        import importlib
        import config.settings as settings_mod
        importlib.reload(settings_mod)
        s = settings_mod.Settings(_env_file=None)  # type: ignore[call-arg]

        assert s.upload_dir == "uploads"
        assert s.max_upload_size_mb == 50
        assert s.max_upload_batch == 5
        assert s.superadmin_user_ids == ""
    finally:
        for k, v in env_backup.items():
            if v is not None:
                os.environ[k] = v


def test_settings_upload_fields_env_override(monkeypatch):
    """Settings reads upload config from environment variables."""
    monkeypatch.setenv("UPLOAD_DIR", "/tmp/my_uploads")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "100")
    monkeypatch.setenv("MAX_UPLOAD_BATCH", "10")
    monkeypatch.setenv("SUPERADMIN_USER_IDS", "abc123,def456")

    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)
    s = settings_mod.Settings()

    assert s.upload_dir == "/tmp/my_uploads"
    assert s.max_upload_size_mb == 100
    assert s.max_upload_batch == 10
    assert s.superadmin_user_ids == "abc123,def456"
