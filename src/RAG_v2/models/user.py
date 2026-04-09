"""Pydantic v2 models for the `users` MongoDB collection.

Four model variants follow the separation-of-concerns pattern:

    UserDocument  — full document as stored in MongoDB (includes _id as ObjectId).
    UserCreate    — validated input when a new user is inserted after OAuth login.
    UserUpdate    — all-optional form used by the profile-update endpoint.
    UserPublic    — safe response model (microsoft_id is excluded).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from bson import ObjectId
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ═══════════════════════════════════════════════════════════════════════════════
# PyObjectId helper
# ═══════════════════════════════════════════════════════════════════════════════

class PyObjectId(str):
    """A str subclass that validates and serialises MongoDB ObjectIds.

    Works as a Pydantic v2 annotation:
        id: PyObjectId = Field(default_factory=lambda: str(ObjectId()))
    """

    @classmethod
    def __get_validators__(cls):  # noqa: D401 — kept for pydantic v1 compat shim
        yield cls.validate

    @classmethod
    def validate(cls, value: Any, _info: Any = None) -> "PyObjectId":
        if isinstance(value, ObjectId):
            return cls(str(value))
        if isinstance(value, str) and ObjectId.is_valid(value):
            return cls(value)
        raise ValueError(f"Invalid ObjectId: {value!r}")

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any):  # noqa: D401
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.to_string_ser_schema(),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Shared config
# ═══════════════════════════════════════════════════════════════════════════════

_HUST_EMAIL_DOMAIN = "@sis.hust.edu.vn"


# ═══════════════════════════════════════════════════════════════════════════════
# Collection 1 — UserDocument (full MongoDB document)
# ═══════════════════════════════════════════════════════════════════════════════

class UserDocument(BaseModel):
    """Represents a document in the ``users`` collection.

    The ``id`` field maps to MongoDB's ``_id`` (ObjectId serialised as str).
    All timestamps are timezone-aware UTC datetimes.
    """

    model_config = ConfigDict(
        populate_by_name=True,          # allow alias AND field name
        arbitrary_types_allowed=True,   # required for ObjectId / PyObjectId
        json_encoders={ObjectId: str},  # fallback for ObjectId in nested dicts
    )

    # --- Identity ---
    id: Optional[PyObjectId] = Field(
        default=None,
        alias="_id",
        description="MongoDB ObjectId (auto-generated on insert)",
    )
    microsoft_id: str = Field(
        ...,
        description="Unique sub/oid claim from the Microsoft OAuth token",
    )

    # --- Contact ---
    email: str = Field(
        ...,
        description="HUST student email — must end with @sis.hust.edu.vn",
    )

    # --- Profile ---
    full_name: str = Field(
        ...,
        description="Display name parsed from the email prefix",
    )
    student_id: str = Field(
        ...,
        description="HUST student ID (e.g. '20225653')",
    )
    cohort: str = Field(
        ...,
        description="Academic cohort label (e.g. 'K67')",
    )
    major: str = Field(
        default="CNTT Việt Nhật",
        description="Student's major — defaults to 'CNTT Việt Nhật'",
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="Microsoft profile photo URL",
    )

    # --- Status flags ---
    is_profile_complete: bool = Field(
        default=False,
        description="False until the user confirms/edits the profile form",
    )
    is_active: bool = Field(
        default=True,
        description="Soft-delete flag; set to False to deactivate the account",
    )

    # --- Timestamps (UTC) ---
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of account creation",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the last profile update",
    )
    last_login_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the most recent successful login",
    )

    # --- Validators ---

    @field_validator("email", mode="after")
    @classmethod
    def email_must_be_hust(cls, value: str) -> str:
        if not value.lower().endswith(_HUST_EMAIL_DOMAIN):
            raise ValueError(
                f"Email must end with {_HUST_EMAIL_DOMAIN!r}, got {value!r}"
            )
        return value.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# UserCreate — used when inserting a new user after OAuth
# ═══════════════════════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    """Input model for creating a new user document after a successful OAuth login.

    The ``full_name``, ``student_id``, ``cohort``, and ``major`` fields are
    typically pre-populated by :func:`~utils.parse_hust_email.parse_hust_email`
    and may be overridden before submission.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required OAuth claims
    microsoft_id: str
    email: str

    # Pre-parsed profile fields (supplied by parse_hust_email)
    full_name: str
    student_id: str
    cohort: str
    major: str = "CNTT Việt Nhật"

    # Optional
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
# UserUpdate — all-Optional, used for the profile-form PATCH endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class UserUpdate(BaseModel):
    """All fields are optional so callers can send partial updates.

    Only fields present in the request body are written to MongoDB via
    ``$set``.  Timestamps (``updated_at``) are managed server-side.
    """

    model_config = ConfigDict(populate_by_name=True)

    full_name: Optional[str] = None
    student_id: Optional[str] = None
    cohort: Optional[str] = None
    major: Optional[str] = None
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
# UserPublic — safe API response (no microsoft_id)
# ═══════════════════════════════════════════════════════════════════════════════

class UserPublic(BaseModel):
    """User representation returned to API clients.

    ``microsoft_id`` is deliberately excluded to avoid leaking the OAuth
    token claim.  ``id`` is serialised as a plain string.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    email: str
    full_name: str
    student_id: str
    cohort: str
    major: str
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
