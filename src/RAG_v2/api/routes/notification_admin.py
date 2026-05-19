"""Internal notification creation routes (admin/system use)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from auth.jwt_handler import get_current_user
from models.database import (
    NOTIFICATIONS_COLLECTION,
    NOTIFICATION_SUBSCRIPTIONS_COLLECTION,
    get_database,
)
from models.user import UserDocument

router = APIRouter(prefix="/admin/notifications", tags=["notifications-admin"])


class NotificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    type: str = Field(default="update")
    related_doc_id: str | None = None
    topics: list[str] = Field(default_factory=list)  # target topics; empty = broadcast to all


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Create notifications for users subscribed to given topics (or all users)."""
    # For now, any authenticated user can create (TODO: add admin role check)
    now = datetime.now(timezone.utc)

    # Find target user_ids based on topics
    if body.topics:
        # Find subscriptions matching any of the topics
        subs_cursor = db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].find(
            {"topics": {"$in": body.topics}},
            {"user_id": 1},
        )
        user_ids = list({doc["user_id"] async for doc in subs_cursor})
    else:
        # Broadcast: get all unique user_ids from subscriptions
        subs_cursor = db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].find(
            {}, {"user_id": 1}
        )
        user_ids = list({doc["user_id"] async for doc in subs_cursor})

    if not user_ids:
        return {"created_count": 0, "target_user_ids": []}

    # Create one notification per user
    docs = [
        {
            "user_id": uid,
            "title": body.title,
            "body": body.body,
            "type": body.type,
            "related_doc_id": body.related_doc_id,
            "topics": body.topics,
            "read": False,
            "created_at": now,
        }
        for uid in user_ids
    ]
    result = await db[NOTIFICATIONS_COLLECTION].insert_many(docs)
    return {"created_count": len(result.inserted_ids), "target_user_ids": user_ids}
