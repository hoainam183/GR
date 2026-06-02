"""Focused tests for persisted admin LLM config and runtime hot reload."""

from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from config.settings import Settings
from models.database import SYSTEM_CONFIG_COLLECTION
from models.system_config import (
    API_KEYS_FIELD,
    LLM_CONFIG_DOCUMENT_ID,
    ApiKeyRegistryError,
    create_api_key,
    filter_llm_config_updates,
    list_api_keys,
    merge_llm_config_into_settings,
    upsert_llm_config,
)


class _FakeCollection:
    def __init__(self, doc: dict | None = None, *, fail_update: bool = False) -> None:
        self.doc = dict(doc) if doc else None
        self.fail_update = fail_update
        self.update_calls: list[tuple[dict, dict, bool]] = []

    async def find_one(self, query: dict) -> dict | None:
        if self.doc and self.doc.get("_id") == query.get("_id"):
            return dict(self.doc)
        return None

    async def update_one(self, query: dict, update: dict, *, upsert: bool = False):
        self.update_calls.append((query, update, upsert))
        if self.fail_update:
            raise RuntimeError("db unavailable")
        self.doc = {
            **(self.doc or {}),
            "_id": query["_id"],
            **update["$set"],
        }
        return SimpleNamespace(matched_count=1)


class _FakeDB:
    def __init__(self, doc: dict | None = None, *, fail_update: bool = False) -> None:
        self.system_config = _FakeCollection(doc, fail_update=fail_update)

    def __getitem__(self, collection: str) -> _FakeCollection:
        if collection != SYSTEM_CONFIG_COLLECTION:
            raise KeyError(collection)
        return self.system_config


class _FakePipeline:
    def __init__(self, *, prepare_error: Exception | None = None) -> None:
        self.prepare_error = prepare_error
        self.prepared_settings: Settings | None = None
        self.commit_calls = 0

    def prepare_llm_config_reload(self, settings: Settings) -> dict:
        self.prepared_settings = settings
        if self.prepare_error:
            raise self.prepare_error
        return {"settings": settings}

    def commit_llm_config_reload(self, settings: Settings, prepared: dict) -> dict[str, str]:
        self.commit_calls += 1
        assert prepared["settings"] is settings
        return {"chat_llm": settings.chat_model, "caches": "cleared"}


class _FakeLLMCache:
    def __init__(self) -> None:
        self.calls = 0

    def invalidate_all(self) -> int:
        self.calls += 1
        return 3


def _make_settings(**updates) -> Settings:
    return Settings(
        google_api_key="env-google",
        tavily_api_key="env-tavily",
        _env_file=None,  # type: ignore[call-arg]
        **updates,
    )


def _make_request(settings: Settings, pipeline: _FakePipeline, llm_cache=None):
    state = SimpleNamespace(
        settings=settings,
        pipeline=pipeline,
        llm_cache=llm_cache,
    )
    return SimpleNamespace(app=SimpleNamespace(state=state))


def test_filter_and_merge_keep_model_fields_outside_api_key_registry() -> None:
    settings = _make_settings()

    filtered = filter_llm_config_updates(
        {
            "llm_provider": "  deepseek  ",
            "chat_model": "  new-chat  ",
            "google_api_key": "",
            "agent_enabled": False,
            "reflection_model": None,
        }
    )
    applied = merge_llm_config_into_settings(settings, filtered)

    assert filtered == {"llm_provider": "deepseek", "chat_model": "new-chat"}
    assert applied == ["llm_provider", "chat_model"]
    assert settings.llm_provider == "deepseek"
    assert settings.chat_model == "new-chat"
    assert settings.agent_enabled is True


@pytest.mark.anyio
async def test_upsert_llm_config_writes_fixed_document() -> None:
    db = _FakeDB()

    stored = await upsert_llm_config(
        db,
        {
            "chat_temperature": 0.15,
            "rate_limit_enabled": False,
        },
    )

    assert stored["_id"] == LLM_CONFIG_DOCUMENT_ID
    assert stored["chat_temperature"] == 0.15
    assert "rate_limit_enabled" not in stored
    assert db.system_config.update_calls[0][2] is True


@pytest.mark.anyio
async def test_startup_loader_merges_db_overrides(monkeypatch) -> None:
    from api import main as api_main

    settings = _make_settings(mongodb_database="test-db")
    db = _FakeDB(
        {
            "_id": LLM_CONFIG_DOCUMENT_ID,
            "google_api_key": "db-google",
            "chat_model": "db-chat",
        }
    )

    monkeypatch.setattr(
        "models.database.get_motor_client",
        lambda: {"test-db": db},
    )

    applied = await api_main._load_persisted_llm_config(settings)

    assert set(applied) == {"google_api_key", "chat_model"}
    assert settings.google_api_key == "db-google"
    assert settings.chat_model == "db-chat"
    assert db.system_config.doc[API_KEYS_FIELD][0]["secret"] == "db-google"
    assert db.system_config.doc[API_KEYS_FIELD][0]["status"] == "active"


