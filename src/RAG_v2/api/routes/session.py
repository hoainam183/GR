"""Session API routes — create and retrieve chat sessions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["session"])


# ------------------------------------------------------------------
# POST /session — create a new session
# ------------------------------------------------------------------


@router.post("")
async def create_session(request: Request):
    """Create a new empty chat session."""
    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    if mongo_logger is None:
        raise HTTPException(status_code=503, detail="MongoDB logging disabled")

    session_id = mongo_logger.new_session()
    session = mongo_logger.get_session(session_id)
    return {
        "session_id": session_id,
        "created_at": session["created_at"] if session else None,
    }


# ------------------------------------------------------------------
# GET /session/{session_id} — get session with turns
# ------------------------------------------------------------------


@router.get("/{session_id}")
async def get_session(request: Request, session_id: str):
    """Return the full session document including all turns."""
    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    if mongo_logger is None:
        raise HTTPException(status_code=503, detail="MongoDB logging disabled")

    session = mongo_logger.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session
