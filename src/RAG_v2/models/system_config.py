"""Mongo-backed runtime overrides for admin-managed system configuration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from models.database import SYSTEM_CONFIG_COLLECTION

LLM_CONFIG_DOCUMENT_ID = "llm_config"
API_KEYS_FIELD = "api_keys"
API_KEY_SETTING_FIELDS = {
    "google": "google_api_key",
    "tavily": "tavily_api_key",
}
_IMPORTED_API_KEY_NAMES = {
    "google": "Imported Google key",
    "tavily": "Imported Tavily key",
}

# Keep this aligned with the current SystemTab LLM form. Runtime toggles and
# provider switching have separate lifecycle semantics and are not persisted here.
PERSISTABLE_LLM_FIELDS = frozenset(
    {
        "chat_model",
        "chat_temperature",
        "chat_max_tokens",
        "agent_model",
        "reflection_model",
    }
)


class ApiKeyRegistryError(ValueError):
    """Raised when an admin API key registry mutation is invalid."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_api_keys(config: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    records = (config or {}).get(API_KEYS_FIELD, [])
    if not isinstance(records, list):
        return []
    return [dict(record) for record in records if isinstance(record, Mapping)]


def _active_provider_secrets(config: Mapping[str, Any] | None) -> dict[str, str]:
    secrets: dict[str, str] = {}
    for record in _clean_api_keys(config):
        provider = record.get("provider")
        secret = record.get("secret")
        if (
            provider in API_KEY_SETTING_FIELDS
            and record.get("status") == "active"
            and isinstance(secret, str)
            and secret.strip()
        ):
            secrets[provider] = secret.strip()
    return secrets


def _provider_records(
    config: Mapping[str, Any] | None,
    provider: str,
) -> list[dict[str, Any]]:
    return [
        record
        for record in _clean_api_keys(config)
        if record.get("provider") == provider
    ]