@pytest.mark.anyio
async def test_legacy_google_and_tavily_keys_import_into_registry() -> None:
    db = _FakeDB(
        {
            "_id": LLM_CONFIG_DOCUMENT_ID,
            "google_api_key": "legacy-google",
            "tavily_api_key": "legacy-tavily",
        }
    )

    keys = await list_api_keys(db)

    assert {key["provider"] for key in keys} == {"google", "tavily"}
    assert all("secret" not in key for key in keys)
    assert all(key["status"] == "active" for key in keys)
    assert {
        record["secret"]
        for record in db.system_config.doc[API_KEYS_FIELD]
    } == {"legacy-google", "legacy-tavily"}


@pytest.mark.anyio
async def test_legacy_deepseek_key_imports_into_registry() -> None:
    db = _FakeDB(
        {
            "_id": LLM_CONFIG_DOCUMENT_ID,
            "deepseek_api_key": "legacy-deepseek",
        }
    )

    keys = await list_api_keys(db)

    assert keys[0]["provider"] == "deepseek"
    assert keys[0]["status"] == "active"
    assert "secret" not in keys[0]
    assert db.system_config.doc[API_KEYS_FIELD][0]["secret"] == "legacy-deepseek"


@pytest.mark.anyio
async def test_create_api_key_keeps_previous_provider_key_inactive() -> None:
    db = _FakeDB()
    old_key = await create_api_key(db, "google", "Old key", "old-google-secret")

    new_key = await create_api_key(db, "google", "New key", "new-google-secret")
    keys = await list_api_keys(db)

    assert old_key["status"] == "active"
    assert new_key["status"] == "active"
    assert [key["status"] for key in keys] == ["active", "inactive"]
    assert keys[0]["name"] == "New key"
    assert keys[1]["name"] == "Old key"
    assert sum(key["status"] == "active" for key in keys) == 1


@pytest.mark.anyio
async def test_create_api_key_rejects_duplicate_provider_secret() -> None:
    db = _FakeDB()
    await create_api_key(db, "google", "Primary", "shared-google-secret")

    with pytest.raises(ApiKeyRegistryError):
        await create_api_key(db, "google", "Duplicate", "shared-google-secret")


def test_create_llm_builds_deepseek_provider() -> None:
    from llm import create_llm

    settings = _make_settings(
        llm_provider="deepseek",
        chat_model="deepseek-v4-flash",
        deepseek_api_key="deepseek-secret",
    )

    llm = create_llm(settings)

    assert llm.__class__.__name__ == "DeepSeekLLM"
    assert llm.model == "deepseek-v4-flash"


@pytest.mark.anyio
async def test_api_key_listing_keeps_env_fallback_out_of_registry() -> None:
    from api.routes.admin_stats import get_api_keys

    db = _FakeDB()
    listing = await get_api_keys(
        _make_request(_make_settings(), _FakePipeline()),
        None,  # type: ignore[arg-type]
        db,
    )

    assert listing["keys"] == []
    assert set(listing["fallback_providers"]) == {"google", "tavily"}
    assert db.system_config.doc is None


@pytest.mark.anyio
async def test_deepseek_env_fallback_is_listed_when_unmanaged() -> None:
    from api.routes.admin_stats import get_api_keys

    db = _FakeDB()
    listing = await get_api_keys(
        _make_request(
            _make_settings(deepseek_api_key="env-deepseek"),
            _FakePipeline(),
        ),
        None,  # type: ignore[arg-type]
        db,
    )

    assert "deepseek" in listing["fallback_providers"]
    assert listing["keys"] == []
    assert db.system_config.doc is None


