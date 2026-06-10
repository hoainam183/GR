"""File storage abstraction for document uploads.

Phase 1 implementation uses local disk storage. The abstract interface
allows swapping to S3/MinIO later without changing callers.
"""

from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import UploadFile

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract file-storage interface."""

    @abstractmethod
    async def save_upload(self, file: UploadFile, doc_id: str) -> str:
        """Save an uploaded file and return the relative path."""
        ...

    @abstractmethod
    async def save_text(self, content: str, doc_id: str, suffix: str) -> str:
        """Save text content (markdown, cleaned) and return relative path."""
        ...

    @abstractmethod
    async def read_text(self, path: str) -> str:
        """Read text content from a stored file."""
        ...

    @abstractmethod
    async def delete_all(self, doc_id: str) -> None:
        """Delete all files for a document."""
        ...


class LocalStorage(StorageBackend):
    """Local-disk storage backend.

    Structure::

        {base_dir}/
            {doc_id}/
                original.pdf
                markdown.md
                cleaned.md
    """

    def __init__(self, base_dir: str = "uploads") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _doc_dir(self, doc_id: str) -> Path:
        d = self.base_dir / doc_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def save_upload(self, file: UploadFile, doc_id: str) -> str:
        """Save uploaded PDF, return relative path."""
        doc_dir = self._doc_dir(doc_id)
        dest = doc_dir / "original.pdf"
        content = await file.read()
        dest.write_bytes(content)
        return str(dest.relative_to(self.base_dir))

    async def save_text(self, content: str, doc_id: str, suffix: str) -> str:
        """Save text file (e.g. markdown.md, cleaned.md)."""
        doc_dir = self._doc_dir(doc_id)
        dest = doc_dir / suffix
        dest.write_text(content, encoding="utf-8")
        return str(dest.relative_to(self.base_dir))

    async def read_text(self, path: str) -> str:
        """Read text from a relative path under base_dir."""
        base = self.base_dir.resolve()
        full_path = (base / path).resolve()
        # Reject path traversal (e.g. "../../etc/passwd") that escapes base_dir.
        if not full_path.is_relative_to(base):
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return full_path.read_text(encoding="utf-8")

    async def delete_all(self, doc_id: str) -> None:
        """Remove the entire document directory."""
        doc_dir = self.base_dir / doc_id
        if doc_dir.exists():
            shutil.rmtree(doc_dir)
            logger.info("Deleted storage for document %s", doc_id)
