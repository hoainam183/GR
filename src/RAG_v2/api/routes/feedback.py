"""Feedback API routes for answer quality signals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.jwt_handler import get_current_user
from models.database import (
    FEEDBACK_COLLECTION,
    SESSIONS_COLLECTION,
    TURNS_COLLECTION,
    get_database,
)
from models.user import UserDocument
from schemas.mobile import FeedbackCreate

router = APIRouter(tags=["feedback"])


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def create_feedback(
    body: FeedbackCreate,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Persist one feedback record per user/session/turn."""
    user_id = str(current_user.id)
    session = await db[SESSIONS_COLLECTION].find_one({"session_id": body.session_id})
    if session is None or session.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    turn = await db[TURNS_COLLECTION].find_one(
        {"session_id": body.session_id, "turn_id": body.turn_id}
    )
    if turn is None:
        raise HTTPException(status_code=404, detail="Turn not found")

    now = datetime.now(timezone.utc)
    await db[FEEDBACK_COLLECTION].update_one(
        {"user_id": user_id, "session_id": body.session_id, "turn_id": body.turn_id},
        {
            "$set": {
                "rating": body.rating,
                "category": body.category,
                "comment": body.comment,
                "question": turn.get("question", ""),
                "answer_snapshot": turn.get("answer", ""),
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "session_id": body.session_id,
                "turn_id": body.turn_id,
                "created_at": now,
            },
        },
        upsert=True,
    )
    doc = await db[FEEDBACK_COLLECTION].find_one(
        {"user_id": user_id, "session_id": body.session_id, "turn_id": body.turn_id}
    )
    if doc is None:
        raise HTTPException(status_code=500, detail="Failed to create feedback")
    return {"feedback_id": str(doc["_id"])}
