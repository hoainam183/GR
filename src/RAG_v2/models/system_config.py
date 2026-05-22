"""Mongo-backed runtime overrides for admin-managed system configuration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from motor.motor_asyncio import AsyncIOMotorDatabase

from models.database import SYSTEM_CONFIG_COLLECTION

LLM_CONFIG_DOCUMENT_ID = "llm_config"

# Keep this aligned with the current SystemTab LLM form. Runtime toggles and
# provider switching have separate lifecycle semantics and are not persisted here.
PERSISTABLE_LLM_FIELDS = frozenset(
    {
        "google_api_key",
        "tavily_api_key",
        "chat_model",
        "chat_temperature",
        "chat_max_tokens",
        "agent_model",
        "reflection_model",
    }
)


def filter_llm_config_updates(updates: Mapping[str, Any]) -> dict[str, Any]:
    """Return non-empty admin LLM overrides that are safe to persist."""
    filtered: dict[str, Any] = {}
    for field_name, value in updates.items():
        if field_name not in PERSISTABLE_LLM_FIELDS or value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        filtered[field_name] = value
    return filtered


async def get_llm_config(db: AsyncIOMotorDatabase) -> dict[str, Any] | None:
    """Read the persisted LLM override document."""
    return await db[SYSTEM_CONFIG_COLLECTION].find_one(
        {"_id": LLM_CONFIG_DOCUMENT_ID}
    )


async def upsert_llm_config(
    db: AsyncIOMotorDatabase,
    updates: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a partial LLM override update and return the stored document."""
    filtered = filter_llm_config_updates(updates)
    if not filtered:
        raise ValueError("No persistable LLM config fields to update")

    payload = {
        **filtered,
        "updated_at": datetime.now(timezone.utc),
    }
    collection = db[SYSTEM_CONFIG_COLLECTION]
    await collection.update_one(
        {"_id": LLM_CONFIG_DOCUMENT_ID},
        {"$set": payload},
        upsert=True,
    )
    stored = await collection.find_one({"_id": LLM_CONFIG_DOCUMENT_ID})
    return dict(stored or {"_id": LLM_CONFIG_DOCUMENT_ID, **payload})


def merge_llm_config_into_settings(
    settings: Any,
    db_config: Mapping[str, Any] | None,
) -> list[str]:
    """Apply persisted LLM overrides onto a Settings-like object."""
    applied: list[str] = []
    for field_name, value in filter_llm_config_updates(db_config or {}).items():
        if hasattr(settings, field_name):
            setattr(settings, field_name, value)
            applied.append(field_name)
    return applied
