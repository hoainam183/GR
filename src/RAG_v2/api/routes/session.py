"""Session API routes — create and retrieve chat sessions."""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from auth.jwt_handler import get_current_user, get_optional_current_user
from models.user import UserDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["session"])


class SessionCreateRequest(BaseModel):
    """Optional legacy body for creating a session with a supplied user id."""

    user_id: Optional[str] = None


# ------------------------------------------------------------------
# POST /session — create a new session
# ------------------------------------------------------------------


@router.post("")
async def create_session(
    request: Request,
    body: SessionCreateRequest | None = Body(default=None),
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
):
    """Create a new empty chat session."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    user_id = str(current_user.id) if current_user is not None else body.user_id if body else None

    if redis_session is not None:
        session_id = redis_session.new_session(user_id=user_id)
        session = redis_session.get_session(session_id)
        return {
            "session_id": session_id,
            "created_at": session["created_at"] if session else None,
        }

    if mongo_logger is None:
        raise HTTPException(status_code=503, detail="No session store available")

    session_id = mongo_logger.new_session(user_id=user_id)
    session = mongo_logger.get_session(session_id)
    return {
        "session_id": session_id,
        "created_at": session["created_at"] if session else None,
    }


# ------------------------------------------------------------------
# GET /session/{session_id} — get session metadata + turns
# ------------------------------------------------------------------


@router.get("/{session_id}")
async def get_session(
    request: Request,
    session_id: str,
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
):
    """Return session metadata with its turns (from turns collection)."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    session = None
    if redis_session is not None:
        session = redis_session.get_session(session_id)

    if session is None and mongo_logger is not None:
        session = mongo_logger.get_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if current_user is not None and session.get("user_id") not in (None, str(current_user.id)):
        raise HTTPException(status_code=404, detail="Session not found")

    # Turns are always stored in MongoDB
    if mongo_logger is not None:
        turns = mongo_logger.get_turns(session_id)
        session["turns"] = turns
    else:
        session["turns"] = []

    return session


# ------------------------------------------------------------------
# GET /sessions?user_id=... — list sessions for a user
# ------------------------------------------------------------------


@router.get("s", summary="List sessions for a user")
async def list_sessions(
    request: Request,
    user_id: str = Query(..., description="User ID to filter sessions"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return sessions owned by *user_id*, newest first."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    if redis_session is not None:
        sessions = redis_session.list_sessions(user_id=user_id, limit=limit)
        return {"sessions": sessions, "count": len(sessions)}

    if mongo_logger is None:
        raise HTTPException(status_code=503, detail="No session store available")

    sessions = mongo_logger.list_sessions(user_id=user_id, limit=limit)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("s/me", summary="List sessions for the authenticated user")
async def list_my_sessions(
    request: Request,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
):
    """Return sessions owned by the current authenticated user."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    user_id = str(current_user.id)

    if redis_session is not None:
        sessions = redis_session.list_sessions(user_id=user_id, limit=limit)
        return {"sessions": sessions, "count": len(sessions)}

    if mongo_logger is None:
        raise HTTPException(status_code=503, detail="No session store available")

    sessions = mongo_logger.list_sessions(user_id=user_id, limit=limit)
    return {"sessions": sessions, "count": len(sessions)}