@pytest.mark.anyio
async def test_admin_api_key_create_and_activate_return_no_secret() -> None:
    from api.routes.admin_stats import (
        ApiKeyCreateBody,
        activate_managed_api_key,
        create_managed_api_key,
        get_api_keys,
    )

    settings = _make_settings()
    pipeline = _FakePipeline()
    db = _FakeDB()
    first = await create_managed_api_key(
        _make_request(settings, pipeline),
        ApiKeyCreateBody(provider="tavily", name="Tavily A", key="tvly-first-secret"),
        None,  # type: ignore[arg-type]
        db,
    )
    second = await create_managed_api_key(
        _make_request(settings, pipeline),
        ApiKeyCreateBody(provider="tavily", name="Tavily B", key="tvly-second-secret"),
        None,  # type: ignore[arg-type]
        db,
    )

    listing = await get_api_keys(
        _make_request(settings, pipeline),
        None,  # type: ignore[arg-type]
        db,
    )
    activated = await activate_managed_api_key(
        _make_request(settings, pipeline),
        first["key"]["id"],
        None,  # type: ignore[arg-type]
        db,
    )

    assert second["key"]["status"] == "active"
    assert "secret" not in listing["keys"][0]
    assert all("fingerprint" in key for key in listing["keys"])
    assert activated["key"]["id"] == first["key"]["id"]
    assert activated["key"]["status"] == "active"
    assert settings.tavily_api_key == "tvly-first-secret"
    assert [
        record["status"]
        for record in db.system_config.doc[API_KEYS_FIELD]
        if record["provider"] == "tavily"
    ] == ["active", "inactive"]


@pytest.mark.anyio
async def test_create_managed_api_key_prepare_failure_does_not_persist() -> None:
    from api.routes.admin_stats import ApiKeyCreateBody, create_managed_api_key

    settings = _make_settings()
    pipeline = _FakePipeline(prepare_error=RuntimeError("prepare failed"))
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc_info:
        await create_managed_api_key(
            _make_request(settings, pipeline),
            ApiKeyCreateBody(provider="google", name="Google A", key="new-google"),
            None,  # type: ignore[arg-type]
            db,
        )

    assert exc_info.value.status_code == 400
    assert db.system_config.update_calls == []
    assert settings.google_api_key == "env-google"
    assert pipeline.commit_calls == 0


@pytest.mark.anyio
async def test_create_managed_api_key_db_failure_does_not_commit_runtime() -> None:
    from api.routes.admin_stats import ApiKeyCreateBody, create_managed_api_key

    settings = _make_settings()
    pipeline = _FakePipeline()
    db = _FakeDB(fail_update=True)

    with pytest.raises(HTTPException) as exc_info:
        await create_managed_api_key(
            _make_request(settings, pipeline),
            ApiKeyCreateBody(provider="google", name="Google A", key="new-google"),
            None,  # type: ignore[arg-type]
            db,
        )

    assert exc_info.value.status_code == 503
    assert settings.google_api_key == "env-google"
    assert pipeline.commit_calls == 0


@pytest.mark.anyio
async def test_update_llm_config_persists_reloads_and_invalidates_chat_cache() -> None:
    from api.routes.admin_stats import LLMConfigBody, update_llm_config

    settings = _make_settings()
    pipeline = _FakePipeline()
    llm_cache = _FakeLLMCache()
    db = _FakeDB()

    response = await update_llm_config(
        _make_request(settings, pipeline, llm_cache),
        LLMConfigBody(
            google_api_key="new-google-key",
            chat_model="new-chat",
            chat_temperature=0.1,
        ),
        None,  # type: ignore[arg-type]
        db,
    )

    assert response["ok"] is True
    assert response["updated"]["google_api_key"] == "new-***-key"
    assert response["rebuilt"]["chat_llm"] == "new-chat"
    assert response["llm_cache_invalidated"] == 3
    assert db.system_config.doc["chat_model"] == "new-chat"
    assert db.system_config.doc[API_KEYS_FIELD][0]["secret"] == "new-google-key"
    assert settings.google_api_key == "new-google-key"
    assert settings.chat_model == "new-chat"
    assert pipeline.prepared_settings is not settings
    assert pipeline.prepared_settings.chat_model == "new-chat"
    assert pipeline.commit_calls == 1
    assert llm_cache.calls == 1


@pytest.mark.anyio
async def test_update_llm_config_switches_chat_generation_to_deepseek() -> None:
    from api.routes.admin_stats import LLMConfigBody, update_llm_config

    settings = _make_settings()
    pipeline = _FakePipeline()
    llm_cache = _FakeLLMCache()
    db = _FakeDB()

    response = await update_llm_config(
        _make_request(settings, pipeline, llm_cache),
        LLMConfigBody(
            llm_provider="deepseek",
            deepseek_api_key="new-deepseek-key",
            chat_model="deepseek-v4-flash",
        ),
        None,  # type: ignore[arg-type]
        db,
    )

    assert response["ok"] is True
    assert response["updated"]["llm_provider"] == "deepseek"
    assert response["updated"]["deepseek_api_key"] == "new-***-key"
    assert db.system_config.doc["llm_provider"] == "deepseek"
    assert db.system_config.doc["chat_model"] == "deepseek-v4-flash"
    assert db.system_config.doc[API_KEYS_FIELD][0]["provider"] == "deepseek"
    assert settings.llm_provider == "deepseek"
    assert settings.deepseek_api_key == "new-deepseek-key"
    assert settings.chat_model == "deepseek-v4-flash"
    assert pipeline.prepared_settings is not settings
    assert pipeline.prepared_settings.llm_provider == "deepseek"
    assert pipeline.commit_calls == 1
    assert llm_cache.calls == 1


