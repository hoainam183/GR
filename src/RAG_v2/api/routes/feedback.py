"""Feedback API routes for answer quality signals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.jwt_handler import get_current_user
from auth.rbac import require_admin
from models.database import (
    FEEDBACK_COLLECTION,
    SESSIONS_COLLECTION,
    TURNS_COLLECTION,
    get_database,
)
from models.user import UserDocument
from schemas.mobile import FeedbackCreate

router = APIRouter(tags=["feedback"])


def _serialize_feedback(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "session_id": doc["session_id"],
        "turn_id": doc["turn_id"],
        "rating": doc.get("rating"),
        "category": doc.get("category"),
        "comment": doc.get("comment"),
        "question": doc.get("question", ""),
        "answer_snapshot": doc.get("answer_snapshot", ""),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


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
    return {"feedback_id": str(doc["_id"]), "feedback": _serialize_feedback(doc)}


@router.get("/feedback")
async def get_feedback(
    session_id: Annotated[str, Query()],
    turn_id: Annotated[int, Query(ge=1)],
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Retrieve feedback for a specific session/turn belonging to current user."""
    user_id = str(current_user.id)
    doc = await db[FEEDBACK_COLLECTION].find_one(
        {"user_id": user_id, "session_id": session_id, "turn_id": turn_id}
    )
    if doc is None:
        return {"feedback": None}
    return {"feedback": _serialize_feedback(doc)}


@router.get("/feedback/list")
async def list_feedback(
    _admin: Annotated[UserDocument, Depends(require_admin)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    rating: Literal["up", "down", "all"] | None = Query(default=None),
    category: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Return paginated feedback records (admin)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict[str, Any] = {"created_at": {"$gte": since}}
    if rating and rating != "all":
        query["rating"] = rating
    if category:
        query["category"] = category

    skip = (page - 1) * limit
    total = await db[FEEDBACK_COLLECTION].count_documents(query)
    cursor = (
        db[FEEDBACK_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    feedbacks = [_serialize_feedback(doc) async for doc in cursor]
    return {"feedbacks": feedbacks, "total": total, "page": page, "limit": limit}


@router.get("/feedback/stats")
async def get_feedback_stats(
    _admin: Annotated[UserDocument, Depends(require_admin)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Return aggregated feedback stats (admin-only in future)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline: list[dict[str, Any]] = [
        {"$match": {"created_at": {"$gte": since}}},
        {
            "$facet": {
                "totals": [
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": 1},
                            "up": {
                                "$sum": {"$cond": [{"$eq": ["$rating", "up"]}, 1, 0]}
                            },
                            "down": {
                                "$sum": {"$cond": [{"$eq": ["$rating", "down"]}, 1, 0]}
                            },
                        }
                    }
                ],
                "by_category": [
                    {"$match": {"category": {"$ne": None}}},
                    {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                ],
            }
        },
    ]

    results = await db[FEEDBACK_COLLECTION].aggregate(pipeline).to_list(length=1)
    result = results[0] if results else {"totals": [], "by_category": []}

    totals = result["totals"][0] if result["totals"] else {"total": 0, "up": 0, "down": 0}
    by_category = {item["_id"]: item["count"] for item in result["by_category"]}

    return {
        "stats": {
            "total": totals["total"],
            "up": totals["up"],
            "down": totals["down"],
            "by_category": by_category,
            "recent_days": days,
        }
    }
