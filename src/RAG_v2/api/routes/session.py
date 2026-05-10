"""Session API routes — create and retrieve chat sessions."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["session"])


# ------------------------------------------------------------------
# POST /session — create a new session
# ------------------------------------------------------------------


@router.post("")
async def create_session(request: Request):
    """Create a new empty chat session."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    if redis_session is not None:
        session_id = redis_session.new_session()
        session = redis_session.get_session(session_id)
        return {
            "session_id": session_id,
            "created_at": session["created_at"] if session else None,
        }

    if mongo_logger is None:
        raise HTTPException(status_code=503, detail="No session store available")

    session_id = mongo_logger.new_session()
    session = mongo_logger.get_session(session_id)
    return {
        "session_id": session_id,
        "created_at": session["created_at"] if session else None,
    }


# ------------------------------------------------------------------
# GET /session/{session_id} — get session metadata + turns
# ------------------------------------------------------------------


@router.get("/{session_id}")
async def get_session(request: Request, session_id: str):
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
