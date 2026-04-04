"""Test Phase 8 — Collection-aware Query Routing.

Tests:
  8.1 CollectionSelector logic
  8.2 MultiCollectionSearch active_collections filtering
  8.3 rag_flow integration with routing_result
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

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
# 8.1 CollectionSelector
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 8.1 CollectionSelector ===")

try:
    from retrieval.collection_selector import (
        CollectionSelector,
        DOMAIN_TO_COLLECTIONS,
        ALL_COLLECTIONS,
        MULTI_DOMAIN_FALLBACK,
    )

    selector = CollectionSelector()
    report("CollectionSelector import", True)

    # Test 1: domain=None → all collections
    result = selector.select(domain=None, confidence=0.0)
    report(
        "domain=None → all collections",
        set(result) == set(ALL_COLLECTIONS),
        str(result),
    )

    # Test 2: domain="quydinh" with high confidence → ["quydinh"]
    result = selector.select(domain="quydinh", confidence=0.90)
    report(
        "domain=quydinh, conf=0.90 → ['quydinh']",
        result == ["quydinh"],
        str(result),
    )

    # Test 3: domain="stsv" with high confidence → ["stsv"]
    result = selector.select(domain="stsv", confidence=0.80)
    report(
        "domain=stsv, conf=0.80 → ['stsv']",
        result == ["stsv"],
        str(result),
    )

    # Test 4: domain="ctdt" with high confidence → ["ctdt"]
    result = selector.select(domain="ctdt", confidence=0.75)
    report(
        "domain=ctdt, conf=0.75 → ['ctdt']",
        result == ["ctdt"],
        str(result),
    )

    # Test 5: domain="kehoach" with high confidence → ["kehoach"]
    result = selector.select(domain="kehoach", confidence=0.70)
    report(
        "domain=kehoach, conf=0.70 → ['kehoach']",
        result == ["kehoach"],
        str(result),
    )

    # Test 6: Low confidence → fallback
    result = selector.select(domain="quydinh", confidence=0.40)
    report(
        "low confidence → fallback",
        set(result) == set(MULTI_DOMAIN_FALLBACK),
        str(result),
    )

    # Test 7: Unknown domain → all collections
    result = selector.select(domain="unknown_domain", confidence=0.99)
    report(
        "unknown domain → all collections",
        set(result) == set(ALL_COLLECTIONS),
        str(result),
    )

    # Test 8: Custom threshold
    custom = CollectionSelector(confidence_threshold=0.80)
    result = custom.select(domain="quydinh", confidence=0.75)
    report(
        "custom threshold=0.80, conf=0.75 → fallback",
        set(result) == set(MULTI_DOMAIN_FALLBACK),
        str(result),
    )

    # Test 9: Custom fallback collections
    custom2 = CollectionSelector(fallback_collections=["stsv", "ctdt"])
    result = custom2.select(domain="quydinh", confidence=0.30)
    report(
        "custom fallback=['stsv','ctdt']",
        set(result) == {"stsv", "ctdt"},
        str(result),
    )

    # Test 10: Confidence at exact threshold → should pass
    result = selector.select(domain="quydinh", confidence=0.65)
    report(
        "conf == threshold (0.65) → mapped collections",
        result == ["quydinh"],
        str(result),
    )

except Exception as exc:
    report("8.1 CollectionSelector", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 8.2 MultiCollectionSearch active_collections filtering
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 8.2 MultiCollectionSearch active_collections ===")

try:
    from retrieval.multi_collection_search import MultiCollectionSearch

    # Create mock HybridSearch instances
    def make_mock_hybrid(name: str) -> MagicMock:
        hybrid = MagicMock()
        hybrid.qdrant.search.return_value = [
            {
                "id": f"{name}-v1",
                "text": f"vec from {name}",
                "score": 0.8,
                "metadata": {},
            },
        ]
        hybrid.es.keyword_search.return_value = [
            {
                "id": f"{name}-k1",
                "text": f"kw from {name}",
                "score": 5.0,
                "metadata": {},
            },
        ]
        return hybrid

    searchers = [
        ("stsv", make_mock_hybrid("stsv")),
        ("quydinh", make_mock_hybrid("quydinh")),
        ("kehoach", make_mock_hybrid("kehoach")),
        ("ctdt", make_mock_hybrid("ctdt")),
    ]

    mcs = MultiCollectionSearch(searchers=searchers)
    report("MultiCollectionSearch created", True)

    # Test: search all (no active_collections)
    results = mcs.search(
        query="test",
        bge_m3_query=[0.1] * 10,
        e5_query=[0.2] * 10,
        top_k=10,
    )
    # All 4 collections searched
    for name, hybrid in searchers:
        report(
            f"All search: {name} qdrant called",
            hybrid.qdrant.search.called,
        )

    # Reset mocks
    for _, hybrid in searchers:
        hybrid.qdrant.search.reset_mock()
        hybrid.es.keyword_search.reset_mock()

    # Test: search only ["quydinh"]
    results = mcs.search(
        query="test",
        bge_m3_query=[0.1] * 10,
        e5_query=[0.2] * 10,
        top_k=10,
        active_collections=["quydinh"],
    )
    report(
        "Filtered: quydinh searched",
        searchers[1][1].qdrant.search.called,
    )
    report(
        "Filtered: stsv NOT searched",
        not searchers[0][1].qdrant.search.called,
    )
    report(
        "Filtered: kehoach NOT searched",
        not searchers[2][1].qdrant.search.called,
    )
    report(
        "Filtered: ctdt NOT searched",
        not searchers[3][1].qdrant.search.called,
    )

    # Reset mocks
    for _, hybrid in searchers:
        hybrid.qdrant.search.reset_mock()
        hybrid.es.keyword_search.reset_mock()

    # Test: search with multiple collections
    results = mcs.search(
        query="test",
        bge_m3_query=[0.1] * 10,
        e5_query=[0.2] * 10,
        top_k=10,
        active_collections=["stsv", "ctdt"],
    )
    report(
        "Multi-filter: stsv searched",
        searchers[0][1].qdrant.search.called,
    )
    report(
        "Multi-filter: ctdt searched",
        searchers[3][1].qdrant.search.called,
    )
    report(
        "Multi-filter: quydinh NOT searched",
        not searchers[1][1].qdrant.search.called,
    )

    # Reset mocks
    for _, hybrid in searchers:
        hybrid.qdrant.search.reset_mock()
        hybrid.es.keyword_search.reset_mock()

    # Test: unknown collection falls back to all
    results = mcs.search(
        query="test",
        bge_m3_query=[0.1] * 10,
        e5_query=[0.2] * 10,
        top_k=10,
        active_collections=["nonexistent"],
    )
    # Should fall back to searching all
    all_searched = all(hybrid.qdrant.search.called for _, hybrid in searchers)
    report(
        "Unknown collection → fallback to all",
        all_searched,
    )

    # Test: qdrant_stores property
    stores = mcs.qdrant_stores
    report(
        "qdrant_stores returns dict",
        isinstance(stores, dict) and len(stores) == 4,
        f"keys={list(stores.keys())}",
    )

except Exception as exc:
    report("8.2 MultiCollectionSearch", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 8.3 rag_flow integration with routing_result
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 8.3 rag_flow routing integration ===")

try:
    from pipeline.flows import rag_flow, rag_flow_stream

    mock_bge = MagicMock()
    mock_bge.embed_query.return_value = [0.1] * 1024

    mock_e5 = MagicMock()
    mock_e5.embed_query.return_value = [0.2] * 1024

    mock_searcher = MagicMock()
    mock_searcher.search.return_value = [
        {
            "text": "doc1",
            "metadata": {"title": "Test"},
            "collection": "quydinh",
        },
    ]

    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = [
        {
            "text": "doc1",
            "metadata": {"title": "Test"},
            "collection": "quydinh",
        },
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

    # Test 1: routing_result with domain passes active_collections to searcher
    result = rag_flow(
        question="Điều kiện xét học bổng?",
        history=None,
        reflector=None,
        bge_embedder=mock_bge,
        e5_embedder=mock_e5,
        searcher=mock_searcher,
        reranker=mock_reranker,
        chat_model=mock_chat,
        self_evaluator=None,
        tavily_tool=None,
        cfg=cfg,
        routing_result={
            "intent": "rag",
            "domain": "quydinh",
            "confidence": 0.90,
        },
    )

    # Check that search was called with active_collections
    search_kwargs = mock_searcher.search.call_args
    report(
        "active_collections passed to searcher",
        "active_collections" in search_kwargs.kwargs,
        f"kwargs keys: {list(search_kwargs.kwargs.keys())}",
    )
    report(
        "active_collections == ['quydinh']",
        search_kwargs.kwargs.get("active_collections") == ["quydinh"],
        str(search_kwargs.kwargs.get("active_collections")),
    )

    # Check result dict contains target_collections
    report(
        "result has target_collections",
        "target_collections" in result,
        str(result.get("target_collections")),
    )
    report(
        "target_collections == ['quydinh']",
        result.get("target_collections") == ["quydinh"],
        str(result.get("target_collections")),
    )

    # Test 2: No routing_result → active_collections is None
    mock_searcher.reset_mock()
    result2 = rag_flow(
        question="Xin chào",
        history=None,
        reflector=None,
        bge_embedder=mock_bge,
        e5_embedder=mock_e5,
        searcher=mock_searcher,
        reranker=mock_reranker,
        chat_model=mock_chat,
        self_evaluator=None,
        tavily_tool=None,
        cfg=cfg,
        routing_result=None,
    )
    search_kwargs2 = mock_searcher.search.call_args
    report(
        "No routing → active_collections is None",
        search_kwargs2.kwargs.get("active_collections") is None,
    )

    # Test 3: Low confidence → fallback collections
    mock_searcher.reset_mock()
    result3 = rag_flow(
        question="Test query",
        history=None,
        reflector=None,
        bge_embedder=mock_bge,
        e5_embedder=mock_e5,
        searcher=mock_searcher,
        reranker=mock_reranker,
        chat_model=mock_chat,
        self_evaluator=None,
        tavily_tool=None,
        cfg=cfg,
        routing_result={"intent": "rag", "domain": "ctdt", "confidence": 0.30},
    )
    search_kwargs3 = mock_searcher.search.call_args
    active = search_kwargs3.kwargs.get("active_collections")
    report(
        "Low confidence → fallback collections",
        set(active) == {"quydinh", "stsv"},
        str(active),
    )

    # Test 4: rag_flow_stream also passes active_collections
    mock_searcher.reset_mock()
    mock_chat.generate_stream.return_value = iter(["chunk1"])
    stream, sources = rag_flow_stream(
        question="Test stream",
        history=None,
        reflector=None,
        bge_embedder=mock_bge,
        e5_embedder=mock_e5,
        searcher=mock_searcher,
        reranker=mock_reranker,
        chat_model=mock_chat,
        cfg=cfg,
        routing_result={"intent": "rag", "domain": "stsv", "confidence": 0.85},
    )
    list(stream)  # consume
    search_kwargs4 = mock_searcher.search.call_args
    report(
        "Stream: active_collections passed",
        search_kwargs4.kwargs.get("active_collections") == ["stsv"],
        str(search_kwargs4.kwargs.get("active_collections")),
    )

except Exception as exc:
    report("8.3 rag_flow routing", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 8.4 Settings fields
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 8.4 Settings Phase 8 fields ===")

try:
    from config.settings import Settings

    s = Settings()
    report(
        "domain_routing_enabled exists",
        hasattr(s, "domain_routing_enabled"),
        str(s.domain_routing_enabled),
    )
    report(
        "domain_routing_enabled default True",
        s.domain_routing_enabled is True,
    )
    report(
        "domain_confidence_threshold exists",
        hasattr(s, "domain_confidence_threshold"),
        str(s.domain_confidence_threshold),
    )
    report(
        "domain_confidence_threshold default 0.65",
        s.domain_confidence_threshold == 0.65,
    )
except Exception as exc:
    report("8.4 Settings", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"Phase 8 Tests: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
print(f"{'='*60}")

if FAILED > 0:
    sys.exit(1)
