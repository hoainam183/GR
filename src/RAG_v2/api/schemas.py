"""Pydantic schemas for API request / response models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Request models
# ═══════════════════════════════════════════════════════════════════════════════


class HistoryMessage(BaseModel):
    """A single message in the chat history."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Body for ``POST /chat`` and ``POST /chat/stream``."""

    question: str = Field(..., min_length=1, max_length=4096)
    top_k: int = Field(default=5, ge=1, le=50)
    history: Optional[List[HistoryMessage]] = None
    session_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Response models
# ═══════════════════════════════════════════════════════════════════════════════


class RetrievedDocument(BaseModel):
    """A single retrieved source document."""

    rank: int
    content: str
    score: float
    metadata: Dict[str, Any]


class ChatResponse(BaseModel):
    """Response body for ``POST /chat``."""

    question: str
    answer: str
    retrieved_documents: List[RetrievedDocument]
    num_documents: int
    model_name: str
    intent: str
    target_collections: Optional[List[str]] = None
    reflected_query: Optional[str] = None
    session_id: str


class HealthResponse(BaseModel):
    """Response body for ``GET /health``."""

    status: str
    rag_initialized: bool
