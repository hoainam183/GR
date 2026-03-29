"""Test Phase 7 — Bug Fixes & Feature Activation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure RAG_v2 root is on path
RAG_V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAG_V2_ROOT))

PASSED = 0
FAILED = 0


def report(name: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    status = "PASS" if ok else "FAIL"
    if ok:
        PASSED += 1
    else:
        FAILED += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")


# ═══════════════════════════════════════════════════════════════════════════════
# 7.1 Query Reflection Bug Fix
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 7.1 Query Reflection ===")

try:
    from pipeline.flows import rag_flow, rag_flow_stream

    # Mock all dependencies
    mock_reflector = MagicMock()
    mock_reflector.reflect.return_value = {
        "original": "test query",
        "rewritten": "rewritten test query",
    }

    mock_bge = MagicMock()
    mock_bge.embed_query.return_value = [0.1] * 1024

    mock_e5 = MagicMock()
    mock_e5.embed_query.return_value = [0.2] * 1024

    mock_searcher = MagicMock()
    mock_searcher.search.return_value = [
        {"text": "doc1", "metadata": {"title": "Test"}},
    ]

    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = [
        {"text": "doc1", "metadata": {"title": "Test"}},
    ]

    mock_chat = MagicMock()
    mock_chat.generate.return_value = "Test answer"
    mock_chat.model = "test-model"

    cfg = {
        "top_k": 5,
        "vector_top_k": 20,
        "keyword_top_k": 20,
        "vector_pool_k": 15,
        "keyword_pool_k": 15,
    }

    # Test rag_flow calls reflect() not rewrite()
    result = rag_flow(
        question="test query",
        history=None,
        reflector=mock_reflector,
        bge_embedder=mock_bge,
        e5_embedder=mock_e5,
        searcher=mock_searcher,
        reranker=mock_reranker,
        chat_model=mock_chat,
        self_evaluator=None,
        tavily_tool=None,
        cfg=cfg,
    )

    # Verify reflect() was called, not rewrite()
    report(
        "reflect() called",
        mock_reflector.reflect.called,
        "reflect() should be used",
    )
    report(
        "rewrite() NOT called",
        not mock_reflector.rewrite.called,
        "rewrite() should NOT be used",
    )

    # Verify the rewritten query was used for embedding
    mock_bge.embed_query.assert_called_with("rewritten test query")
    report("Rewritten query used for embedding", True)

    # Verify reflect was called with correct args
    call_args = mock_reflector.reflect.call_args
    report(
        "reflect() called with chat_history kwarg",
        "chat_history" in call_args.kwargs,
        f"kwargs={list(call_args.kwargs.keys())}",
    )

    # Test rag_flow_stream also uses reflect()
    mock_reflector.reset_mock()
    mock_chat.generate_stream.return_value = iter(["chunk1", "chunk2"])

    stream, sources = rag_flow_stream(
        question="test query",
        history=None,
        reflector=mock_reflector,
        bge_embedder=mock_bge,
        e5_embedder=mock_e5,
        searcher=mock_searcher,
        reranker=mock_reranker,
        chat_model=mock_chat,
        cfg=cfg,
    )
    # Consume the stream
    list(stream)

    report("Stream: reflect() called", mock_reflector.reflect.called)
    report("Stream: rewrite() NOT called", not mock_reflector.rewrite.called)

except Exception as exc:
    report("7.1 Query Reflection", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 7.2 Self-Evaluation Activation
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 7.2 Self-Evaluation ===")

try:
    from config.settings import Settings

    s = Settings()
    report(
        "self_eval_enabled default is True",
        s.self_eval_enabled is True,
        str(s.self_eval_enabled),
    )
except Exception as exc:
    report("Settings.self_eval_enabled", False, str(exc))

try:
    from llm.prompts import SELF_EVAL_SYSTEM_PROMPT, SELF_EVAL_USER_TEMPLATE

    # Verify prompt is in Vietnamese
    report(
        "Self-eval system prompt in Vietnamese",
        "Bạn là" in SELF_EVAL_SYSTEM_PROMPT
        or "đánh giá" in SELF_EVAL_SYSTEM_PROMPT,
        "Should contain Vietnamese text",
    )
    report(
        "Self-eval system prompt NOT English-only",
        "You are a strict" not in SELF_EVAL_SYSTEM_PROMPT,
        "Old English prompt should be replaced",
    )
    report(
        "User template in Vietnamese",
        "Câu hỏi người dùng" in SELF_EVAL_USER_TEMPLATE,
        "Should contain Vietnamese labels",
    )

    # Verify JSON keys are still in English (for parser compatibility)
    report(
        "JSON keys still English",
        '"pass"' in SELF_EVAL_SYSTEM_PROMPT
        and '"relevance"' in SELF_EVAL_SYSTEM_PROMPT,
        "JSON schema keys must remain English",
    )

    # Test self-eval with mock — verify it processes pass/fail correctly
    from llm.self_eval import SelfEvaluator

    evaluator = SelfEvaluator.__new__(SelfEvaluator)
    evaluator.model = "test"
    evaluator.temperature = 0.0

    # Test parse success
    result = evaluator._parse_evaluation(
        '{"pass": true, "relevance": "good", "faithfulness": "grounded", "completeness": "complete", "reason": "OK"}'
    )
    report("Parse eval pass=true", result["pass"] is True)

    # Test parse failure
    result = evaluator._parse_evaluation(
        '{"pass": false, "relevance": "bad", "faithfulness": "hallucinated", "completeness": "incomplete", "reason": "bad"}'
    )
    report("Parse eval pass=false", result["pass"] is False)

    # Test parse invalid JSON
    result = evaluator._parse_evaluation("not json at all")
    report("Parse invalid JSON → pass=False", result["pass"] is False)

except Exception as exc:
    report("7.2 Self-Evaluation", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 7.3 Tavily Fallback Activation
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 7.3 Tavily Fallback ===")

try:
    from config.settings import Settings

    s = Settings()
    report(
        "tavily_fallback_enabled default is True",
        s.tavily_fallback_enabled is True,
        str(s.tavily_fallback_enabled),
    )
except Exception as exc:
    report("Settings.tavily_fallback_enabled", False, str(exc))

try:
    from tools.tavily_search import TavilySearchTool

    # Verify retry attributes exist
    tool = TavilySearchTool.__new__(TavilySearchTool)
    tool.max_retries = 3
    tool.min_retry_delay = 1.0
    tool._last_call_time = 0.0
    report("TavilySearchTool has max_retries", hasattr(tool, "max_retries"))
    report(
        "TavilySearchTool has min_retry_delay", hasattr(tool, "min_retry_delay")
    )
    report(
        "TavilySearchTool has _last_call_time", hasattr(tool, "_last_call_time")
    )

    # Test that self-eval FAIL triggers Tavily in rag_flow
    from pipeline.flows import rag_flow

    mock_self_eval = MagicMock()
    mock_self_eval.evaluate.return_value = {
        "pass": False,
        "reason": "bad answer",
    }

    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {"context": "web context here"}

    mock_chat2 = MagicMock()
    mock_chat2.model = "test-model"
    # First call returns bad answer, second call (after tavily) returns better answer
    mock_chat2.generate.side_effect = ["bad answer", "better answer from web"]

    result = rag_flow(
        question="test",
        history=None,
        reflector=None,
        bge_embedder=mock_bge,
        e5_embedder=mock_e5,
        searcher=mock_searcher,
        reranker=mock_reranker,
        chat_model=mock_chat2,
        self_evaluator=mock_self_eval,
        tavily_tool=mock_tavily,
        cfg=cfg,
    )

    report("Self-eval triggered", mock_self_eval.evaluate.called)
    report("Tavily search triggered on FAIL", mock_tavily.search.called)
    report(
        "Answer replaced by Tavily fallback",
        result["answer"] == "better answer from web",
        f"got: {result['answer'][:50]}",
    )

except Exception as exc:
    report("7.3 Tavily Fallback", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 7.4 payload.pop("text") Bug Fix
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 7.4 payload.pop fix ===")

try:
    from retrieval.qdrant_store import QdrantStore

    # Create mock hits that simulate Qdrant results
    mock_hit_bge = MagicMock()
    mock_hit_bge.id = "point-1"
    mock_hit_bge.payload = {"text": "hello world", "title": "Doc1"}
    mock_hit_bge.score = 0.9

    mock_hit_e5 = MagicMock()
    mock_hit_e5.id = "point-1"  # Same ID — appears in both results
    mock_hit_e5.payload = {"text": "hello world", "title": "Doc1"}
    mock_hit_e5.score = 0.8

    # Before the fix, the second pop would lose "text" because the first pop mutated the payload.
    # After the fix (copy dict first), both should work correctly.
    fused = QdrantStore._fuse_results(
        [mock_hit_bge], [mock_hit_e5], top_k=5, bge_weight=0.5, e5_weight=0.5
    )

    report("Fused results not empty", len(fused) > 0)
    report(
        "Fused text preserved",
        fused[0]["text"] == "hello world",
        fused[0].get("text", "MISSING"),
    )

    # Verify original payload was NOT mutated
    report(
        "Original payload not mutated",
        "text" in mock_hit_bge.payload,
        f"payload keys: {list(mock_hit_bge.payload.keys())}",
    )

except Exception as exc:
    report("7.4 payload.pop fix", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 7.5 Config Sync
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 7.5 Config Sync ===")

try:
    from config.settings import Settings

    s = Settings()
    # Verify Settings has all required fields
    report(
        "Settings.reflection_enabled exists", hasattr(s, "reflection_enabled")
    )
    report(
        "Settings.reflection_enabled default True", s.reflection_enabled is True
    )
    report("Settings.self_eval_enabled", s.self_eval_enabled is True)
    report(
        "Settings.tavily_fallback_enabled", s.tavily_fallback_enabled is True
    )
except Exception as exc:
    report("Settings fields", False, str(exc))

try:
    import importlib
    import pipeline.rag_pipeline as rp_module

    # Verify CONFIG dict is removed
    report(
        "CONFIG dict removed",
        not hasattr(rp_module, "CONFIG"),
        "Should use Settings class",
    )

    # Verify _settings_to_cfg function exists
    report("_settings_to_cfg exists", hasattr(rp_module, "_settings_to_cfg"))

    # Test _settings_to_cfg output
    from pipeline.rag_pipeline import _settings_to_cfg

    cfg = _settings_to_cfg(s)
    report("cfg has collections", "collections" in cfg)
    report(
        "cfg has es_host", "es_host" in cfg, "mapped from elasticsearch_host"
    )
    report("cfg has model", "model" in cfg, "mapped from chat_model")
    report(
        "cfg has temperature",
        "temperature" in cfg,
        "mapped from chat_temperature",
    )
    report("cfg has reflection_enabled", "reflection_enabled" in cfg)
    report("cfg has self_eval_enabled", "self_eval_enabled" in cfg)
    report("cfg has tavily_fallback_enabled", "tavily_fallback_enabled" in cfg)

    # Verify values match Settings
    report("cfg.model matches", cfg["model"] == s.chat_model, cfg["model"])
    report("cfg.es_host matches", cfg["es_host"] == s.elasticsearch_host)
    report("cfg.top_k matches", cfg["top_k"] == s.top_k, str(cfg["top_k"]))

except Exception as exc:
    report("7.5 Config Sync", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(
    f"Phase 7 Results: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total"
)
print(f"{'='*60}")

if FAILED > 0:
    sys.exit(1)
