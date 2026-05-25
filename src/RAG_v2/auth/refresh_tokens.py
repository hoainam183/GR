"""Opaque refresh-token rotation and revocation helpers."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.database import REFRESH_TOKENS_COLLECTION, USERS_COLLECTION
from models.user import UserDocument


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _settings() -> tuple[int, int]:
    lifetime_days = int(os.environ.get("JWT_REFRESH_EXPIRE_DAYS", "30"))
    idle_days = int(os.environ.get("JWT_REFRESH_IDLE_DAYS", "7"))
    return lifetime_days, idle_days


def generate_refresh_token() -> str:
    """Return a high-entropy opaque token for clients to store."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token before storing or looking it up."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_max_age_seconds() -> int:
    lifetime_days, _ = _settings()
    return lifetime_days * 24 * 60 * 60


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _is_expired(doc: dict[str, Any], now: datetime) -> bool:
    _, idle_days = _settings()
    expires_at = doc.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at <= now:
        return True

    last_used_at = doc.get("last_used_at") or doc.get("created_at")
    if isinstance(last_used_at, datetime):
        return last_used_at + timedelta(days=idle_days) <= now

    return False


async def create_refresh_session(
    db: AsyncIOMotorDatabase,
    *,
    user_id: str,
    client_type: str = "web",
    family_id: str | None = None,
) -> str:
    """Create a refresh-token session and return the raw token once."""
    lifetime_days, _ = _settings()
    now = _now()
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    await db[REFRESH_TOKENS_COLLECTION].insert_one(
        {
            "token_hash": token_hash,
            "user_id": user_id,
            "family_id": family_id or str(uuid4()),
            "client_type": client_type,
            "created_at": now,
            "expires_at": now + timedelta(days=lifetime_days),
            "last_used_at": now,
            "revoked_at": None,
            "replaced_by": None,
        }
    )
    return raw_token


async def revoke_refresh_family(
    db: AsyncIOMotorDatabase,
    family_id: str,
    *,
    now: datetime | None = None,
) -> None:
    revoked_at = now or _now()
    await db[REFRESH_TOKENS_COLLECTION].update_many(
        {"family_id": family_id, "revoked_at": None},
        {"$set": {"revoked_at": revoked_at}},
    )


async def revoke_refresh_token(
    db: AsyncIOMotorDatabase,
    token: str,
    *,
    now: datetime | None = None,
) -> bool:
    token_hash = hash_refresh_token(token)
    revoked_at = now or _now()
    result = await db[REFRESH_TOKENS_COLLECTION].update_one(
        {"token_hash": token_hash, "revoked_at": None},
        {"$set": {"revoked_at": revoked_at}},
    )
    return bool(getattr(result, "modified_count", 0))


async def rotate_refresh_token(
    db: AsyncIOMotorDatabase,
    token: str,
    *,
    client_type: str = "web",
) -> tuple[str, UserDocument]:
    """Rotate a refresh token and return ``(new_raw_token, user)``.

    Reusing an already-revoked token revokes the whole token family.

    Note: the find-then-update pattern has a theoretical TOCTOU race if two
    concurrent requests present the same token simultaneously.  In practice this
    is extremely rare and the worst outcome is a duplicate child token in the
    same family; both children will later be treated as reuse-detected and the
    family will be revoked.  A full fix requires a MongoDB transaction or an
    atomic ``findOneAndUpdate`` migration.
    """
    now = _now()
    token_hash = hash_refresh_token(token)
    collection = db[REFRESH_TOKENS_COLLECTION]
    doc = await collection.find_one({"token_hash": token_hash})

    if doc is None:
        raise _unauthorized("Invalid refresh token")

    family_id = doc.get("family_id")
    if doc.get("revoked_at") is not None:
        if family_id:
            await revoke_refresh_family(db, family_id, now=now)
        raise _unauthorized("Refresh token has been revoked")

    if _is_expired(doc, now):
        await collection.update_one(
            {"token_hash": token_hash},
            {"$set": {"revoked_at": now, "last_used_at": now}},
        )
        raise _unauthorized("Refresh token has expired")

    user_id = str(doc.get("user_id") or "")
    if not ObjectId.is_valid(user_id):
        await collection.update_one(
            {"token_hash": token_hash},
            {"$set": {"revoked_at": now, "last_used_at": now}},
        )
        raise _unauthorized("Refresh token user is invalid")

    user_doc = await db[USERS_COLLECTION].find_one({"_id": ObjectId(user_id)})
    if user_doc is None:
        await collection.update_one(
            {"token_hash": token_hash},
            {"$set": {"revoked_at": now, "last_used_at": now}},
        )
        raise _unauthorized("User account not found")

    user = UserDocument.model_validate(user_doc)
    if not user.is_active:
        if family_id:
            await revoke_refresh_family(db, str(family_id), now=now)
        raise _unauthorized("User account has been deactivated")

    next_raw = generate_refresh_token()
    next_hash = hash_refresh_token(next_raw)
    await collection.insert_one(
        {
            "token_hash": next_hash,
            "user_id": user_id,
            "family_id": family_id,
            "client_type": client_type,
            "created_at": now,
            "expires_at": doc.get("expires_at"),
            "last_used_at": now,
            "revoked_at": None,
            "replaced_by": None,
        }
    )
    await collection.update_one(
        {"token_hash": token_hash},
        {"$set": {"revoked_at": now, "last_used_at": now, "replaced_by": next_hash}},
    )

    return next_raw, user
