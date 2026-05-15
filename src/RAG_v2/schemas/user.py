"""Pydantic schemas for user-related API endpoints.

Separation of concerns
----------------------
``models.user``   — MongoDB document models (``UserDocument``).
``schemas.user``  — API request/response models (this module).

All user schemas that appear in API request bodies or response payloads
are defined here.  ``PyObjectId`` is imported from ``models.user`` because
it is tightly coupled to the MongoDB ObjectId type.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.user import PyObjectId

# Only @sis.hust.edu.vn addresses are accepted for OAuth-created accounts.
_HUST_EMAIL_DOMAIN = "@sis.hust.edu.vn"


# ═══════════════════════════════════════════════════════════════════════════════
# UserCreate — input after Microsoft OAuth login
# ═══════════════════════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    """Input model for creating a new user document after a successful OAuth login.

    Fields are typically pre-populated by ``parse_hust_email()`` and may be
    overridden before submission.
    """

    model_config = ConfigDict(populate_by_name=True)

    microsoft_id: str
    email: str
    full_name: str
    student_id: str
    cohort: str
    major: str = "CNTT Việt Nhật"
    avatar_url: Optional[str] = None

    @field_validator("email", mode="after")
    @classmethod
    def email_must_be_hust(cls, value: str) -> str:
        if not value.lower().endswith(_HUST_EMAIL_DOMAIN):
            raise ValueError(
                f"Email must end with {_HUST_EMAIL_DOMAIN!r}, got {value!r}"
            )
        return value.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# UserUpdate — all-Optional PATCH body
# ═══════════════════════════════════════════════════════════════════════════════

class UserUpdate(BaseModel):
    """All fields are optional so callers can send partial updates.

    Only fields present in the request body are written to MongoDB via
    ``$set``.  The ``updated_at`` timestamp is injected server-side.
    """

    model_config = ConfigDict(populate_by_name=True)

    full_name: Optional[str] = None
    student_id: Optional[str] = None
    cohort: Optional[str] = None
    major: Optional[str] = None
    major_code: Optional[str] = None
    avatar_url: Optional[str] = None
    is_profile_complete: Optional[bool] = None
    is_active: Optional[bool] = None

    def to_update_dict(self) -> dict[str, Any]:
        """Return only the explicitly-set fields as a ``$set``-ready dict.

        Also injects the server-side ``updated_at`` timestamp.
        """
        data = self.model_dump(exclude_none=True)
        data["updated_at"] = datetime.now(timezone.utc)
        return data


# ═══════════════════════════════════════════════════════════════════════════════
# UserPublic — safe API response (no sensitive fields)
# ═══════════════════════════════════════════════════════════════════════════════

class UserPublic(BaseModel):
    """User representation returned to API clients.

    ``microsoft_id`` and ``password_hash`` are deliberately excluded.
    ``id`` is serialised as a plain string.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    email: Optional[str] = None
    username: Optional[str] = None
    full_name: str
    student_id: str
    cohort: str
    major: str
    major_code: str = ""
    role: str = "student"
    avatar_url: Optional[str] = None
    is_profile_complete: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime

    @classmethod
    def from_document(cls, doc: dict[str, Any]) -> "UserPublic":
        """Construct a :class:`UserPublic` from a raw MongoDB document dict."""
        return cls.model_validate(doc)


# ═══════════════════════════════════════════════════════════════════════════════
# Manual auth schemas — username/password registration and login
# ═══════════════════════════════════════════════════════════════════════════════

class UserManualCreate(BaseModel):
    """Request body for ``POST /auth/register`` (manual sign-up)."""

    model_config = ConfigDict(populate_by_name=True)

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    cohort: str = Field(..., min_length=1)
    major: str = Field(..., min_length=1)
    major_code: str = Field(default="")


class UserLoginRequest(BaseModel):
    """Request body for ``POST /auth/login``."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Response body for ``POST /auth/login``."""

    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ═══════════════════════════════════════════════════════════════════════════════
# AdminCreate — superadmin creates admin accounts
# ═══════════════════════════════════════════════════════════════════════════════

class AdminCreateRequest(BaseModel):
    """Request body for ``POST /auth/admin/create`` (superadmin only)."""

    model_config = ConfigDict(populate_by_name=True)

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1)
    student_id: str = Field(default="admin")
    cohort: str = Field(default="N/A")
    major: str = Field(default="N/A")
    major_code: str = Field(default="")
