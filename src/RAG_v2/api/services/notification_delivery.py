"""Shared notification creation and Expo push delivery helpers."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from models.database import (
    NOTIFICATION_SUBSCRIPTIONS_COLLECTION,
    NOTIFICATIONS_COLLECTION,
    USERS_COLLECTION,
)

logger = logging.getLogger(__name__)

DEFAULT_EXPO_PUSH_ENDPOINT = "https://exp.host/--/api/v2/push/send"
EXPO_BATCH_SIZE = 100


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


async def resolve_notification_user_ids(
    db: AsyncIOMotorDatabase,
    topics: list[str] | None = None,
) -> list[str]:
    """Return target user ids for topics, or every user when topics are empty."""
    clean_topics = sorted({topic.strip() for topic in topics or [] if topic.strip()})
    if clean_topics:
        cursor = db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].find(
            {"topics": {"$in": clean_topics}},
            {"user_id": 1},
        )
        return sorted({str(doc["user_id"]) async for doc in cursor if doc.get("user_id")})

    cursor = db[USERS_COLLECTION].find({}, {"_id": 1})
    return [str(doc["_id"]) async for doc in cursor]


async def broadcast_user_notification(
    db: AsyncIOMotorDatabase,
    *,
    title: str,
    body: str,
    notification_type: str = "update",
    metadata: dict[str, Any] | None = None,
    related_doc_id: str | None = None,
    topics: list[str] | None = None,
    user_ids: list[str] | None = None,
    push_enabled: bool | None = None,
) -> dict[str, Any]:
    """Create DB notifications and best-effort Expo pushes for users."""
    clean_topics = sorted({topic.strip() for topic in topics or [] if topic.strip()})
    target_user_ids = user_ids or await resolve_notification_user_ids(db, clean_topics)
    target_user_ids = [uid for uid in dict.fromkeys(target_user_ids) if uid]

    if not target_user_ids:
        return {
            "created_count": 0,
            "target_user_ids": [],
            "push_sent_count": 0,
            "push_error_count": 0,
        }

    now = datetime.now(timezone.utc)
    docs = [
        {
            "user_id": uid,
            "title": title,
            "body": body,
            "type": notification_type,
            "related_doc_id": related_doc_id,
            "topics": clean_topics,
            "metadata": metadata or {},
            "read": False,
            "created_at": now,
        }
        for uid in target_user_ids
    ]
    result = await db[NOTIFICATIONS_COLLECTION].insert_many(docs)

    push_result = await send_expo_push_notifications(
        db,
        user_ids=target_user_ids,
        title=title,
        body=body,
        data={
            "type": notification_type,
            "related_doc_id": related_doc_id,
            "metadata": metadata or {},
        },
        enabled=push_enabled,
    )

    return {
        "created_count": len(result.inserted_ids),
        "target_user_ids": target_user_ids,
        **push_result,
    }


async def send_expo_push_notifications(
    db: AsyncIOMotorDatabase,
    *,
    user_ids: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Send Expo push notifications without making DB notification creation fail."""
    if enabled is None:
        enabled = _env_bool("PUSH_NOTIFICATIONS_ENABLED", True)
    if not enabled:
        return {"push_sent_count": 0, "push_error_count": 0, "push_disabled": True}

    cursor = db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].find(
        {"user_id": {"$in": user_ids}},
        {"expo_push_token": 1, "user_id": 1},
    )
    token_to_user: dict[str, str] = {}
    async for doc in cursor:
        token = str(doc.get("expo_push_token") or "").strip()
        if token:
            token_to_user[token] = str(doc.get("user_id") or "")

    tokens = list(token_to_user)
    if not tokens:
        return {"push_sent_count": 0, "push_error_count": 0}

    endpoint = os.getenv("EXPO_PUSH_ENDPOINT", DEFAULT_EXPO_PUSH_ENDPOINT)
    timeout_s = _env_float("EXPO_PUSH_TIMEOUT_SECONDS", 5.0)
    sent_count = 0
    error_count = 0
    invalid_tokens: list[str] = []

    for start in range(0, len(tokens), EXPO_BATCH_SIZE):
        batch_tokens = tokens[start : start + EXPO_BATCH_SIZE]
        messages = [
            {
                "to": token,
                "title": title,
                "body": body,
                "data": data or {},
                "sound": "default",
            }
            for token in batch_tokens
        ]
        try:
            response = await asyncio.to_thread(
                _post_expo_push_batch,
                endpoint,
                messages,
                timeout_s,
            )
            batch_sent, batch_errors, batch_invalid = _summarize_expo_response(
                response,
                batch_tokens,
            )
            sent_count += batch_sent
            error_count += batch_errors
            invalid_tokens.extend(batch_invalid)
        except Exception:
            error_count += len(batch_tokens)
            logger.warning("Expo push batch failed", exc_info=True)

    if invalid_tokens:
        await db[NOTIFICATION_SUBSCRIPTIONS_COLLECTION].delete_many(
            {"expo_push_token": {"$in": invalid_tokens}}
        )

    return {
        "push_sent_count": sent_count,
        "push_error_count": error_count,
        "push_invalid_token_count": len(invalid_tokens),
    }


def _post_expo_push_batch(
    endpoint: str,
    messages: list[dict[str, Any]],
    timeout_s: float,
) -> dict[str, Any]:
    payload = json.dumps(messages).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Expo push HTTP {exc.code}: {raw[:500]}") from exc
    return json.loads(raw or "{}")


def _summarize_expo_response(
    response: dict[str, Any],
    tokens: list[str],
) -> tuple[int, int, list[str]]:
    data = response.get("data")
    if not isinstance(data, list):
        return 0, len(tokens), []

    sent = 0
    errors = 0
    invalid_tokens: list[str] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            errors += 1
            continue
        if item.get("status") == "ok":
            sent += 1
            continue
        errors += 1
        details = item.get("details")
        if (
            isinstance(details, dict)
            and details.get("error") == "DeviceNotRegistered"
            and index < len(tokens)
        ):
            invalid_tokens.append(tokens[index])
    return sent, errors, invalid_tokens