def _import_legacy_api_keys(
    config: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Return a config copy with legacy DB key fields imported into the registry."""
    migrated = dict(config or {"_id": LLM_CONFIG_DOCUMENT_ID})
    records = _clean_api_keys(migrated)
    imported: list[str] = []
    now = _utc_now()

    for provider, field_name in API_KEY_SETTING_FIELDS.items():
        legacy_secret = migrated.get(field_name)
        if _provider_records({API_KEYS_FIELD: records}, provider):
            continue
        if not isinstance(legacy_secret, str) or not legacy_secret.strip():
            continue
        records.append(
            {
                "id": str(uuid4()),
                "provider": provider,
                "name": _IMPORTED_API_KEY_NAMES[provider],
                "secret": legacy_secret.strip(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "activated_at": now,
            }
        )
        imported.append(provider)

    if imported:
        migrated[API_KEYS_FIELD] = records
    return migrated, imported


async def _persist_api_key_records(
    db: AsyncIOMotorDatabase,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    collection = db[SYSTEM_CONFIG_COLLECTION]
    await collection.update_one(
        {"_id": LLM_CONFIG_DOCUMENT_ID},
        {"$set": {API_KEYS_FIELD: records, "updated_at": _utc_now()}},
        upsert=True,
    )
    stored = await collection.find_one({"_id": LLM_CONFIG_DOCUMENT_ID})
    return dict(stored or {"_id": LLM_CONFIG_DOCUMENT_ID, API_KEYS_FIELD: records})


def filter_llm_config_updates(updates: Mapping[str, Any]) -> dict[str, Any]:
    """Return non-empty admin model overrides that are safe to persist."""
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
    """Read persisted system config and migrate DB-backed legacy API keys."""
    config = await db[SYSTEM_CONFIG_COLLECTION].find_one(
        {"_id": LLM_CONFIG_DOCUMENT_ID}
    )
    if not config:
        return None
    migrated, imported = _import_legacy_api_keys(config)
    if imported:
        return await _persist_api_key_records(db, _clean_api_keys(migrated))
    return dict(config)


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

    active_secrets = _active_provider_secrets(db_config)
    for provider, field_name in API_KEY_SETTING_FIELDS.items():
        secret = active_secrets.get(provider)
        if secret and hasattr(settings, field_name):
            setattr(settings, field_name, secret)
            applied.append(field_name)
            continue

        if _provider_records(db_config, provider):
            continue

        legacy_secret = (db_config or {}).get(field_name)
        if (
            isinstance(legacy_secret, str)
            and legacy_secret.strip()
            and hasattr(settings, field_name)
        ):
            setattr(settings, field_name, legacy_secret.strip())
            applied.append(field_name)
    return applied


def fingerprint_api_key(secret: str) -> str:
    """Return the only API key representation safe for admin responses."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "***"
    return secret[:4] + "***" + secret[-4:]


def public_api_key_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Strip the secret from one API key registry record."""
    return {
        "id": str(record.get("id", "")),
        "provider": str(record.get("provider", "")),
        "name": str(record.get("name", "")),
        "fingerprint": fingerprint_api_key(str(record.get("secret", ""))),
        "status": str(record.get("status", "inactive")),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "activated_at": record.get("activated_at"),
    }


def _api_key_sort_value(record: Mapping[str, Any]) -> tuple[int, float]:
    updated_at = record.get("updated_at")
    timestamp = updated_at.timestamp() if isinstance(updated_at, datetime) else 0.0
    return (0 if record.get("status") == "active" else 1, -timestamp)


async def list_api_keys(db: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    """Return secret-free managed API key rows for the admin UI."""
    config = await get_llm_config(db)
    records = sorted(_clean_api_keys(config), key=_api_key_sort_value)
    return [public_api_key_record(record) for record in records]


def _normalize_api_key_input(provider: str, name: str, secret: str) -> tuple[str, str, str]:
    provider = provider.strip().lower()
    name = name.strip()
    secret = secret.strip()
    if provider not in API_KEY_SETTING_FIELDS:
        raise ApiKeyRegistryError("Unsupported API key provider")
    if not name:
        raise ApiKeyRegistryError("API key name is required")
    if len(name) > 120:
        raise ApiKeyRegistryError("API key name is too long")
    if not secret:
        raise ApiKeyRegistryError("API key value is required")
    return provider, name, secret


async def create_api_key(
    db: AsyncIOMotorDatabase,
    provider: str,
    name: str,
    secret: str,
) -> dict[str, Any]:
    """Create and activate a managed API key, preserving prior key history."""
    provider, name, secret = _normalize_api_key_input(provider, name, secret)
    config = await get_llm_config(db)
    records = _clean_api_keys(config)
    if any(
        record.get("provider") == provider and record.get("secret") == secret
        for record in records
    ):
        raise ApiKeyRegistryError("API key already exists for this provider")

    now = _utc_now()
    for record in records:
        if record.get("provider") == provider and record.get("status") == "active":
            record["status"] = "inactive"
            record["updated_at"] = now

    created = {
        "id": str(uuid4()),
        "provider": provider,
        "name": name,
        "secret": secret,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "activated_at": now,
    }
    records.append(created)
    await _persist_api_key_records(db, records)
    return public_api_key_record(created)


async def get_api_key_record(
    db: AsyncIOMotorDatabase,
    key_id: str,
) -> dict[str, Any] | None:
    """Return one internal API key record, including the secret for runtime use."""
    config = await get_llm_config(db)
    for record in _clean_api_keys(config):
        if record.get("id") == key_id:
            return record
    return None


async def activate_api_key(
    db: AsyncIOMotorDatabase,
    key_id: str,
) -> dict[str, Any]:
    """Set one managed API key active and mark sibling provider keys inactive."""
    config = await get_llm_config(db)
    records = _clean_api_keys(config)
    selected = next((record for record in records if record.get("id") == key_id), None)
    if not selected:
        raise ApiKeyRegistryError("API key not found")

    provider = str(selected.get("provider", ""))
    if provider not in API_KEY_SETTING_FIELDS:
        raise ApiKeyRegistryError("Unsupported API key provider")

    now = _utc_now()
    for record in records:
        if record.get("provider") != provider:
            continue
        record["status"] = "active" if record.get("id") == key_id else "inactive"
        record["updated_at"] = now
        if record.get("id") == key_id:
            record["activated_at"] = now

    await _persist_api_key_records(db, records)
    return public_api_key_record(selected)
