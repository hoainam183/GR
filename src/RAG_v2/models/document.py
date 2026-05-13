"""MongoDB document model for the ``documents`` collection.

Stores metadata and status tracking for admin-uploaded documents
as they progress through the processing pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.user import PyObjectId


class AuditEntry(BaseModel):
    """Single audit log entry embedded in a DocumentRecord."""

    action: str  # upload | convert | edit_markdown | approve_markdown | ...
    user_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    details: Optional[dict] = None


class DocumentRecord(BaseModel):
    """Full representation of a document in the ``documents`` collection.

    Tracks file metadata, pipeline status, review flags, and audit history.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    # --- Identity ---
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    filename: str
    file_size: int
    file_path: str  # relative path in uploads/

    # --- Classification ---
    collection: str  # ctdt | quydinh | kehoach | stsv

    # --- Pipeline status ---
    status: str = "uploaded"
    # Values: uploaded | converting | converted | cleaning | cleaned |
    #         chunking | chunked | embedding | indexed | failed

    # --- Ownership ---
    uploaded_by: PyObjectId
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # --- Processed artifact paths ---
    markdown_path: Optional[str] = None
    cleaned_path: Optional[str] = None

    # --- Chunks ---
    chunk_count: Optional[int] = None
    chunk_ids: Optional[List[str]] = None
    chunking_strategy: Optional[str] = None

    # --- Converter ---
    converter: Optional[str] = None  # pymupdf4llm | docling

    # --- Review flags ---
    markdown_reviewed: bool = False
    cleaned_reviewed: bool = False
    chunks_reviewed: bool = False

    # --- Optional metadata overrides ---
    metadata_overrides: dict = Field(default_factory=dict)

    # --- Error tracking ---
    error_message: Optional[str] = None

    # --- Step timestamps ---
    converted_at: Optional[datetime] = None
    cleaned_at: Optional[datetime] = None
    chunked_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None

    # --- Audit log ---
    audit_log: List[AuditEntry] = Field(default_factory=list)

    @classmethod
    def from_mongo(cls, doc: dict[str, Any]) -> "DocumentRecord":
        """Construct from a raw MongoDB document dict."""
        return cls.model_validate(doc)
