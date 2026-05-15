"""Bookmark API routes for mobile saved answers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.jwt_handler import get_current_user
from models.database import (
    BOOKMARK_FOLDERS_COLLECTION,
    BOOKMARKS_COLLECTION,
    SESSIONS_COLLECTION,
    TURNS_COLLECTION,
    get_database,
)
from models.user import UserDocument
from schemas.mobile import BookmarkCreate, BookmarkFolderCreate

router = APIRouter(tags=["bookmarks"])


def _serialize_bookmark(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "session_id": doc["session_id"],
        "turn_id": doc["turn_id"],
        "question": doc.get("question", ""),
        "answer_preview": doc.get("answer_preview", ""),
        "answer_snapshot": doc.get("answer_snapshot", ""),
        "sources_snapshot": doc.get("sources_snapshot", []),
        "folder": doc.get("folder") or "Chung",
        "note": doc.get("note"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def _get_owned_turn(
    db: AsyncIOMotorDatabase,
    *,
    user_id: str,
    session_id: str,
    turn_id: int,
) -> dict[str, Any]:
    session = await db[SESSIONS_COLLECTION].find_one({"session_id": session_id})
    if session is None or session.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    turn = await db[TURNS_COLLECTION].find_one(
        {"session_id": session_id, "turn_id": turn_id}
    )
    if turn is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    return turn


@router.post("/bookmarks", status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    body: BookmarkCreate,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Save a chat turn as a user-scoped bookmark."""
    user_id = str(current_user.id)
    turn = await _get_owned_turn(
        db,
        user_id=user_id,
        session_id=body.session_id,
        turn_id=body.turn_id,
    )

    now = datetime.now(timezone.utc)
    answer = str(turn.get("answer") or "")
    update = {
        "$set": {
            "folder": body.folder.strip() or "Chung",
            "note": body.note,
            "updated_at": now,
        },
        "$setOnInsert": {
            "user_id": user_id,
            "session_id": body.session_id,
            "turn_id": body.turn_id,
            "question": turn.get("question", ""),
            "answer_snapshot": answer,
            "answer_preview": answer[:240],
            "sources_snapshot": turn.get("sources", []),
            "created_at": now,
        },
    }
    await db[BOOKMARKS_COLLECTION].update_one(
        {"user_id": user_id, "session_id": body.session_id, "turn_id": body.turn_id},
        update,
        upsert=True,
    )
    doc = await db[BOOKMARKS_COLLECTION].find_one(
        {"user_id": user_id, "session_id": body.session_id, "turn_id": body.turn_id}
    )
    if doc is None:
        raise HTTPException(status_code=500, detail="Failed to create bookmark")
    return {"bookmark": _serialize_bookmark(doc)}


@router.get("/bookmarks")
async def list_bookmarks(
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    folder: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Return paginated bookmarks for the current user."""
    query: dict[str, Any] = {"user_id": str(current_user.id)}
    if folder:
        query["folder"] = folder

    skip = (page - 1) * limit
    total = await db[BOOKMARKS_COLLECTION].count_documents(query)
    cursor = (
        db[BOOKMARKS_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    bookmarks = [_serialize_bookmark(doc) async for doc in cursor]
    return {"bookmarks": bookmarks, "total": total, "page": page, "limit": limit}


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, str]:
    """Delete a bookmark owned by the current user."""
    if not ObjectId.is_valid(bookmark_id):
        raise HTTPException(status_code=404, detail="Bookmark not found")
    result = await db[BOOKMARKS_COLLECTION].delete_one(
        {"_id": ObjectId(bookmark_id), "user_id": str(current_user.id)}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {"status": "deleted"}


@router.get("/bookmark-folders")
async def list_bookmark_folders(
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Return bookmark folders and counts for the current user."""
    user_id = str(current_user.id)
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$folder", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    folders = [
        {"name": item["_id"] or "Chung", "count": item["count"]}
        async for item in db[BOOKMARKS_COLLECTION].aggregate(pipeline)
    ]

    explicit = db[BOOKMARK_FOLDERS_COLLECTION].find({"user_id": user_id})
    existing = {folder["name"] for folder in folders}
    async for item in explicit:
        if item["name"] not in existing:
            folders.append({"name": item["name"], "count": 0})
    return {"folders": folders}


@router.post("/bookmark-folders", status_code=status.HTTP_201_CREATED)
async def create_bookmark_folder(
    body: BookmarkFolderCreate,
    current_user: Annotated[UserDocument, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict[str, Any]:
    """Create an empty bookmark folder for the current user."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Folder name is required")
    await db[BOOKMARK_FOLDERS_COLLECTION].update_one(
        {"user_id": str(current_user.id), "name": name},
        {
            "$setOnInsert": {
                "user_id": str(current_user.id),
                "name": name,
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    return {"folder": {"name": name, "count": 0}}
