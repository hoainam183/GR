"""Pydantic schemas for document upload API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Valid collection names
VALID_COLLECTIONS = {"ctdt", "quydinh", "kehoach", "stsv", "test"}

# Valid converter names
VALID_CONVERTERS = {"pymupdf4llm", "docling"}

# Collection → suggested chunker mapping
COLLECTION_CHUNKER_MAP: dict[str, str] = {
    "quydinh": "recursive",
    "ctdt": "recursive",
    "kehoach": "kehoach",
    "stsv": "stsv",
    "test": "recursive",
}

# Converter metadata for listing
CONVERTER_INFO = [
    {
        "key": "pymupdf4llm",
        "label": "PyMuPDF4LLM",
        "description": "Chuyển đổi nhanh, tốt cho tài liệu đơn giản",
    },
    {
        "key": "docling",
        "label": "Docling (IBM)",
        "description": "Xử lý tốt bảng và cấu trúc phức tạp",
    },
]

# Chunker metadata for listing
CHUNKER_INFO = [
    {
        "key": "recursive",
        "label": "Recursive",
        "description": "Tách theo cấu trúc heading (H2/H3), phù hợp CTDT",
        "collections": ["ctdt", "quydinh", "kehoach", "stsv", "test"],
    },
    {
        "key": "hierarchical",
        "label": "Hierarchical Legal",
        "description": "Tách theo Điều/Chương cho văn bản pháp quy (PyMuPDF)",
        "collections": ["ctdt", "quydinh", "test"],
    },
    {
        "key": "olmocr",
        "label": "OLM OCR Legal",
        "description": "Cho văn bản OCR không có markdown heading",
        "collections": ["quydinh", "test"],
    },
]


class DocumentUploadRequest(BaseModel):
    """Form data accompanying a file upload."""

    collection: str
    chunking_strategy: Optional[str] = None
    metadata_overrides: Optional[Dict[str, Any]] = None

    @field_validator("collection")
    @classmethod
    def validate_collection(cls, v: str) -> str:
        if v not in VALID_COLLECTIONS:
            raise ValueError(
                f"Invalid collection {v!r}. Must be one of: {sorted(VALID_COLLECTIONS)}"
            )
        return v


class DocumentDetail(BaseModel):
    """Single document detail returned by the API."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    filename: str
    file_size: int
    status: str
    collection: str
    chunking_strategy: Optional[str] = None
    converter: Optional[str] = None
    chunk_count: Optional[int] = None
    markdown_reviewed: bool = False
    cleaned_reviewed: bool = False
    chunks_reviewed: bool = False
    metadata_overrides: dict = Field(default_factory=dict)
    uploaded_by: str
    uploaded_at: datetime
    error_message: Optional[str] = None
    converted_at: Optional[datetime] = None
    cleaned_at: Optional[datetime] = None
    chunked_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None

    @classmethod
    def from_document(cls, doc: dict) -> "DocumentDetail":
        """Build from a MongoDB document dict."""
        return cls(
            id=str(doc["_id"]),
            filename=doc["filename"],
            file_size=doc.get("file_size", 0),
            status=doc["status"],
            collection=doc["collection"],
            chunking_strategy=doc.get("chunking_strategy"),
            converter=doc.get("converter"),
            chunk_count=doc.get("chunk_count"),
            markdown_reviewed=doc.get("markdown_reviewed", False),
            cleaned_reviewed=doc.get("cleaned_reviewed", False),
            chunks_reviewed=doc.get("chunks_reviewed", False),
            metadata_overrides=doc.get("metadata_overrides", {}),
            uploaded_by=str(doc["uploaded_by"]),
            uploaded_at=doc["uploaded_at"],
            error_message=doc.get("error_message"),
            converted_at=doc.get("converted_at"),
            cleaned_at=doc.get("cleaned_at"),
            chunked_at=doc.get("chunked_at"),
            indexed_at=doc.get("indexed_at"),
        )


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    documents: List[DocumentDetail]
    total: int
    page: int
    limit: int


class ChunkPreview(BaseModel):
    """Single chunk preview for the review UI."""

    chunk_id: str
    chunk_index: int
    content: str
    metadata: dict = Field(default_factory=dict)


class ChunksResponse(BaseModel):
    """Paginated chunk listing with stats."""

    chunks: List[ChunkPreview]
    total: int
    page: int
    limit: int
    strategy: str
    stats: dict = Field(default_factory=dict)  # avg_size, min, max, etc.


class MarkdownContent(BaseModel):
    """Markdown content for review/edit."""

    content: str


class CleanedContent(BaseModel):
    """Cleaned markdown content for review/edit."""

    content: str