@pytest.mark.anyio
async def test_update_llm_config_prepare_failure_does_not_persist() -> None:
    from api.routes.admin_stats import LLMConfigBody, update_llm_config

    settings = _make_settings()
    pipeline = _FakePipeline(prepare_error=RuntimeError("prepare failed"))
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc_info:
        await update_llm_config(
            _make_request(settings, pipeline),
            LLMConfigBody(chat_model="new-chat"),
            None,  # type: ignore[arg-type]
            db,
        )

    assert exc_info.value.status_code == 400
    assert db.system_config.update_calls == []
    assert settings.chat_model != "new-chat"
    assert pipeline.commit_calls == 0


@pytest.mark.anyio
async def test_update_llm_config_db_failure_does_not_commit_runtime() -> None:
    from api.routes.admin_stats import LLMConfigBody, update_llm_config

    settings = _make_settings()
    pipeline = _FakePipeline()
    db = _FakeDB(fail_update=True)

    with pytest.raises(HTTPException) as exc_info:
        await update_llm_config(
            _make_request(settings, pipeline),
            LLMConfigBody(chat_model="new-chat"),
            None,  # type: ignore[arg-type]
            db,
        )

    assert exc_info.value.status_code == 503
    assert settings.chat_model != "new-chat"
    assert pipeline.commit_calls == 0


def test_pipeline_llm_reload_prepares_before_swapping(monkeypatch) -> None:
    import agent.tool_adapters as tool_adapters
    import pipeline.rag_pipeline as rag_pipeline_module
    from pipeline.rag_pipeline import RAGPipeline

    pipeline = object.__new__(RAGPipeline)
    old_chat = SimpleNamespace(model="old-chat")
    new_chat = SimpleNamespace(model="new-chat")
    retrieval_service = SimpleNamespace(
        settings=object(),
        tavily_tool=object(),
        bge_embedder=object(),
        e5_embedder=object(),
        searcher=object(),
        reranker=object(),
    )
    pipeline._cfg = {"top_k": 5}
    pipeline._chat = old_chat
    pipeline._self_eval = object()
    pipeline._reflector = object()
    pipeline._decomposer = object()
    pipeline.agent = object()
    pipeline._tavily = object()
    pipeline._retrieval_service = retrieval_service
    pipeline._route_cache = OrderedDict([("route", (0.0, {}))])
    pipeline._llm_runtime_lock = rag_pipeline_module.RLock()

    new_reflector = object()
    new_decomposer = object()
    new_agent = object()
    new_tavily = object()
    injected: list[object] = []

    monkeypatch.setattr(rag_pipeline_module, "create_llm", lambda settings: new_chat)
    monkeypatch.setattr(
        rag_pipeline_module,
        "QueryReflector",
        lambda settings: new_reflector,
    )
    monkeypatch.setattr(
        rag_pipeline_module,
        "QueryDecomposer",
        lambda settings: new_decomposer,
    )
    monkeypatch.setattr(
        rag_pipeline_module,
        "ReActAgent",
        lambda settings: new_agent,
    )
    monkeypatch.setattr(
        rag_pipeline_module,
        "_build_tavily_tool",
        lambda settings: new_tavily,
    )
    monkeypatch.setattr(
        tool_adapters,
        "inject_from_retrieval_service",
        lambda service: injected.append(service),
    )

    settings = _make_settings(chat_model="new-chat", agent_model="new-agent")
    prepared = pipeline.prepare_llm_config_reload(settings)

    assert pipeline._chat is old_chat
    rebuilt = pipeline.commit_llm_config_reload(settings, prepared)

    assert pipeline._chat is new_chat
    assert pipeline._reflector is new_reflector
    assert pipeline._decomposer is new_decomposer
    assert pipeline.agent is new_agent
    assert retrieval_service.tavily_tool is new_tavily
    assert retrieval_service.settings is settings
    assert pipeline._route_cache == {}
    assert rebuilt["agent"] == "new-agent"
    assert injected == [retrieval_service]
    assert pipeline._llm_runtime_snapshot().chat is new_chat
