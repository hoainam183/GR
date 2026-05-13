"""MongoDB document model for the ``document_chunks`` collection.

Stores individual text chunks produced by the chunking pipeline step.
Embedding vectors are NOT stored here — they live in Qdrant/ES only.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.user import PyObjectId


class DocumentChunk(BaseModel):
    """A single chunk of a processed document.

    References a parent ``DocumentRecord`` via ``document_id``.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    document_id: PyObjectId  # FK to documents collection
    chunk_index: int
    content: str
    metadata: dict = Field(default_factory=dict)

    @classmethod
    def from_mongo(cls, doc: dict[str, Any]) -> "DocumentChunk":
        """Construct from a raw MongoDB document dict."""
        return cls.model_validate(doc)
