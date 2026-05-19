"""Pydantic schemas for mobile-specific feature APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class BookmarkCreate(BaseModel):
    session_id: str
    turn_id: int = Field(..., ge=1)
    folder: str = Field(default="Chung", min_length=1, max_length=80)
    note: Optional[str] = Field(default=None, max_length=1000)


class BookmarkUpdate(BaseModel):
    folder: Optional[str] = Field(default=None, min_length=1, max_length=80)
    note: Optional[str] = Field(default=None, max_length=1000)


class BookmarkFolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class BookmarkFolderRename(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=80)


class FeedbackCreate(BaseModel):
    session_id: str
    turn_id: int = Field(..., ge=1)
    rating: Literal["up", "down"]
    category: Optional[Literal["wrong", "incomplete", "outdated"]] = None
    comment: Optional[str] = Field(default=None, max_length=1000)


class NotificationSubscribe(BaseModel):
    topics: list[str] = Field(default_factory=list)
    expo_push_token: str = Field(..., min_length=1)


class NotificationUnsubscribe(BaseModel):
    expo_push_token: str = Field(..., min_length=1)
    topics: list[str] = Field(default_factory=list)


class LookupDocument(BaseModel):
    title: str
    summary: str
    collection: str | None = None
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationCreateInternal(BaseModel):
    user_id: str
    title: str
    body: str
    type: str = "update"
    related_doc_id: Optional[str] = None
    read: bool = False
    created_at: datetime
