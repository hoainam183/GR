"""Regression tests for major fallback behavior in pipeline.flows."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

# Ensure src/RAG_v2 is importable in test context.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.flows import _should_prepend_profile_note, rag_flow, rag_flow_stream


def _make_doc() -> Dict[str, Any]:
    return {
        "id": "doc-1",
        "text": "Nội dung tài liệu mẫu.",
        "score": 0.9,
        "metadata": {"title": "Tài liệu mẫu", "source": "sample.md"},
        "collection": "ctdt",
    }


def _make_deps() -> Dict[str, Any]:
    reflector = MagicMock()

    bge = MagicMock()
    bge.embed_query.return_value = [0.1] * 4

    e5 = MagicMock()
    e5.embed_query.return_value = [0.2] * 4

    searcher = MagicMock()

    def _search_side_effect(**kwargs: Any) -> list[Dict[str, Any]]:
        trace = kwargs.get("trace_out")
        if isinstance(trace, dict):
            trace["filters"] = {
                "ctdt": {
                    "applied": True,
                    "matched_ids": 1,
                    "filter_desc": "major_code filter (chain[0], 1 IDs)",
                }
            }
            trace["collection_counts"] = {
                "ctdt": {"vector": 1, "keyword": 1}
            }
            trace["fusion_weights"] = {
                "vector": 0.8,
                "keyword": 0.2,
                "reason": "default",
            }
        return [_make_doc()]

    searcher.search.side_effect = _search_side_effect

    reranker = MagicMock()
    reranker.rerank.return_value = [_make_doc()]

    chat = MagicMock()
    chat.model = "test-model"
    chat.generate.return_value = "ok"
    chat.generate_stream.return_value = iter(["ok"])

    cfg = {
        "top_k": 5,
        "vector_top_k": 20,
        "keyword_top_k": 20,
        "vector_pool_k": 15,
        "keyword_pool_k": 15,
    }

    return {
        "reflector": reflector,
        "bge": bge,
        "e5": e5,
        "searcher": searcher,
        "reranker": reranker,
        "chat": chat,
        "cfg": cfg,
    }


def test_rag_flow_uses_raw_results_when_reranker_unavailable() -> None:
    deps = _make_deps()

    result = rag_flow(
        question="hoc bong",
        history=None,
        reflector=None,
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=None,
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    assert result["sources"][0]["id"] == "doc-1"
    assert result["timings_ms"]["rerank_skipped"] == 1.0
    assert result["rerank_trace"]["rerank_skipped"] is True


def test_rag_flow_stream_uses_raw_results_when_reranker_unavailable() -> None:
    deps = _make_deps()
    timings_ms: Dict[str, float] = {}
    metadata: Dict[str, Any] = {}

    stream, sources = rag_flow_stream(
        question="hoc bong",
        history=None,
        reflector=None,
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=None,
        chat_model=deps["chat"],
        cfg=deps["cfg"],
        timings_ms_out=timings_ms,
        metadata_out=metadata,
    )

    assert sources[0]["id"] == "doc-1"
    assert list(stream) == ["ok"]
    assert timings_ms["rerank_skipped"] == 1.0
    assert metadata["rerank_trace"]["rerank_skipped"] is True


def test_rag_flow_fallback_extracts_major_from_query_when_reflection_missing_entities() -> None:
    deps = _make_deps()
    question = "môn lập trình mạng của ngành IT-E6"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    result = rag_flow(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    search_kwargs = deps["searcher"].search.call_args.kwargs
    assert search_kwargs["resolved_major"] == "IT-E6"
    assert search_kwargs["query"] == "môn lập trình mạng"
    deps["bge"].embed_query.assert_called_with("môn lập trình mạng")
    deps["e5"].embed_query.assert_called_with("môn lập trình mạng")
    assert deps["reranker"].rerank.call_args.kwargs["query"] == "môn lập trình mạng"

    assert result["applied_filters"]["ctdt"]["applied"] is True


def test_rag_flow_fallback_extracts_me_gu_major_from_query() -> None:
    deps = _make_deps()
    question = "ME-GU học ngoại ngữ chính là gì"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    result = rag_flow(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    search_kwargs = deps["searcher"].search.call_args.kwargs
    assert search_kwargs["resolved_major"] == "ME-GU"
    assert search_kwargs["query"] == "học ngoại ngữ chính là gì"
    assert result["applied_filters"]["ctdt"]["applied"] is True


def test_should_prepend_profile_note_detects_new_major_codes() -> None:
    assert _should_prepend_profile_note("ME-GU học ngoại ngữ chính là gì") is False
    assert _should_prepend_profile_note("TROY IT là chương trình nào") is False
    assert _should_prepend_profile_note("MS–E3 có bao nhiêu tín chỉ") is False


def test_rag_flow_stream_fallback_extracts_major_from_user_context() -> None:
    deps = _make_deps()
    question = "môn lập trình mạng trong ngành của tôi"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    stream, _sources = rag_flow_stream(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        cfg=deps["cfg"],
        user_context={
            "major_code": "IT-E6",
            "major": "Công nghệ thông tin Việt - Nhật",
        },
    )
    list(stream)

    search_kwargs = deps["searcher"].search.call_args.kwargs
    assert search_kwargs["resolved_major"] == "IT-E6"
    assert search_kwargs["query"] == "môn lập trình mạng của tôi"
    deps["bge"].embed_query.assert_called_with("môn lập trình mạng của tôi")
    deps["e5"].embed_query.assert_called_with("môn lập trình mạng của tôi")
    assert (
        deps["reranker"].rerank.call_args.kwargs["query"]
        == "môn lập trình mạng của tôi"
    )


def test_rag_flow_uses_configured_context_budget() -> None:
    deps = _make_deps()
    question = "điều kiện tốt nghiệp"
    long_doc = {
        **_make_doc(),
        "text": "x" * 5000,
    }
    deps["reranker"].rerank.return_value = [long_doc]
    deps["cfg"] = {
        **deps["cfg"],
        "context_doc_char_limit": 2000,
        "context_total_char_budget": 12000,
        "context_list_total_char_budget": 24000,
    }

    result = rag_flow(
        question=question,
        history=None,
        reflector=None,
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    context = deps["chat"].generate.call_args.kwargs["context"]
    assert "x" * 2000 in context
    assert "x" * 2001 not in context
    assert result["context_trace"]["context_doc_char_limit"] == 2000
    assert result["context_trace"]["context_total_char_budget"] == 12000


def test_rag_flow_list_query_uses_configured_list_context_budget() -> None:
    deps = _make_deps()
    question = "liệt kê các điều kiện tốt nghiệp"
    deps["cfg"] = {
        **deps["cfg"],
        "context_doc_char_limit": 2000,
        "context_total_char_budget": 12000,
        "context_list_total_char_budget": 24000,
    }

    result = rag_flow(
        question=question,
        history=None,
        reflector=None,
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    assert result["context_trace"]["context_total_char_budget"] == 24000


def test_rag_flow_stream_exposes_search_trace_metadata() -> None:
    deps = _make_deps()
    metadata: Dict[str, Any] = {}

    stream, _sources = rag_flow_stream(
        question="điều kiện tốt nghiệp",
        history=None,
        reflector=None,
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        cfg=deps["cfg"],
        metadata_out=metadata,
    )
    list(stream)

    assert metadata["applied_filters"]["ctdt"]["applied"] is True
    assert metadata["collection_results"]["ctdt"] == {"vector": 1, "keyword": 1}
    assert metadata["fusion_weights"]["reason"] == "default"
    assert metadata["context_trace"]["context_docs_used"] == 1
    assert metadata["rerank_trace"]["rerank_candidate_count"] == 1


def test_rag_flow_keeps_major_terms_for_quydinh_only_routing() -> None:
    deps = _make_deps()
    question = "quy định đầu ra ngoại ngữ trong ngành Công nghệ thông tin Việt - Nhật (IT-E6)"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    rag_flow(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
        routing_result={
            "domain": "quydinh",
            "domains": ["quydinh"],
            "confidence": 0.85,
        },
    )

    search_kwargs = deps["searcher"].search.call_args.kwargs
    assert search_kwargs["resolved_major"] == "IT-E6"
    assert search_kwargs["query"] == question
    deps["bge"].embed_query.assert_called_with(question)
    deps["e5"].embed_query.assert_called_with(question)


def test_rag_flow_stream_keeps_major_terms_for_quydinh_only_routing() -> None:
    deps = _make_deps()
    question = "quy định đầu ra ngoại ngữ trong ngành Công nghệ thông tin Việt - Nhật (IT-E6)"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    stream, _sources = rag_flow_stream(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        cfg=deps["cfg"],
        routing_result={
            "domain": "quydinh",
            "domains": ["quydinh"],
            "confidence": 0.85,
        },
    )
    list(stream)

    search_kwargs = deps["searcher"].search.call_args.kwargs
    assert search_kwargs["resolved_major"] == "IT-E6"
    assert search_kwargs["query"] == question
    deps["bge"].embed_query.assert_called_with(question)
    deps["e5"].embed_query.assert_called_with(question)


def test_rag_flow_fallback_uses_full_history_for_major_resolution() -> None:
    deps = _make_deps()
    question = "môn lập trình mạng trong ngành của tôi"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    history = [
        {"role": "user", "content": "Em học ngành IT-E6."},
        {"role": "assistant", "content": "Mình đã ghi nhận."},
    ]
    # Add enough turns so the first major mention falls outside trimmed history.
    for i in range(10):
        role = "user" if i % 2 == 0 else "assistant"
        history.append({"role": role, "content": f"turn {i}"})

    rag_flow(
        question=question,
        history=history,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    search_kwargs = deps["searcher"].search.call_args.kwargs
    assert search_kwargs["resolved_major"] == "IT-E6"


def test_rag_flow_stream_fallback_uses_full_history_for_major_resolution() -> None:
    deps = _make_deps()
    question = "môn lập trình mạng trong ngành của tôi"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    history = [
        {"role": "user", "content": "Em học ngành IT-E6."},
        {"role": "assistant", "content": "Mình đã ghi nhận."},
    ]
    for i in range(10):
        role = "user" if i % 2 == 0 else "assistant"
        history.append({"role": role, "content": f"turn {i}"})

    stream, _sources = rag_flow_stream(
        question=question,
        history=history,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        cfg=deps["cfg"],
    )
    list(stream)

    search_kwargs = deps["searcher"].search.call_args.kwargs
    assert search_kwargs["resolved_major"] == "IT-E6"


def test_rag_flow_fallback_extracts_cohort_from_user_context() -> None:
    deps = _make_deps()
    question = "quy định về ngoại ngữ"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    rag_flow(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
        user_context={
            "cohort": "70",
        },
    )

    search_kwargs = deps["searcher"].search.call_args.kwargs
    assert search_kwargs["resolved_cohort"] == "70"


def test_rag_flow_decomposes_compare_query_by_cohort() -> None:
    deps = _make_deps()
    question = "so sánh quy định về ngoại ngữ của K70 và K67"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    rag_flow(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    search_queries = [
        call.kwargs["query"] for call in deps["searcher"].search.call_args_list
    ]
    assert any("cho K70" in q for q in search_queries)
    assert any("cho K67" in q for q in search_queries)
    assert deps["reranker"].rerank.call_args.kwargs["query"] == "quy định về ngoại ngữ"


def test_rag_flow_decomposes_compare_query_by_major() -> None:
    deps = _make_deps()
    question = "môn lập trình mạng của ngành IT-E7 và IT-E6 có gì khác nhau"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    rag_flow(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    search_calls = deps["searcher"].search.call_args_list
    search_queries = [call.kwargs["query"] for call in search_calls]
    search_majors = [call.kwargs.get("resolved_major") for call in search_calls]

    assert any("của ngành IT-E7" in q for q in search_queries)
    assert any("của ngành IT-E6" in q for q in search_queries)
    assert "IT-E7" in search_majors
    assert "IT-E6" in search_majors
    assert deps["reranker"].rerank.call_args.kwargs["query"] == "môn lập trình mạng"


def test_rag_flow_retries_without_quydinh_metadata_filter() -> None:
    deps = _make_deps()
    question = "Quy định về đánh giá điểm rèn luyện sinh viên"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    def _search_side_effect(**kwargs: Any) -> list[Dict[str, Any]]:
        disabled = kwargs.get("disable_metadata_filter_collections") or []
        if "quydinh" in disabled:
            return [_make_doc()]
        return []

    deps["searcher"].search.side_effect = _search_side_effect

    rag_flow(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
    )

    assert deps["searcher"].search.call_count >= 2
    assert any(
        "quydinh" in (call.kwargs.get("disable_metadata_filter_collections") or [])
        for call in deps["searcher"].search.call_args_list
    )


def test_rag_flow_does_not_prepend_profile_note_when_query_has_explicit_major_code() -> None:
    deps = _make_deps()
    question = "môn lập trình mạng của ngành IT-E7"
    deps["reflector"].reflect.return_value = {
        "original": question,
        "rewritten": question,
        "entities": {},
    }

    rag_flow(
        question=question,
        history=None,
        reflector=deps["reflector"],
        bge_embedder=deps["bge"],
        e5_embedder=deps["e5"],
        searcher=deps["searcher"],
        reranker=deps["reranker"],
        chat_model=deps["chat"],
        self_evaluator=None,
        tavily_tool=None,
        cfg=deps["cfg"],
        user_context={
            "major_code": "IT-E6",
            "major": "Công nghệ thông tin Việt - Nhật",
            "cohort": "67",
        },
    )

    llm_context = deps["chat"].generate.call_args.kwargs["context"]
    assert "Ngành: Công nghệ thông tin Việt - Nhật [IT-E6]" not in llm_context
