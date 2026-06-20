"""MongoDB models for staged crawler review runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.user import PyObjectId

CRAWLER_STATUS_PENDING_REVIEW = "pending_review"
CRAWLER_STATUS_INDEXING = "indexing"
CRAWLER_STATUS_INDEXED = "indexed"
CRAWLER_STATUS_INDEX_FAILED = "index_failed"

CRAWLER_EDITABLE_STATUSES = {
    CRAWLER_STATUS_PENDING_REVIEW,
    CRAWLER_STATUS_INDEX_FAILED,
}
CRAWLER_INDEXABLE_STATUSES = {
    CRAWLER_STATUS_PENDING_REVIEW,
    CRAWLER_STATUS_INDEX_FAILED,
}
CRAWLER_DELETABLE_STATUSES = {
    CRAWLER_STATUS_PENDING_REVIEW,
}


def crawler_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CrawlerRun(BaseModel):
    """A staged crawler run waiting for admin review/index approval."""

    model_config = ConfigDict(
        populate_by_name=True, arbitrary_types_allowed=True
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    run_id: str
    pipeline: str
    collection: str
    status: str = CRAWLER_STATUS_PENDING_REVIEW
    source_label: str
    output_file: str
    chunks_file: str
    new_articles: int = 0
    new_chunks: int = 0
    indexed: int = 0
    expired_removed: int = 0
    created_at: datetime = Field(default_factory=crawler_utc_now)
    updated_at: datetime = Field(default_factory=crawler_utc_now)
    indexed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    summary: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_mongo(cls, doc: dict[str, Any]) -> "CrawlerRun":
        return cls.model_validate(doc)


class CrawlerChunk(BaseModel):
    """A single staged crawler chunk whose content can be reviewed."""

    model_config = ConfigDict(
        populate_by_name=True, arbitrary_types_allowed=True
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    run_id: str
    chunk_id: str
    chunk_index: int
    content: str
    original_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    edited: bool = False
    index_status: str = "pending"
    created_at: datetime = Field(default_factory=crawler_utc_now)
    updated_at: datetime = Field(default_factory=crawler_utc_now)

    @classmethod
    def from_mongo(cls, doc: dict[str, Any]) -> "CrawlerChunk":
        return cls.model_validate(doc)
