"""Notification API routes for the mobile app."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.jwt_handler import get_current_user
from models.database import (
    NOTIFICATION_SUBSCRIPTIONS_COLLECTION,
    NOTIFICATIONS_COLLECTION,
    get_database,
)
from models.user import UserDocument
from schemas.mobile import NotificationSubscribe, NotificationUnsubscribe

router = APIRouter(tags=["notifications"])


def _serialize_notification(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", ""),
        "body": doc.get("body", ""),
        "type": doc.get("type", "update"),
        "related_doc_id": doc.get("related_doc_id"),
        "read": bool(doc.get("read", False)),
        "created_at": doc.get("created_at"),
        "metadata": doc.get("metadata"),
    }


@router.get("/notifications")
async def list_notifications(
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    """Return notifications for the current user."""
    query: dict[str, Any] = {"user_id": str(current_user.id)}
    if unread_only:
        query["read"] = False
    skip = (page - 1) * limit
    total = await db[NOTIFICATIONS_COLLECTION].count_documents(query)
    cursor = (
        db[NOTIFICATIONS_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    notifications = [_serialize_notification(doc) async for doc in cursor]
    return {"notifications": notifications, "total": total, "page": page}


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, int]:
    """Return the count of unread notifications for the current user."""
    count = await db[NOTIFICATIONS_COLLECTION].count_documents(
        {"user_id": str(current_user.id), "read": False}
    )
    return {"unread_count": count}


@router.put("/notifications/read-all")
async def mark_all_read(
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Mark all unread notifications for the current user as read."""
    now = datetime.now(timezone.utc)
    result = await db[NOTIFICATIONS_COLLECTION].update_many(
        {"user_id": str(current_user.id), "read": False},
        {"$set": {"read": True, "read_at": now}},
    )
    return {"status": "ok", "updated_count": result.modified_count}


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, str]:
    """Mark one notification as read."""
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    result = await db[NOTIFICATIONS_COLLECTION].update_one(
        {"_id": ObjectId(notification_id), "user_id": str(current_user.id)},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read"}


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, str]:
    """Delete a specific notification owned by the current user."""
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    result = await db[NOTIFICATIONS_COLLECTION].delete_one(
        {"_id": ObjectId(notification_id), "user_id": str(current_user.id)},
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "deleted"}


@router.post("/notifications/subscribe")
async def subscribe_notifications(
    body: NotificationSubscribe,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Store an Expo push token and topic subscriptions for the current user."""
    user_id = str(current_user.id)
    now = datetime.now(timezone.utc)
    topics = sorted({topic.strip() for topic in body.topics if topic.strip()})
    await db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].update_one(
        {"user_id": user_id, "expo_push_token": body.expo_push_token},
        {
            "$set": {
                "topics": topics,
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "expo_push_token": body.expo_push_token,
                "created_at": now,
            },
        },
        upsert=True,
    )
    return {"subscribed_topics": topics}


@router.post("/notifications/unsubscribe")
async def unsubscribe_notifications(
    body: NotificationUnsubscribe,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Remove topics from a subscription or delete it entirely."""
    user_id = str(current_user.id)
    filter_doc = {"user_id": user_id, "expo_push_token": body.expo_push_token}

    if not body.topics:
        # No topics specified — delete entire subscription
        await db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].delete_one(filter_doc)
        return {"remaining_topics": []}

    # Remove specified topics from the subscription
    topics_to_remove = [t.strip() for t in body.topics if t.strip()]
    await db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].update_one(
        filter_doc,
        {"$pull": {"topics": {"$in": topics_to_remove}}},
    )
    # Fetch updated document to return remaining topics
    doc = await db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].find_one(filter_doc)
    remaining = doc.get("topics", []) if doc else []
    return {"remaining_topics": remaining}
