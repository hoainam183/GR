"""MongoDB document model for the ``users`` collection.

This module contains only the database-layer representation of a user
document.  All API request/response schemas live in ``schemas.user``.

Exported symbols
----------------
PyObjectId   — Pydantic v2 annotation that validates/serialises ObjectIds.
UserDocument — Full document as stored in the ``users`` collection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════════════════
# PyObjectId helper
# ═══════════════════════════════════════════════════════════════════════════════

class PyObjectId(str):
    """A str subclass that validates and serialises MongoDB ObjectIds.

    Works as a Pydantic v2 annotation::

        id: PyObjectId = Field(default_factory=lambda: str(ObjectId()))
    """

    @classmethod
    def __get_validators__(cls):  # noqa: D401 — pydantic v1 compat shim
        yield cls.validate

    @classmethod
    def validate(cls, value: Any, _info: Any = None) -> "PyObjectId":
        if isinstance(value, ObjectId):
            return cls(str(value))
        if isinstance(value, str) and ObjectId.is_valid(value):
            return cls(value)
        raise ValueError(f"Invalid ObjectId: {value!r}")

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any):
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.to_string_ser_schema(),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# UserDocument — full MongoDB document
# ═══════════════════════════════════════════════════════════════════════════════

class UserDocument(BaseModel):
    """Full representation of a document in the ``users`` collection.

    The ``id`` field maps to MongoDB's ``_id`` (ObjectId serialised as str).
    All timestamps are timezone-aware UTC datetimes.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    # --- Identity ---
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    microsoft_id: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    password_hash: Optional[str] = Field(default=None)

    # --- Contact ---
    email: Optional[str] = Field(default=None)

    # --- Profile ---
    full_name: str
    student_id: str
    cohort: str
    major: str = "CNTT Việt Nhật"
    major_code: str = ""
    avatar_url: Optional[str] = Field(default=None)

    # --- Role ---
    role: str = Field(default="student", description="student | admin")

    # --- Status ---
    is_profile_complete: bool = False
    is_active: bool = True

    # --- Timestamps (UTC) ---
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



