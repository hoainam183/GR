"""Unit and integration tests for Phase 2: Exact Cache & History Cache.

Utilizes fakeredis to mock Redis connection and state.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

try:
    import fakeredis
except ImportError:  # pragma: no cover - optional test dependency
    fakeredis = None

pytestmark = pytest.mark.skipif(
    fakeredis is None,
    reason="fakeredis not installed (pip install fakeredis)",
)

from cache.llm_cache import LLMResponseCache
from cache.history_cache import ConversationHistoryCache
from models.mongo_logger import MongoLogger
from pipeline.flows import rag_flow, rag_flow_stream


@pytest.fixture
def fake_redis():
    """Returns a fake redis client instance."""
    return fakeredis.FakeRedis(decode_responses=True)


# ═══════════════════════════════════════════════════════════════════════════════
# LLM Response Cache Tests (Feature 3)
# ═══════════════════════════════════════════════════════════════════════════════

def test_llm_cache_put_get_hit_miss(fake_redis):
    cache = LLMResponseCache(fake_redis)

    query = "Học phí ngành CNTT là bao nhiêu?"
    doc_ids = ["doc_1", "doc_2"]
    model = "gemini-1.5-pro"
    answer = "Học phí là 30 triệu/năm."
    sources = [{"id": "doc_1", "text": "CNTT: 30tr/năm"}]

    # 1. Miss initially
    res = cache.get(query, doc_ids, model)
    assert res is None

    stats = cache.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 1

    # 2. Put into cache
    cache.put(query, doc_ids, model, answer, sources)

    # 3. Hit subsequently
    res = cache.get(query, doc_ids, model)
    assert res is not None
    assert res["answer"] == answer
    assert res["sources"] == sources
    assert res["model_name"] == model

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_llm_cache_faq_promotion(fake_redis):
    cache = LLMResponseCache(fake_redis)

    query = "Quy định đăng ký tín chỉ"
    doc_ids = ["doc_qc"]
    model = "gemini"
    cache.put(query, doc_ids, model, "Trả lời", [])

    # We need 4 hits first, so the 5th hit triggers the FAQ promotion
    for _ in range(4):
        res = cache.get(query, doc_ids, model)
        assert res is not None

    key = cache._build_key(query, doc_ids, model)
    ttl = fake_redis.ttl(key)
    assert ttl <= 3600  # Default 1h

    # 5th hit promotes to FAQ TTL (24h = 86400s)
    res = cache.get(query, doc_ids, model)
    assert res is not None
    ttl = fake_redis.ttl(key)
    assert ttl > 3600
    assert ttl <= 86400


def test_llm_cache_invalidation(fake_redis):
    cache = LLMResponseCache(fake_redis)

    cache.put("Q1", ["D1"], "model", "A1", [])
    cache.put("Q2", ["D2"], "model", "A2", [])

    # Check they exist
    assert cache.get("Q1", ["D1"], "model") is not None
    assert cache.get("Q2", ["D2"], "model") is not None

    # Invalidate all — returns total keys deleted (cache entries + doc reverse-index tags).
    # 2 cache keys (llm_cache:*) + 2 doc-tag keys (doc_cache_tag:D1, doc_cache_tag:D2) = 4.
    cleared = cache.invalidate_all()
    assert cleared >= 2  # At minimum the 2 cache entries must be removed

    # Check they are deleted
    assert cache.get("Q1", ["D1"], "model") is None
    assert cache.get("Q2", ["D2"], "model") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Conversation History Cache Tests (Feature 4)
# ═══════════════════════════════════════════════════════════════════════════════

def test_history_cache_operations(fake_redis):
    cache = ConversationHistoryCache(fake_redis)
    session_id = "test_session_123"

    # Miss initially
    assert cache.get_history(session_id) is None

    # Add messages (LPUSH + LTRIM)
    cache.add_message(session_id, "user", "Hello")
    cache.add_message(session_id, "assistant", "Hi there")

    history = cache.get_history(session_id)
    assert history == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]


def test_history_cache_ltrim_cap(fake_redis):
    cache = ConversationHistoryCache(fake_redis)
    session_id = "cap_session"

    # Add 25 messages
    for i in range(25):
        cache.add_message(session_id, "user", f"Msg {i}")

    history = cache.get_history(session_id)
    # List is capped at 20 messages
    assert len(history) == 20
    assert history[0]["content"] == "Msg 5"
    assert history[-1]["content"] == "Msg 24"


def test_history_cache_warming(fake_redis):
    cache = ConversationHistoryCache(fake_redis)
    session_id = "warm_session"

    mongo_history = [
        {"role": "user", "content": "Hello Mongo"},
        {"role": "assistant", "content": "Hi Mongo"},
    ]
    cache.warm_history(session_id, mongo_history)

    history = cache.get_history(session_id)
    assert history == mongo_history


# ═══════════════════════════════════════════════════════════════════════════════
# RAG Flow Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_rag_flow_cache_hit_and_put(fake_redis):
    cache = LLMResponseCache(fake_redis)

    mock_chat = MagicMock()
    mock_chat.model = "gemini-mock"
    mock_chat.generate.return_value = "Mocked LLM Answer"

    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = [{"id": "doc_1", "text": "CNTT"}]

    cfg = {"collections": ["kehoach"], "top_k": 3}

    # 1. First run - Misses cache, generates and puts to cache
    result = rag_flow(
        question="Hỏi về CNTT",
        history=[],
        reflector=None,
        bge_embedder=MagicMock(),
        e5_embedder=MagicMock(),
        searcher=MagicMock(),
        reranker=mock_reranker,
        chat_model=mock_chat,
        self_evaluator=None,
        tavily_tool=None,
        cfg=cfg,
        llm_cache=cache,
    )

    assert result["answer"] == "Mocked LLM Answer"
    assert "cache_hit" not in result
    mock_chat.generate.assert_called_once()

    # 2. Second run - Hits cache directly, skipping LLM call
    mock_chat.reset_mock()
    result_cached = rag_flow(
        question="Hỏi về CNTT",
        history=[],
        reflector=None,
        bge_embedder=MagicMock(),
        e5_embedder=MagicMock(),
        searcher=MagicMock(),
        reranker=mock_reranker,
        chat_model=mock_chat,
        self_evaluator=None,
        tavily_tool=None,
        cfg=cfg,
        llm_cache=cache,
    )

    assert result_cached["answer"] == "Mocked LLM Answer"
    assert result_cached["cache_hit"] is True
    mock_chat.generate.assert_not_called()
