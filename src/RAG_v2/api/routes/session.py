"""Session API routes — create and retrieve chat sessions."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Dict, Iterable, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator

from auth.jwt_handler import get_current_user, get_optional_current_user
from models.user import UserDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["session"])


class SessionCreateRequest(BaseModel):
    """Optional legacy body for creating a session with a supplied user id."""

    user_id: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    """Editable session metadata."""

    title: str

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Title must not be empty.")
        return title[:120]


def _user_owner_aliases(user: UserDocument) -> list[str]:
    """Return all historic identifiers that may own this user's sessions."""
    raw_values = [
        getattr(user, "id", None),
        getattr(user, "email", None),
        getattr(user, "username", None),
        getattr(user, "student_id", None),
    ]
    aliases: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        if value is None:
            continue
        alias = str(value).strip()
        if alias and alias not in seen:
            aliases.append(alias)
            seen.add(alias)
    return aliases


def _can_read_session(session: Dict[str, Any], user: UserDocument | None) -> bool:
    """Legacy sessions without an owner remain readable."""
    if user is None:
        return True
    owner_id = session.get("user_id")
    return owner_id in (None, *_user_owner_aliases(user))


def _assert_session_owned(session: Dict[str, Any], user: UserDocument) -> str:
    """Require an explicit owner match for destructive metadata actions."""
    owner_id = session.get("user_id")
    if owner_id not in _user_owner_aliases(user):
        raise HTTPException(status_code=404, detail="Session not found")
    return str(owner_id)


def _parse_updated_at(session: Dict[str, Any]) -> float:
    value = session.get("updated_at")
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _merge_sessions(
    session_groups: Iterable[Iterable[Dict[str, Any]]],
    limit: int,
) -> list[Dict[str, Any]]:
    merged: dict[str, Dict[str, Any]] = {}
    for sessions in session_groups:
        for session in sessions:
            session_id = session.get("session_id")
            if not session_id:
                continue
            existing = merged.get(str(session_id))
            if existing is None or _parse_updated_at(session) > _parse_updated_at(existing):
                merged[str(session_id)] = session
    return sorted(merged.values(), key=_parse_updated_at, reverse=True)[:limit]


def _get_session_from_stores(
    redis_session: Any,
    mongo_logger: Any,
    session_id: str,
) -> Dict[str, Any] | None:
    session = None
    if redis_session is not None:
        session = redis_session.get_session(session_id)
    if session is None and mongo_logger is not None:
        session = mongo_logger.get_session(session_id)
    return session


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
    if not _can_read_session(session, current_user):
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
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    user_id: str = Query(..., description="User ID to filter sessions"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return sessions owned by *user_id*, newest first.

    The caller may only list their own sessions: ``user_id`` must match one of
    the authenticated user's identifiers (id / email / username / student_id).
    This prevents an IDOR where any caller could read another user's sessions
    (and the question titles within) by guessing a user id.
    """
    if user_id not in _user_owner_aliases(current_user):
        raise HTTPException(
            status_code=403,
            detail="You can only list your own sessions.",
        )

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
    owner_aliases = _user_owner_aliases(current_user)

    if redis_session is not None:
        sessions = _merge_sessions(
            (
                redis_session.list_sessions(user_id=owner_id, limit=limit)
                for owner_id in owner_aliases
            ),
            limit,
        )
        return {"sessions": sessions, "count": len(sessions)}

    if mongo_logger is None:
        raise HTTPException(status_code=503, detail="No session store available")

    sessions = _merge_sessions(
        (
            mongo_logger.list_sessions(user_id=owner_id, limit=limit)
            for owner_id in owner_aliases
        ),
        limit,
    )
    return {"sessions": sessions, "count": len(sessions)}


@router.delete("/{session_id}", summary="Delete an authenticated user's session")
async def delete_session(
    request: Request,
    session_id: str,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
):
    """Delete a session and all its associated data."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    session = _get_session_from_stores(redis_session, mongo_logger, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    owner_id = _assert_session_owned(session, current_user)

    if redis_session is not None:
        deleted = redis_session.delete_session(session_id, user_id=owner_id)
    elif mongo_logger is not None:
        deleted = mongo_logger.delete_session(session_id)
    else:
        raise HTTPException(status_code=503, detail="No session store available")

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id}


@router.patch("/{session_id}", summary="Update an authenticated user's session")
async def update_session(
    request: Request,
    session_id: str,
    body: SessionUpdateRequest,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
):
    """Update session metadata."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    session = _get_session_from_stores(redis_session, mongo_logger, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_session_owned(session, current_user)

    if redis_session is not None:
        updated = redis_session.update_session_title(session_id, body.title)
    elif mongo_logger is not None:
        updated = mongo_logger.update_session_title(session_id, body.title)
    else:
        raise HTTPException(status_code=503, detail="No session store available")

    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"updated": True, "session_id": session_id, "title": body.title}
