"""Pydantic schemas package — all API request/response models live here.

Sub-modules
-----------
schemas.chat   — ChatRequest, ChatResponse, HealthResponse, and related types.
schemas.user   — UserCreate, UserUpdate, UserPublic, UserManualCreate,
                 UserLoginRequest, TokenResponse.

All public symbols are re-exported so callers can do either::

    from schemas import ChatRequest, UserPublic
    from schemas.chat import ChatRequest
    from schemas.user import UserPublic
"""

from schemas.chat import (  # noqa: F401
    ChatRequest,
    ChatResponse,
    CollectionScore,
    HealthResponse,
    HistoryMessage,
    RetrievedDocument,
)
from schemas.user import (  # noqa: F401
    TokenResponse,
    UserCreate,
    UserLoginRequest,
    UserManualCreate,
    UserPublic,
    UserUpdate,
)

__all__ = [
    # chat
    "ChatRequest",
    "ChatResponse",
    "CollectionScore",
    "HealthResponse",
    "HistoryMessage",
    "RetrievedDocument",
    # user
    "TokenResponse",
    "UserCreate",
    "UserLoginRequest",
    "UserManualCreate",
    "UserPublic",
    "UserUpdate",
]
