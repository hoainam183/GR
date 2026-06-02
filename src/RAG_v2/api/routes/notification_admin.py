"""Internal notification creation routes (admin/system use)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from api.services.notification_delivery import broadcast_user_notification
from auth.jwt_handler import get_current_user
from models.database import get_database
from models.user import UserDocument

router = APIRouter(prefix="/admin/notifications", tags=["notifications-admin"])


class NotificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    type: str = Field(default="update")
    related_doc_id: str | None = None
    topics: list[str] = Field(default_factory=list)  # target topics; empty = broadcast to all


class BroadcastNotificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    type: str = Field(default="update")
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Create notifications for users subscribed to given topics (or all users)."""
    result = await broadcast_user_notification(
        db,
        title=body.title,
        body=body.body,
        notification_type=body.type,
        related_doc_id=body.related_doc_id,
        topics=body.topics,
    )
    return result


@router.post("/broadcast", status_code=status.HTTP_201_CREATED)
async def broadcast_notification(
    body: BroadcastNotificationCreate,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Broadcast a notification to ALL users in the system."""
    result = await broadcast_user_notification(
        db,
        title=body.title,
        body=body.body,
        notification_type=body.type,
        metadata=body.metadata,
    )
    if not result["target_user_ids"]:
        return {**result, "message": "No users found"}
    return result
