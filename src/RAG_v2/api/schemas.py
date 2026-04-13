"""Backward-compatible re-export shim.

All chat/health API schemas have moved to ``schemas.chat``.
This module re-exports them so existing imports continue to work.

    from api.schemas import ChatRequest  # still valid
"""

from schemas.chat import (  # noqa: F401
    ChatRequest,
    ChatResponse,
    CollectionScore,
    HealthResponse,
    HistoryMessage,
    RetrievedDocument,
    UserContext,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "CollectionScore",
    "HealthResponse",
    "HistoryMessage",
    "RetrievedDocument",
    "UserContext",
]

