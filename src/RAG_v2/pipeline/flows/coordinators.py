"""Flow orchestrators: chitchat and RAG (classic + streaming)."""

from __future__ import annotations

import logging
import re
import time

from typing import Any, Dict, Generator, List, Optional, Set

from embedding.base import BaseEmbedder
from llm.base import BaseLLM
from llm.prompts import build_rag_messages
from llm.self_eval import SelfEvaluator
from reranking.base import BaseReranker
from retrieval.collection_selector import CollectionSelector
from retrieval.metadata_filters import (
    build_major_comparison_subqueries_for_retrieval,
    build_cohort_comparison_subqueries_for_retrieval,
    strip_cohort_comparison_scaffold_for_retrieval,
    strip_major_comparison_scaffold_for_retrieval,
    strip_major_from_query_for_retrieval,
    expand_major_in_query_for_reranking,
)

from .cache_policy import (
    _build_cache_profile,
    _should_bypass_query_cache,
    _should_cache_final_answer,
)
from .common import (
    _cfg_bool,
    _cfg_int,
    _elapsed_ms,
    _is_context_length_error,
    _log_timings,
)
from .context import (
    _format_context,
    _merge_local_and_web_context,
    _resolve_context_budget,
)
from .history import _trim_history
from .hyde import (
    _hyde_fallback_post_rerank,
    _should_trigger_hyde,
)
from .profile import _profile_note_for_generation
from .rerank_scoring import (
    _apply_score_cliff_per_collection,
    _best_explicit_rerank_score,
    _build_rerank_trace,
    _has_strong_local_evidence,
    _update_rerank_trace_after_fallback,
)
from .retrieval_helpers import (
    _build_collection_scores,
    _dedup_retrieval_candidates,
    _expand_parent_context_post_rerank,
    _expand_with_siblings_pre_rerank,
    _merge_search_trace,
    _order_with_siblings,
    _reranker_kwargs,
    _resolve_candidate_pool,
    _resolve_top_k,
    _should_strip_major_for_retrieval,
)
from .tavily import (
    _tavily_fallback_result,
    _tavily_search_context,
)
from .url_sanitize import (
    _StreamUrlSanitizer,
    _sanitize_answer_urls,
    _strip_raw_urls,
)
from .web_fallback import (
    _answer_has_no_info_signal,
    _build_answer_quality_gate,
    _build_pre_generation_web_decision,
    _is_dynamic_web_query,
    _should_lock_kehoach_route,
)


logger = logging.getLogger(__name__)

_collection_selector = CollectionSelector()

# â”€â”€ Self-eval â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# BGE reranker scores are raw logits, not probabilities. The high default avoids
# skipping self-eval for logits like 5.25 that would dwarf a probability threshold.
_SELF_EVAL_SCORE_THRESHOLD = 100.0  # run self-eval only when top score < this
_SELF_EVAL_MAX_DOCS = 2
_SELF_EVAL_DOC_CHAR_LIMIT = 600
_SELF_EVAL_TOTAL_CHAR_BUDGET = 1800


def try_query_cache(
    *,
    question: str,
    chat_model: Any,
    cfg: Dict[str, Any],
    llm_cache: Optional[Any],
    user_context: Optional[Dict[str, Any]] = None,
    routing_result: Optional[Dict[str, Any]] = None,
    timings_ms: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Pre-reflection query-cache probe (profile-scoped).

    Returns a fully-formed RAG result dict on a cache hit, else ``None``. Safe to
    call before reflection/routing: the bypass guard is text-based on the raw
    question, and the store path never caches dynamic/web/no-info answers, so an
    early probe can only ever serve a stable, previously-answered result.

    ``rag_flow``/``rag_flow_stream`` keep their own inline probe for the direct
    ``query()`` path; this lets ``query_v3``/``query_stream`` skip the reflection
    LLM round-trip + complexity routing on a hit.
    """
    if timings_ms is None:
        timings_ms = {}
    if llm_cache is None or not hasattr(llm_cache, "get_by_query"):
        return None
    if _should_bypass_query_cache(
        question=question,
        search_query=question,
        target_collections=None,
        routing_result=routing_result,
        cfg=cfg,
    ):
        timings_ms["query_cache_bypassed"] = 1.0
        return None

    cache_profile = _build_cache_profile(user_context)
    _qcached = llm_cache.get_by_query(
        question, chat_model.model, profile=cache_profile
    )
    if _qcached is None:
        return None
    if _answer_has_no_info_signal(str(_qcached.get("answer", ""))):
        timings_ms["query_cache_ignored_no_info"] = 1.0
        return None

    timings_ms["query_cache_hit"] = 1.0
    sources = _qcached["sources"]
    return {
        "question": question,
        "answer": _strip_raw_urls(_qcached["answer"]),
        "sources": sources,
        "num_sources": len(sources),
        "intent": "rag",
        "model_name": chat_model.model,
        "timings_ms": timings_ms,
        "cache_hit": True,
        "query_cache_hit": True,
        "target_collections": None,
        "collection_scores": {},
        "reflected_question": question,
        "routing_probabilities": None,
        "reflection_prompt": None,
        "llm_prompt": "(cached)",
        "applied_filters": None,
        "collection_results": None,
        "rerank_trace": {
            "cache_hit": True,
            "query_cache_hit": True,
            "rerank_candidate_count": len(sources),
            "rerank_returned_count": len(sources),
        },
        "answer_quality_gate": {
            "answer_status": "answered",
            "cache_hit": True,
        },
        "context_trace": {
            "cache_hit": True,
            "context_docs_used": len(sources),
        },
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Chitchat Flow
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def chitchat_flow(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    chat_model: BaseLLM,
) -> Dict[str, Any]:
    """Router â†’ Chat Model â†’ response (no retrieval).

    Args:
        question: The user message.
        history: Recent chat turns.
        chat_model: A :class:`~llm.base.BaseLLM` instance.

    Returns:
        Dict with ``answer``, ``sources``, ``intent``.
    """
    flow_t0 = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    step_t0 = time.perf_counter()
    trimmed = _trim_history(history)
    timings_ms["trim_history"] = _elapsed_ms(step_t0)

    step_t0 = time.perf_counter()
    answer = chat_model.generate(
        query=question,
        history=trimmed,
        mode="chitchat",
    )
    timings_ms["generate"] = _elapsed_ms(step_t0)
    timings_ms["flow_total"] = _elapsed_ms(flow_t0)

    logger.info("chitchat_flow: generated %d chars", len(answer))
    _log_timings("chitchat_flow", timings_ms)

    return {
        "question": question,
        "answer": answer,
        "sources": [],
        "num_sources": 0,
        "intent": "chitchat",
        "target_collections": [],
        "reflected_question": question,
        "model_name": chat_model.model,
        "timings_ms": timings_ms,
    }


def chitchat_flow_stream(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    chat_model: BaseLLM,
) -> Generator[str, None, None]:
    """Streaming variant of :func:`chitchat_flow`."""
    trimmed = _trim_history(history)
    yield from chat_model.generate_stream(
        query=question, history=trimmed, mode="chitchat"
    )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# RAG Flow
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def rag_flow(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    reflector: Any | None,
    bge_embedder: BaseEmbedder,
    e5_embedder: BaseEmbedder,
    searcher: Any,
    reranker: Optional[BaseReranker],
    chat_model: BaseLLM,
    self_evaluator: Optional[SelfEvaluator],
    tavily_tool: Any | None,
    cfg: Dict[str, Any],
    routing_result: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    validity_filter: Any | None = None,
    reference_resolver: Any | None = None,
    llm_cache: Optional[Any] = None,
    domain_subqueries: Optional[List[Dict[str, str]]] = None,
    reroute_reflected: Optional[Any] = None,
    pre_ref_result: Optional[Dict[str, Any]] = None,
    pre_reflection_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """Full RAG flow: Reflect â†’ Embed â†’ Search â†’ Rerank â†’ Generate â†’ SelfEval â†’ (Tavily fallback).

    Args:
        question: Raw user question.
        history: Chat history.
        reflector: ``QueryReflector`` (or *None* to skip reflection).
        bge_embedder: BGE-M3 :class:`~embedding.base.BaseEmbedder`.
        e5_embedder: E5 :class:`~embedding.base.BaseEmbedder`.
        searcher: ``MultiCollectionSearch`` instance.
        reranker: :class:`~reranking.base.BaseReranker` instance.
        chat_model: :class:`~llm.base.BaseLLM` instance.
        self_evaluator: ``SelfEvaluator`` (or *None* to skip).
        tavily_tool: ``TavilySearchTool`` (or *None* to skip).
        cfg: Pipeline config dict with retrieval params.
        user_context: Authenticated user profile (major, cohort, student_id â€¦).

    Returns:
        Dict with ``answer``, ``sources``, ``intent``, etc.
    """
    flow_t0 = time.perf_counter()
    timings_ms: Dict[str, Any] = {}

    step_t0 = time.perf_counter()
    trimmed = _trim_history(history)
    timings_ms["trim_history"] = _elapsed_ms(step_t0)
    bypass_query_cache = _should_bypass_query_cache(
        question=question,
        search_query=question,
        target_collections=None,
        routing_result=routing_result,
        cfg=cfg,
    )
    if bypass_query_cache:
        timings_ms["query_cache_bypassed"] = 1.0

    # â”€â”€ Pre-retrieval query cache (P0) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Check before reflection + retrieval to save the full ~13-25 s pipeline
    # cost for repeated identical queries.  Only fires when the cache backend
    # exposes get_by_query (LLMResponseCache with Redis).
    # Profile scope (major|cohort) so a personal answer is never served to a
    # student with a different profile â€” see _build_cache_profile.
    cache_profile = _build_cache_profile(user_context)
    if (
        llm_cache is not None
        and not bypass_query_cache
        and hasattr(llm_cache, "get_by_query")
    ):
        _qcached = llm_cache.get_by_query(
            question, chat_model.model, profile=cache_profile
        )
        if _qcached is not None:
            if _answer_has_no_info_signal(str(_qcached.get("answer", ""))):
                timings_ms["query_cache_ignored_no_info"] = 1.0
            else:
                timings_ms["query_cache_hit"] = 1.0
                timings_ms["flow_total"] = _elapsed_ms(flow_t0)
                return {
                    "question": question,
                    "answer": _strip_raw_urls(_qcached["answer"]),
                    "sources": _qcached["sources"],
                    "num_sources": len(_qcached["sources"]),
                    "intent": "rag",
                    "model_name": chat_model.model,
                    "timings_ms": timings_ms,
                    "cache_hit": True,
                    "query_cache_hit": True,
                    "target_collections": None,
                    "collection_scores": {},
                    "reflected_question": question,
                    "routing_probabilities": None,
                    "reflection_prompt": None,
                    "llm_prompt": "(cached)",
                    "applied_filters": None,
                    "collection_results": None,
                    "rerank_trace": {
                        "cache_hit": True,
                        "query_cache_hit": True,
                        "rerank_candidate_count": len(_qcached["sources"]),
                        "rerank_returned_count": len(_qcached["sources"]),
                    },
                    "answer_quality_gate": {
                        "answer_status": "answered",
                        "cache_hit": True,
                    },
                    "context_trace": {
                        "cache_hit": True,
                        "context_docs_used": len(_qcached["sources"]),
                    },
                }

    # 1. Reflection â€” rewrite query + extract entities
    search_query = question
    reflection_prompt: Optional[str] = None
    resolved_major: Optional[str] = None
    resolved_cohort: Optional[str] = None
    # Major split (auth profile vs query target) for query.profile_dependency.
    resolved_user_major: Optional[str] = None
    resolved_target_major: Optional[str] = None
    if pre_ref_result is not None:
        # Use pre-computed reflection from upstream (query_v3/query_stream)
        search_query = pre_ref_result.get("rewritten", question)
        reflection_prompt = pre_ref_result.get("prompt")
        entities = pre_ref_result.get("entities") or {}
        resolved_major = entities.get("major_code") or entities.get(
            "major_name"
        )
        resolved_user_major = entities.get("user_major_code")
        resolved_target_major = entities.get("target_major_code")
        cohort_entity = entities.get("cohort")
        if cohort_entity is not None:
            resolved_cohort = str(cohort_entity).strip() or None
        if pre_reflection_ms is not None:
            timings_ms["reflection"] = pre_reflection_ms
        logger.info(
            "Using pre-reflected query: %r | major: %s | cohort: %s",
            search_query[:80],
            resolved_major,
            resolved_cohort,
        )
    elif reflector is not None:
        reflection_t0 = time.perf_counter()
        try:
            ref_result = reflector.reflect(
                question,
                chat_history=trimmed,
                user_context=user_context,
                user_profile=user_context,
            )
            search_query = ref_result.get("rewritten", question)
            reflection_prompt = ref_result.get("prompt")
            entities = ref_result.get("entities") or {}
            resolved_major = entities.get("major_code") or entities.get(
                "major_name"
            )
            resolved_user_major = entities.get("user_major_code")
            resolved_target_major = entities.get("target_major_code")
            cohort_entity = entities.get("cohort")
            if cohort_entity is not None:
                resolved_cohort = str(cohort_entity).strip() or None
            logger.info(
                "Reflected query: %r | major: %s | cohort: %s",
                search_query[:80],
                resolved_major,
                resolved_cohort,
            )
        except Exception:
            logger.warning(
                "Reflection failed, using original query", exc_info=True
            )
        timings_ms["reflection"] = _elapsed_ms(reflection_t0)

    # Deterministic fallback: always recover major/cohort metadata even if
    # reflection fails or does not return entities.
    if not resolved_major or not resolved_cohort:
        from query.reflection import _extract_entities  # noqa: PLC0415

        fallback_entities = _extract_entities(
            question,
            user_context=user_context,
            history=history,
        )
        if not resolved_major:
            resolved_major = fallback_entities.get(
                "major_code"
            ) or fallback_entities.get("major_name")
        if not resolved_cohort:
            cohort_entity = fallback_entities.get("cohort")
            if cohort_entity is not None:
                resolved_cohort = str(cohort_entity).strip() or None
        if not resolved_user_major:
            resolved_user_major = fallback_entities.get("user_major_code")
        if not resolved_target_major:
            resolved_target_major = fallback_entities.get("target_major_code")

        if resolved_major:
            logger.info("Major fallback resolved: %s", resolved_major)
        if resolved_cohort:
            logger.info("Cohort fallback resolved: %s", resolved_cohort)

    # Re-route on the reflected (standalone) query so a topic-heavy
    # conversation cannot bleed into domain selection. The reflector has
    # already baked any legitimate follow-up context into search_query, so
    # routing it history-free is bleed-free. See RAGPipeline._reroute_reflected.
    # Must run BEFORE effective_major / collection selection (both read
    # routing_result).
    if reroute_reflected is not None:
        reroute_t0 = time.perf_counter()
        try:
            routing_result = reroute_reflected(search_query, routing_result)
        except Exception:
            logger.warning(
                "Reflected-query reroute failed; keeping pipeline routing",
                exc_info=True,
            )
        timings_ms["reflected_reroute"] = _elapsed_ms(reroute_t0)

    retrieval_query = search_query

    # Drop the major metadata filter for topics whose answer does not depend on the
    # program (e.g. há»c bá»•ng) so universal answers are not narrowed to one major.
    # After profile_dependency refactor, we simply use the resolved major.
    # If the major was explicitly extracted from the query or user profile, we use it for retrieval.
    retrieval_major = resolved_major

    # 2. Collection-aware routing (Phase 8 â€” Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    routing_probabilities: Optional[Dict[str, Any]] = None
    if cfg.get("find_all", False):
        routing_t0 = time.perf_counter()
        target_collections = list(cfg.get("collections") or [])
        routing_probabilities = (
            routing_result.get("probabilities") if routing_result else None
        )
        logger.info(
            "find_all=true â†’ bypassing routing, searching all collections: %s",
            target_collections,
        )
        timings_ms["collection_routing"] = _elapsed_ms(routing_t0)
        timings_ms["find_all_override"] = 1.0
    elif routing_result:
        routing_t0 = time.perf_counter()
        domain = routing_result.get("domain")
        domains = routing_result.get("domains") or ([domain] if domain else [])
        confidence = routing_result.get("confidence", 0.0)
        target_collections = _collection_selector.select(
            domain=domain,
            confidence=confidence,
            domains=domains,
            query=search_query,
            probabilities=routing_result.get("probabilities"),
        )
        if _should_lock_kehoach_route(
            question=question,
            search_query=search_query,
            routing_result=routing_result,
        ):
            target_collections = ["kehoach"]
            timings_ms["kehoach_route_locked"] = 1.0
            logger.info(
                "KeHoach freshness route locked despite conf=%.3f",
                confidence,
            )
        routing_probabilities = routing_result.get("probabilities")
        logger.info(
            "Domains: %s (conf=%.3f) â†’ searching collections: %s",
            domains,
            confidence,
            target_collections,
        )
        timings_ms["collection_routing"] = _elapsed_ms(routing_t0)

    if _should_strip_major_for_retrieval(
        resolved_major=resolved_major,
        target_collections=target_collections,
    ):
        normalized_query = strip_major_from_query_for_retrieval(
            search_query,
            resolved_major=resolved_major,
        )
        if normalized_query != search_query:
            logger.info(
                "Retrieval query normalized: %r -> %r (major=%s)",
                search_query[:80],
                normalized_query[:80],
                resolved_major,
            )
            retrieval_query = normalized_query

    collection_scores = _build_collection_scores(
        all_collections=cfg.get("collections"),
        target_collections=target_collections,
        routing_result=routing_result,
    )
    dynamic_web_query = _is_dynamic_web_query(
        question=question,
        search_query=search_query,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
    )
    if dynamic_web_query:
        timings_ms["dynamic_web_query"] = 1.0

    top_k_value = _resolve_top_k(cfg.get("top_k", 5), question)
    # C4: Expand candidate pool when routing confidence is low
    routing_confidence = float(
        routing_result.get("confidence", 1.0) if routing_result else 1.0
    )
    raw_candidate_k = _resolve_candidate_pool(
        cfg, top_k_value, routing_confidence
    )
    major_compare_plan = build_major_comparison_subqueries_for_retrieval(
        search_query
    )
    compare_subqueries: List[str] = []
    if not major_compare_plan:
        compare_subqueries = build_cohort_comparison_subqueries_for_retrieval(
            retrieval_query
        )

    if major_compare_plan:
        logger.info(
            "Major comparison retrieval decomposition: %s",
            [q for q, _ in major_compare_plan],
        )
    if compare_subqueries:
        logger.info(
            "Comparison retrieval decomposition: %s",
            compare_subqueries,
        )

    rerank_query = retrieval_query
    if major_compare_plan:
        stripped = strip_major_comparison_scaffold_for_retrieval(search_query)
        if len(stripped.split()) >= 2:
            rerank_query = stripped
    elif compare_subqueries:
        stripped = strip_cohort_comparison_scaffold_for_retrieval(
            retrieval_query
        )
        if len(stripped.split()) >= 2:
            rerank_query = stripped

    # 3. Embed + 4. Hybrid search with metadata pre-filtering
    # resolved_major already set by reflection above.

    search_trace: Dict[str, Any] = {}

    def _search_once(
        local_query: str,
        local_active_collections: Optional[List[str]],
        *,
        local_resolved_major: Optional[str] = None,
        use_outer_resolved_major: bool = True,
        local_disable_metadata_filter_collections: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        embed_t0 = time.perf_counter()
        bge_vec = bge_embedder.embed_query(local_query)
        timings_ms["embed_bge"] = round(
            timings_ms.get("embed_bge", 0.0) + _elapsed_ms(embed_t0),
            2,
        )

        embed_t0 = time.perf_counter()
        e5_vec = e5_embedder.embed_query(local_query)
        timings_ms["embed_e5"] = round(
            timings_ms.get("embed_e5", 0.0) + _elapsed_ms(embed_t0),
            2,
        )

        trace_piece: Dict[str, Any] = {}
        search_t0 = time.perf_counter()
        effective_resolved_major = (
            retrieval_major
            if use_outer_resolved_major
            else local_resolved_major
        )
        result_rows = searcher.search(
            query=local_query,
            bge_m3_query=bge_vec,
            e5_query=e5_vec,
            top_k=raw_candidate_k,
            vector_top_k=cfg.get("vector_top_k", 20),
            keyword_top_k=cfg.get("keyword_top_k", 20),
            vector_pool_k=cfg.get("vector_pool_k", 30),
            keyword_pool_k=cfg.get("keyword_pool_k", 30),
            active_collections=local_active_collections,
            resolved_major=effective_resolved_major,
            resolved_cohort=resolved_cohort,
            disable_metadata_filter_collections=local_disable_metadata_filter_collections,
            trace_out=trace_piece,
            fusion_mode=cfg.get("fusion_mode", "rrf"),
        )
        timings_ms["search"] = round(
            timings_ms.get("search", 0.0) + _elapsed_ms(search_t0),
            2,
        )
        _merge_search_trace(search_trace, trace_piece)
        return result_rows

    raw_results_buffer: List[Dict[str, Any]] = []
    if domain_subqueries:
        # Decomposed multi-domain retrieval: each sub-query targets its own collection.
        # Uses the reflected/stripped query for reranking (set above as rerank_query).
        logger.info(
            "Decomposed retrieval: %d sub-queries",
            len(domain_subqueries),
        )
        for sq in domain_subqueries:
            sq_query = sq.get("query", retrieval_query)
            sq_collection = sq.get("collection", "")
            sq_collections: Optional[List[str]] = (
                [sq_collection] if sq_collection else target_collections
            )
            raw_results_buffer.extend(_search_once(sq_query, sq_collections))
    elif major_compare_plan:
        for subquery, subquery_major in major_compare_plan:
            raw_results_buffer.extend(
                _search_once(
                    subquery,
                    target_collections,
                    local_resolved_major=subquery_major,
                    use_outer_resolved_major=False,
                )
            )
    else:
        primary_queries = compare_subqueries or [retrieval_query]
        for subquery in primary_queries:
            raw_results_buffer.extend(
                _search_once(subquery, target_collections)
            )
    raw_results = _dedup_retrieval_candidates(
        raw_results_buffer,
        top_k=raw_candidate_k,
    )

    if not raw_results and domain_subqueries:
        # Fallback: retry with the reflected query against all relevant collections
        logger.info(
            "Decomposed sub-queries returned no candidates; retrying with reflected query."
        )
        raw_results = _dedup_retrieval_candidates(
            _search_once(retrieval_query, target_collections),
            top_k=raw_candidate_k,
        )

    if not raw_results and (compare_subqueries or major_compare_plan):
        logger.info(
            "Comparison subqueries returned no candidates; retrying original query."
        )
        fallback_compare_query = (
            search_query if major_compare_plan else retrieval_query
        )
        raw_results = _dedup_retrieval_candidates(
            _search_once(
                fallback_compare_query,
                target_collections,
                use_outer_resolved_major=not major_compare_plan,
            ),
            top_k=raw_candidate_k,
        )

    if not raw_results:
        logger.info(
            "No candidates; retrying with quydinh metadata filter disabled."
        )
        raw_results = _dedup_retrieval_candidates(
            _search_once(
                retrieval_query,
                target_collections,
                local_disable_metadata_filter_collections=["quydinh"],
            ),
            top_k=raw_candidate_k,
        )
        if not raw_results and target_collections is not None:
            raw_results = _dedup_retrieval_candidates(
                _search_once(
                    retrieval_query,
                    None,
                    local_disable_metadata_filter_collections=["quydinh"],
                ),
                top_k=raw_candidate_k,
            )

    if not raw_results and target_collections is not None:
        logger.info(
            "No candidates for routed collections; retrying all collections."
        )
        raw_results = _dedup_retrieval_candidates(
            _search_once(retrieval_query, None),
            top_k=raw_candidate_k,
        )

    if not raw_results and (compare_subqueries or major_compare_plan):
        compare_source_query = (
            search_query if major_compare_plan else retrieval_query
        )
        relaxed_query = (
            strip_major_comparison_scaffold_for_retrieval(search_query)
            if major_compare_plan
            else strip_cohort_comparison_scaffold_for_retrieval(retrieval_query)
        )
        if relaxed_query != compare_source_query:
            logger.info(
                "No candidates; retrying relaxed comparison topic query: %r",
                relaxed_query[:80],
            )
            raw_results = _dedup_retrieval_candidates(
                _search_once(
                    relaxed_query,
                    target_collections,
                    use_outer_resolved_major=not major_compare_plan,
                ),
                top_k=raw_candidate_k,
            )
            if not raw_results and target_collections is not None:
                raw_results = _dedup_retrieval_candidates(
                    _search_once(
                        relaxed_query,
                        None,
                        use_outer_resolved_major=not major_compare_plan,
                    ),
                    top_k=raw_candidate_k,
                )

    logger.info("Retrieved %d raw candidates", len(raw_results))

    # 4.5 Sibling chunk expansion (C1) â€” BEFORE rerank
    if _cfg_bool(cfg, "sibling_expansion_enabled", False) and raw_results:
        expansion_t0 = time.perf_counter()
        pre_expansion_count = len(raw_results)
        raw_results = _expand_with_siblings_pre_rerank(
            candidates=raw_results,
            searcher=searcher,
            expand_top_n=3,
            window=1,
            max_expansion=6,
        )
        timings_ms["sibling_expansion"] = _elapsed_ms(expansion_t0)
        siblings_added = len(raw_results) - pre_expansion_count
        timings_ms["sibling_expansion_hit"] = 1.0 if siblings_added > 0 else 0.0
        timings_ms["sibling_expansion_count"] = float(siblings_added)

    # 5. Rerank
    rerank_t0 = time.perf_counter()

    rerank_query = expand_major_in_query_for_reranking(
        rerank_query, resolved_major
    )
    if reranker is not None:
        reranked = reranker.rerank(
            query=rerank_query,
            documents=raw_results,
            top_k=top_k_value,
            **_reranker_kwargs(cfg, top_k_value),
        )
        timings_ms["rerank"] = _elapsed_ms(rerank_t0)
        rerank_trace = _build_rerank_trace(
            reranker=reranker,
            candidate_count=len(raw_results),
            reranked=reranked,
        )
        logger.info("Reranked to %d documents", len(reranked))

        # Fallback: if the cross-encoder threshold dropped all candidates but the
        # vector/hybrid stage found good matches (e.g. the reflected query drifted
        # from the original intent), retry with the original question. This prevents
        # an issue where reflection adds speculative terms that reduce cross-encoder
        # scores below the threshold for otherwise topically-relevant documents.
        # Also trigger when all surviving docs have negative scores (only table-docs
        # passed through the relaxed table_score_threshold but no regular content matched).
        _best_rerank_score = _best_explicit_rerank_score(reranked)
        _rerank_quality_ok = bool(reranked) and (
            _best_rerank_score is None or _best_rerank_score >= 0.0
        )
        if raw_results and not _rerank_quality_ok:
            fallback_reason = (
                "empty_rerank" if not reranked else "negative_rerank_score"
            )
            logger.info(
                "Reranker gave no positive-score candidates (best=%.3f, n=%d). "
                "Retrying rerank with original question.",
                (
                    _best_rerank_score
                    if _best_rerank_score is not None
                    else -999.0
                ),
                len(raw_results),
            )
            reranked = reranker.rerank(
                query=question,
                documents=raw_results,
                top_k=top_k_value,
                **_reranker_kwargs(cfg, top_k_value),
            )
            timings_ms["rerank_fallback"] = 1.0
            retry_best_score = _best_explicit_rerank_score(reranked)
            if not reranked or (
                retry_best_score is not None and retry_best_score < 0.0
            ):
                fallback_reason = (
                    "empty_rerank" if not reranked else "negative_rerank_score"
                )
                # Last resort: use raw top-k by fusion score without threshold.
                logger.info(
                    "Reranker still no positive candidates after fallback. "
                    "Using top-%d raw candidates by fusion score.",
                    top_k_value,
                )
                reranked = sorted(
                    raw_results, key=lambda d: d.get("score", 0.0), reverse=True
                )[:top_k_value]
                timings_ms["rerank_raw_fallback"] = 1.0
            rerank_trace = _update_rerank_trace_after_fallback(
                rerank_trace,
                candidate_count=len(raw_results),
                reranked=reranked,
                fallback_reason=fallback_reason,
                raw_fallback=bool(timings_ms.get("rerank_raw_fallback")),
            )
    else:
        reranked = sorted(
            raw_results, key=lambda d: d.get("score", 0.0), reverse=True
        )[:top_k_value]
        timings_ms["rerank_skipped"] = 1.0
        rerank_trace = _build_rerank_trace(
            reranker=None,
            candidate_count=len(raw_results),
            reranked=reranked,
        )
        rerank_trace["rerank_skipped"] = True
        logger.warning(
            "Reranker unavailable; using top-%d raw candidates by fusion score.",
            top_k_value,
        )

    # 5.05 HyDE post-rerank fallback â€” second-pass retrieval for low-recall
    if _should_trigger_hyde(reranked, reranker, cfg):
        reranked = _hyde_fallback_post_rerank(
            reranked=reranked,
            raw_candidate_k=raw_candidate_k,
            retrieval_query=retrieval_query,
            rerank_query=rerank_query,
            top_k_value=top_k_value,
            bge_embedder=bge_embedder,
            e5_embedder=e5_embedder,
            searcher=searcher,
            reranker=reranker,
            chat_model=chat_model,
            target_collections=target_collections,
            resolved_major=resolved_major,
            resolved_cohort=resolved_cohort,
            cfg=cfg,
            timings_ms=timings_ms,
        )

    # 5.1 Document Validity Filtering
    if validity_filter is not None:
        valid_t0 = time.perf_counter()
        reranked = validity_filter.filter(reranked)
        timings_ms["validity_filter"] = _elapsed_ms(valid_t0)

    # 5.2 Cross-Reference Resolution
    if reference_resolver is not None:
        resolve_t0 = time.perf_counter()
        reranked = reference_resolver.resolve(reranked, query=retrieval_query)
        timings_ms["reference_resolver"] = _elapsed_ms(resolve_t0)

    # 5.3 Per-collection Score Cliff (B1)
    if _cfg_bool(cfg, "score_cliff_enabled", False):
        pre_cliff_count = len(reranked)
        reranked = _apply_score_cliff_per_collection(reranked)
        cliff_dropped = pre_cliff_count - len(reranked)
        timings_ms["cliff_triggered"] = 1.0 if cliff_dropped > 0 else 0.0
        timings_ms["cliff_dropped_count"] = float(cliff_dropped)

    # 5.4 Parent context expansion (C5) â€” fetch parent by ID after rerank
    parent_t0 = time.perf_counter()
    reranked = _expand_parent_context_post_rerank(reranked, cfg)
    timings_ms["parent_expansion"] = _elapsed_ms(parent_t0)

    # â”€â”€ LLM Response Cache Check (Phase 2) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    web_fallback_used = False
    pre_web_fallback_used = False
    web_fallback_sources: List[Dict[str, Any]] = []
    web_context_override = ""
    pre_web_decision = _build_pre_generation_web_decision(
        question=question,
        search_query=search_query,
        reranked=reranked,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
        low_retrieval_confidence=bool(timings_ms.get("rerank_raw_fallback")),
    )
    web_fallback_query = str(
        pre_web_decision.get("web_search_query") or search_query
    )
    pre_web_fallback_reasons = list(pre_web_decision.get("reasons") or [])
    if pre_web_decision.get("freshness_query"):
        timings_ms["freshness_query"] = 1.0
        if (
            pre_web_decision["should_web_search"]
            and "freshness_query" not in pre_web_fallback_reasons
        ):
            pre_web_fallback_reasons.append("freshness_query")
    if pre_web_decision["should_web_search"]:
        timings_ms["web_fallback_requested"] = 1.0
        if cfg.get("tavily_fallback_enabled", False):
            search_info = _tavily_search_context(
                query=web_fallback_query,
                tavily_tool=tavily_tool,
                max_results=_cfg_int(cfg, "tavily_max_results", 3),
                search_depth=str(
                    cfg.get("tavily_search_depth", "basic") or "basic"
                ),
                result_count=_cfg_int(cfg, "tavily_web_result_count", 3),
                content_char_limit=_cfg_int(
                    cfg, "tavily_web_content_char_limit", 1500
                ),
            )
            timings_ms.update(search_info["timings"])
            web_fallback_sources = list(search_info.get("sources") or [])
            if search_info.get("used"):
                web_fallback_used = True
                pre_web_fallback_used = True
                timings_ms["web_fallback_used"] = 1.0
                web_context_override = str(search_info.get("context") or "")
                if web_fallback_sources:
                    reranked = reranked + web_fallback_sources
        else:
            timings_ms["tavily_skipped"] = 1.0

    if (
        llm_cache is not None
        and not dynamic_web_query
        and not pre_web_fallback_reasons
    ):
        doc_ids = [str(doc.get("id", "")) for doc in reranked if doc.get("id")]
        cached = llm_cache.get(
            question, doc_ids, chat_model.model, profile=cache_profile
        )
        if cached is not None:
            if _answer_has_no_info_signal(str(cached.get("answer", ""))):
                timings_ms["llm_cache_ignored_no_info"] = 1.0
            else:
                logger.info("LLM cache HIT for query: %r", question[:80])
                timings_ms["llm_cache_hit"] = 1.0
                timings_ms["flow_total"] = _elapsed_ms(flow_t0)
                return {
                    "question": question,
                    "answer": _strip_raw_urls(cached["answer"]),
                    "sources": cached["sources"],
                    "num_sources": len(cached["sources"]),
                    "intent": "rag",
                    "model_name": chat_model.model,
                    "target_collections": target_collections,
                    "collection_scores": _build_collection_scores(
                        all_collections=cfg.get("collections"),
                        target_collections=target_collections,
                        routing_result=routing_result,
                    ),
                    "reflected_question": search_query,
                    "timings_ms": timings_ms,
                    "routing_probabilities": routing_probabilities,
                    "reflection_prompt": reflection_prompt,
                    "llm_prompt": "(cached)",
                    "applied_filters": search_trace.get("filters"),
                    "collection_results": search_trace.get("collection_counts"),
                    "rerank_trace": {
                        **rerank_trace,
                        "cache_hit": True,
                        "llm_cache_hit": True,
                    },
                    "answer_quality_gate": {
                        "answer_status": "answered",
                        "cache_hit": True,
                    },
                    "context_trace": {
                        "cache_hit": True,
                        "context_docs_used": len(cached["sources"]),
                    },
                    "cache_hit": True,
                }

    # 6. Format context â€” inject profile so user facts survive trimming.
    #    Priority 1: use authenticated user_context (precise, always present).
    #    Priority 2: fall back to regex scan of history.
    context_t0 = time.perf_counter()
    # For list queries (top_k was scaled up), use a larger char budget so we
    # don't truncate the extra docs before passing them to the LLM.
    context_doc_limit, context_char_budget = _resolve_context_budget(
        cfg,
        top_k_value=top_k_value,
    )
    context_trace: Dict[str, Any] = {}
    context_documents = reranked
    if web_context_override:
        context_documents = [
            doc
            for doc in reranked
            if str(doc.get("collection") or "").lower() != "web"
        ]
    # C2: Reorder so siblings appear after their parents
    if _cfg_bool(cfg, "sibling_expansion_enabled", False):
        context_documents = _order_with_siblings(context_documents)
    context = _format_context(
        context_documents,
        per_doc_char_limit=context_doc_limit,
        total_char_budget=context_char_budget,
        sibling_per_doc_limit=_cfg_int(cfg, "sibling_per_doc_limit", 800),
        trace_out=context_trace,
    )
    context = _merge_local_and_web_context(context, web_context_override)
    profile_note = _profile_note_for_generation(
        question,
        search_query,
        routing_result,
        resolved_major,
        resolved_cohort,
        resolved_user_major,
        resolved_target_major,
        user_context,
        history,
    )
    full_context = (
        f"{profile_note}\n\n---\n\n{context}" if profile_note else context
    )
    context_trace["full_context_chars"] = len(full_context)
    timings_ms["format_context"] = _elapsed_ms(context_t0)

    # 7. Generate answer with context-length error recovery
    # Capture the prompt that will be sent to the LLM (for trace/debug).
    try:
        llm_messages = build_rag_messages(question, full_context, trimmed)
        llm_prompt_str: Optional[str] = "\n\n".join(
            f"[{m['role'].upper()}]\n{m['content']}" for m in llm_messages
        )
    except Exception:
        llm_prompt_str = None

    generate_t0 = time.perf_counter()
    recovered = False
    try:
        answer = chat_model.generate(
            query=question,
            context=full_context,
            history=trimmed,
            mode="rag",
        )
    except Exception as exc:
        if not _is_context_length_error(exc):
            raise
        logger.warning(
            "Context too long, retrying with reduced budget",
            exc_info=True,
        )
        reduced_context = _format_context(
            reranked[:2],
            per_doc_char_limit=600,
            total_char_budget=1500,
        )
        trimmed = _trim_history(history, limit=3)
        try:
            answer = chat_model.generate(
                query=question,
                context=reduced_context,
                history=trimmed,
                mode="rag",
            )
            recovered = True
        except Exception as retry_exc:
            if _is_context_length_error(retry_exc):
                raise RuntimeError(
                    "Ngá»¯ cáº£nh há»™i thoáº¡i Ä‘ang quÃ¡ dÃ i. "
                    "Vui lÃ²ng báº¯t Ä‘áº§u phiÃªn má»›i hoáº·c há»i ngáº¯n gá»n hÆ¡n."
                ) from retry_exc
            raise
    if recovered:
        timings_ms["context_recovery"] = 1.0
    timings_ms["generate"] = _elapsed_ms(generate_t0)

    # 8. Self-evaluation â€” only when retrieval confidence is low.
    # Saves 11-20s per query when retrieval already found a relevant chunk.
    top_score = 0.0
    if reranked:
        try:
            top_score = float(reranked[0].get("score", 0.0))
        except (TypeError, ValueError):
            top_score = 0.0
    self_eval_threshold = cfg.get(
        "self_eval_min_top_score",
        _SELF_EVAL_SCORE_THRESHOLD,
    )
    run_self_eval = (
        self_evaluator is not None and top_score < self_eval_threshold
    )
    eval_result: Optional[Dict[str, Any]] = None
    if run_self_eval and self_evaluator is not None:
        self_eval_t0 = time.perf_counter()
        try:
            eval_context = _format_context(
                reranked[:_SELF_EVAL_MAX_DOCS],
                per_doc_char_limit=_SELF_EVAL_DOC_CHAR_LIMIT,
                total_char_budget=_SELF_EVAL_TOTAL_CHAR_BUDGET,
            )
            eval_result = self_evaluator.evaluate(
                query=question, context=eval_context, response=answer
            )
            timings_ms["self_eval"] = _elapsed_ms(self_eval_t0)
        except Exception:
            timings_ms["self_eval"] = _elapsed_ms(self_eval_t0)
            logger.warning(
                "Self-evaluation error, keeping original answer", exc_info=True
            )
    elif self_evaluator is not None:
        timings_ms["self_eval_skipped"] = 1.0
        logger.debug(
            "Self-eval skipped: top_score=%.3f >= threshold=%.3f",
            top_score,
            self_eval_threshold,
        )

    gate_t0 = time.perf_counter()
    answer_quality_gate = _build_answer_quality_gate(
        question=question,
        search_query=search_query,
        answer=answer,
        reranked=reranked,
        target_collections=target_collections,
        routing_result=routing_result,
        eval_result=eval_result,
        cfg=cfg,
        pre_web_fallback_used=pre_web_fallback_used,
    )
    timings_ms["answer_quality_gate"] = _elapsed_ms(gate_t0)

    local_context_for_fallback = (
        full_context
        if context_trace.get("context_docs_used", 0) and full_context.strip()
        else ""
    )
    strong_local_evidence = _has_strong_local_evidence(
        reranked,
        local_context_for_fallback,
        cfg,
    )
    can_retry_with_local_evidence = bool(
        answer_quality_gate["should_web_search"]
        and strong_local_evidence
        and not answer_quality_gate.get("no_sources")
        and not answer_quality_gate.get("dynamic_query")
        and not answer_quality_gate.get("freshness_query")
        and not pre_web_fallback_used
    )
    if can_retry_with_local_evidence:
        retry_t0 = time.perf_counter()
        try:
            answer = chat_model.generate(
                query=question,
                context=local_context_for_fallback,
                history=trimmed,
                mode="rag",
            )
            timings_ms["local_evidence_retry_generate"] = _elapsed_ms(retry_t0)
            timings_ms["local_evidence_retry_used"] = 1.0
            retry_gate_t0 = time.perf_counter()
            answer_quality_gate = _build_answer_quality_gate(
                question=question,
                search_query=search_query,
                answer=answer,
                reranked=reranked,
                target_collections=target_collections,
                routing_result=routing_result,
                eval_result=None,
                cfg=cfg,
                pre_web_fallback_used=pre_web_fallback_used,
            )
            timings_ms["answer_quality_gate_after_local_retry"] = _elapsed_ms(
                retry_gate_t0
            )
            answer_quality_gate["local_evidence_retry_used"] = True
            logger.info(
                "Retried generation with strong local evidence before Tavily"
            )
        except Exception:
            timings_ms["local_evidence_retry_failed"] = 1.0
            logger.warning(
                "Local evidence retry failed, continuing to web fallback decision",
                exc_info=True,
            )
    else:
        answer_quality_gate["local_evidence_retry_used"] = False

    answer_quality_gate["strong_local_evidence"] = strong_local_evidence
    answer_quality_gate["pre_generation_reasons"] = pre_web_fallback_reasons
    answer_quality_gate["pre_generation_web_used"] = pre_web_fallback_used
    answer_quality_gate["pre_generation_freshness_query"] = bool(
        pre_web_decision.get("freshness_query")
    )
    web_fallback_query = str(
        answer_quality_gate.get("web_search_query")
        or web_fallback_query
        or search_query
    )
    timings_ms[f"answer_status_{answer_quality_gate['answer_status']}"] = 1.0
    if answer_quality_gate["should_web_search"]:
        timings_ms["web_fallback_requested"] = 1.0
        logger.info(
            "AnswerQualityGate requested web fallback: status=%s reasons=%s",
            answer_quality_gate["answer_status"],
            answer_quality_gate["reasons"],
        )

    if answer_quality_gate["should_web_search"]:
        if cfg.get("tavily_fallback_enabled", False):
            try:
                tavily_max_results = int(cfg.get("tavily_max_results", 3) or 3)
            except (TypeError, ValueError):
                tavily_max_results = 3
            fallback_result = _tavily_fallback_result(
                question=question,
                answer=answer,
                tavily_tool=tavily_tool,
                chat_model=chat_model,
                history=trimmed,
                max_results=tavily_max_results,
                search_depth=str(
                    cfg.get("tavily_search_depth", "basic") or "basic"
                ),
                search_query=web_fallback_query,
                local_context=local_context_for_fallback or None,
                result_count=_cfg_int(cfg, "tavily_web_result_count", 3),
                content_char_limit=_cfg_int(
                    cfg, "tavily_web_content_char_limit", 1500
                ),
            )
            timings_ms.update(fallback_result["timings"])
            if fallback_result["used"]:
                answer = str(fallback_result["answer"])
                web_fallback_used = True
                timings_ms["web_fallback_used"] = 1.0
                web_fallback_sources = list(
                    fallback_result.get("sources") or []
                )
                if web_fallback_sources:
                    # Intentional prepend: the answer was replaced with web-based content,
                    # so web sources ARE the primary evidence for the new answer.
                    # Contrast with pre-gen path (append) where local docs still contribute.
                    reranked = web_fallback_sources + reranked
        else:
            timings_ms["tavily_skipped"] = 1.0
            logger.info(
                "AnswerQualityGate requested web fallback, but Tavily is disabled"
            )

    cache_final_answer = _should_cache_final_answer(
        answer=answer,
        answer_quality_gate=answer_quality_gate,
        dynamic_web_query=dynamic_web_query,
        pre_web_fallback_used=pre_web_fallback_used,
        web_fallback_used=web_fallback_used,
        web_fallback_reasons=pre_web_fallback_reasons,
    )
    # Note: Kehoach links are displayed via the frontend's source cards,
    # not appended to answer text, for better UX.
    # Previously appended with: answer = _append_kehoach_source_links(answer, reranked)
    if llm_cache is not None and cache_final_answer:
        doc_ids = [str(doc.get("id", "")) for doc in reranked if doc.get("id")]
        llm_cache.put(
            question,
            doc_ids,
            chat_model.model,
            answer,
            reranked,
            profile=cache_profile,
        )

    if (
        llm_cache is not None
        and hasattr(llm_cache, "put_by_query")
        and cache_final_answer
        and not web_fallback_used
        and not dynamic_web_query
        and not answer_quality_gate["should_web_search"]
    ):
        llm_cache.put_by_query(
            question, chat_model.model, answer, reranked, profile=cache_profile
        )
    timings_ms["retrieval_total"] = round(
        timings_ms.get("embed_bge", 0.0)
        + timings_ms.get("embed_e5", 0.0)
        + timings_ms.get("search", 0.0)
        + timings_ms.get("rerank", 0.0)
        + timings_ms.get("format_context", 0.0),
        2,
    )
    timings_ms["flow_total"] = _elapsed_ms(flow_t0)
    _log_timings("rag_flow", timings_ms)

    return {
        "question": question,
        "answer": _strip_raw_urls(answer),
        "sources": reranked,
        "num_sources": len(reranked),
        "intent": "rag",
        "model_name": chat_model.model,
        "target_collections": target_collections,
        "collection_scores": collection_scores,
        "reflected_question": search_query,
        "timings_ms": timings_ms,
        # Extended trace fields
        "routing_probabilities": routing_probabilities,
        "reflection_prompt": reflection_prompt,
        "llm_prompt": llm_prompt_str,
        "applied_filters": search_trace.get("filters"),
        "collection_results": search_trace.get("collection_counts"),
        "fusion_weights": search_trace.get("fusion_weights"),
        "context_trace": context_trace,
        "rerank_trace": rerank_trace,
        "answer_status": answer_quality_gate["answer_status"],
        "answer_quality_gate": answer_quality_gate,
        "tools_used": (
            ["tavily_search"] if timings_ms.get("tavily_search") else []
        ),
        "tool_calls": (
            [
                {
                    "tool": "tavily_search",
                    "args": {
                        "query": web_fallback_query,
                        "include_domains": "HUST_OFFICIAL_DOMAINS",
                    },
                    "result": "used" if web_fallback_used else "searched",
                    "iteration": 0,
                    "latency_ms": timings_ms.get("tavily_search"),
                }
            ]
            if timings_ms.get("tavily_search")
            else []
        ),
    }


def _chunk_cached_answer(
    answer: str, size: int = 60
) -> Generator[str, None, None]:
    """Split a cached answer into fixed-width pieces for progressive SSE rendering.

    A cache hit otherwise yields the whole answer as one chunk, which renders
    instantly with no streaming feel. Concatenating these pieces reproduces the
    original answer byte-for-byte.
    """
    for i in range(0, len(answer), size):
        yield answer[i : i + size]


def rag_flow_stream(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    reflector: Any | None,
    bge_embedder: BaseEmbedder,
    e5_embedder: BaseEmbedder,
    searcher: Any,
    reranker: Optional[BaseReranker],
    chat_model: BaseLLM,
    cfg: Dict[str, Any],
    tavily_tool: Any | None = None,
    routing_result: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    validity_filter: Any | None = None,
    reference_resolver: Any | None = None,
    timings_ms_out: Optional[Dict[str, float]] = None,
    metadata_out: Optional[Dict[str, Any]] = None,
    llm_cache: Optional[Any] = None,
    reroute_reflected: Optional[Any] = None,
    pre_ref_result: Optional[Dict[str, Any]] = None,
    pre_reflection_ms: Optional[float] = None,
) -> tuple[Generator[str, None, None], List[Dict[str, Any]]]:
    """Streaming RAG flow â€” retrieval runs first, then generation is streamed.

    Returns:
        A tuple of (text_chunk_generator, reranked_sources).
    """
    flow_t0 = time.perf_counter()
    timings_ms: Dict[str, Any] = (
        timings_ms_out if timings_ms_out is not None else {}
    )

    step_t0 = time.perf_counter()
    trimmed = _trim_history(history)
    timings_ms["trim_history"] = _elapsed_ms(step_t0)
    bypass_query_cache = _should_bypass_query_cache(
        question=question,
        search_query=question,
        target_collections=None,
        routing_result=routing_result,
        cfg=cfg,
    )
    if bypass_query_cache:
        timings_ms["query_cache_bypassed"] = 1.0

    # â”€â”€ Pre-retrieval query cache (P0 â€” stream variant) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Profile scope (major|cohort) so a personal answer is never served to a
    # student with a different profile â€” see _build_cache_profile.
    cache_profile = _build_cache_profile(user_context)
    if (
        llm_cache is not None
        and not bypass_query_cache
        and hasattr(llm_cache, "get_by_query")
    ):
        _qcached = llm_cache.get_by_query(
            question, chat_model.model, profile=cache_profile
        )
        if _qcached is not None:
            if _answer_has_no_info_signal(str(_qcached.get("answer", ""))):
                timings_ms["query_cache_ignored_no_info"] = 1.0
            else:
                timings_ms["query_cache_hit"] = 1.0
                timings_ms["flow_total"] = _elapsed_ms(flow_t0)
                if metadata_out is not None:
                    metadata_out["num_sources"] = len(_qcached["sources"])
                    metadata_out["collection_scores"] = {}
                    metadata_out["applied_filters"] = None
                    metadata_out["collection_results"] = None
                    metadata_out["rerank_trace"] = {
                        "cache_hit": True,
                        "query_cache_hit": True,
                        "rerank_candidate_count": len(_qcached["sources"]),
                        "rerank_returned_count": len(_qcached["sources"]),
                    }
                    metadata_out["answer_quality_gate"] = {
                        "answer_status": "answered",
                        "cache_hit": True,
                    }
                    metadata_out["context_trace"] = {
                        "cache_hit": True,
                        "context_docs_used": len(_qcached["sources"]),
                    }
                    metadata_out["tools_used"] = []
                    metadata_out["tool_calls"] = []

                def _cached_stream_early() -> Generator[str, None, None]:
                    yield from _chunk_cached_answer(
                        _strip_raw_urls(_qcached["answer"])
                    )

                return _cached_stream_early(), _qcached["sources"]

    # Reflection
    search_query = question
    resolved_major: Optional[str] = None
    resolved_cohort: Optional[str] = None
    # Major split (auth profile vs query target) for query.profile_dependency.
    resolved_user_major: Optional[str] = None
    resolved_target_major: Optional[str] = None
    if pre_ref_result is not None:
        # Use pre-computed reflection from upstream (query_stream)
        search_query = pre_ref_result.get("rewritten", question)
        entities = pre_ref_result.get("entities") or {}
        resolved_major = entities.get("major_code") or entities.get(
            "major_name"
        )
        resolved_user_major = entities.get("user_major_code")
        resolved_target_major = entities.get("target_major_code")
        cohort_entity = entities.get("cohort")
        if cohort_entity is not None:
            resolved_cohort = str(cohort_entity).strip() or None
        if pre_reflection_ms is not None:
            timings_ms["reflection"] = pre_reflection_ms
        logger.info(
            "Using pre-reflected query (stream): %r | major: %s | cohort: %s",
            search_query[:80],
            resolved_major,
            resolved_cohort,
        )
    elif reflector is not None:
        reflection_t0 = time.perf_counter()
        try:
            ref_result = reflector.reflect(
                question,
                chat_history=trimmed,
                user_context=user_context,
                user_profile=user_context,
            )
            search_query = ref_result.get("rewritten", question)
            entities = ref_result.get("entities") or {}
            resolved_major = entities.get("major_code") or entities.get(
                "major_name"
            )
            resolved_user_major = entities.get("user_major_code")
            resolved_target_major = entities.get("target_major_code")
            cohort_entity = entities.get("cohort")
            if cohort_entity is not None:
                resolved_cohort = str(cohort_entity).strip() or None
        except Exception:
            logger.warning(
                "Reflection failed, using original query", exc_info=True
            )
        timings_ms["reflection"] = _elapsed_ms(reflection_t0)

    # Deterministic fallback: always recover major/cohort metadata even if
    # reflection fails or does not return entities.
    if not resolved_major or not resolved_cohort:
        from query.reflection import _extract_entities  # noqa: PLC0415

        fallback_entities = _extract_entities(
            question,
            user_context=user_context,
            history=history,
        )
        if not resolved_major:
            resolved_major = fallback_entities.get(
                "major_code"
            ) or fallback_entities.get("major_name")
        if not resolved_cohort:
            cohort_entity = fallback_entities.get("cohort")
            if cohort_entity is not None:
                resolved_cohort = str(cohort_entity).strip() or None
        if not resolved_user_major:
            resolved_user_major = fallback_entities.get("user_major_code")
        if not resolved_target_major:
            resolved_target_major = fallback_entities.get("target_major_code")

        if resolved_major:
            logger.info("Major fallback resolved: %s", resolved_major)
        if resolved_cohort:
            logger.info("Cohort fallback resolved: %s", resolved_cohort)

    # Re-route on the reflected (standalone) query so a topic-heavy
    # conversation cannot bleed into domain selection. The reflector has
    # already baked any legitimate follow-up context into search_query, so
    # routing it history-free is bleed-free. See RAGPipeline._reroute_reflected.
    # Must run BEFORE effective_major / collection selection (both read
    # routing_result).
    if reroute_reflected is not None:
        reroute_t0 = time.perf_counter()
        try:
            routing_result = reroute_reflected(search_query, routing_result)
        except Exception:
            logger.warning(
                "Reflected-query reroute failed; keeping pipeline routing",
                exc_info=True,
            )
        timings_ms["reflected_reroute"] = _elapsed_ms(reroute_t0)

    retrieval_query = search_query

    # Drop the major metadata filter for topics whose answer does not depend on the
    # program (e.g. há»c bá»•ng) so universal answers are not narrowed to one major.
    # After profile_dependency refactor, we simply use the resolved major.
    # If the major was explicitly extracted from the query or user profile, we use it for retrieval.
    retrieval_major = resolved_major

    # Collection-aware routing (Phase 8 â€” Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    if cfg.get("find_all", False):
        routing_t0 = time.perf_counter()
        target_collections = list(cfg.get("collections") or [])
        logger.info(
            "find_all=true (stream) â†’ bypassing routing, searching all collections: %s",
            target_collections,
        )
        timings_ms["collection_routing"] = _elapsed_ms(routing_t0)
        timings_ms["find_all_override"] = 1.0
    elif routing_result:
        routing_t0 = time.perf_counter()
        domain = routing_result.get("domain")
        domains = routing_result.get("domains") or ([domain] if domain else [])
        confidence = routing_result.get("confidence", 0.0)
        target_collections = _collection_selector.select(
            domain=domain,
            confidence=confidence,
            domains=domains,
            query=search_query,
            probabilities=routing_result.get("probabilities"),
        )
        if _should_lock_kehoach_route(
            question=question,
            search_query=search_query,
            routing_result=routing_result,
        ):
            target_collections = ["kehoach"]
            timings_ms["kehoach_route_locked"] = 1.0
        timings_ms["collection_routing"] = _elapsed_ms(routing_t0)

    if _should_strip_major_for_retrieval(
        resolved_major=resolved_major,
        target_collections=target_collections,
    ):
        normalized_query = strip_major_from_query_for_retrieval(
            search_query,
            resolved_major=resolved_major,
        )
        if normalized_query != search_query:
            logger.info(
                "Retrieval query normalized: %r -> %r (major=%s)",
                search_query[:80],
                normalized_query[:80],
                resolved_major,
            )
            retrieval_query = normalized_query

    dynamic_web_query = _is_dynamic_web_query(
        question=question,
        search_query=search_query,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
    )
    if dynamic_web_query:
        timings_ms["dynamic_web_query"] = 1.0

    # â”€â”€ Populate metadata_out early (pre-generation) so caller can read it â”€â”€â”€â”€â”€â”€
    # The search_trace dict is mutated later; we update metadata_out after rerank.
    if metadata_out is not None:
        metadata_out["reflected_question"] = search_query
        metadata_out["target_collections"] = target_collections
        metadata_out["routing_probabilities"] = (
            routing_result.get("probabilities") if routing_result else None
        )

    top_k_value = _resolve_top_k(cfg.get("top_k", 5), question)
    # C4: Expand candidate pool when routing confidence is low
    routing_confidence_stream = float(
        routing_result.get("confidence", 1.0) if routing_result else 1.0
    )
    raw_candidate_k = _resolve_candidate_pool(
        cfg, top_k_value, routing_confidence_stream
    )
    major_compare_plan = build_major_comparison_subqueries_for_retrieval(
        search_query
    )
    compare_subqueries: List[str] = []
    if not major_compare_plan:
        compare_subqueries = build_cohort_comparison_subqueries_for_retrieval(
            retrieval_query
        )

    if major_compare_plan:
        logger.info(
            "Major comparison retrieval decomposition (stream): %s",
            [q for q, _ in major_compare_plan],
        )
    if compare_subqueries:
        logger.info(
            "Comparison retrieval decomposition (stream): %s",
            compare_subqueries,
        )

    rerank_query = retrieval_query
    if major_compare_plan:
        stripped = strip_major_comparison_scaffold_for_retrieval(search_query)
        if len(stripped.split()) >= 2:
            rerank_query = stripped
    elif compare_subqueries:
        stripped = strip_cohort_comparison_scaffold_for_retrieval(
            retrieval_query
        )
        if len(stripped.split()) >= 2:
            rerank_query = stripped

    # Embed â†’ Search â†’ Rerank
    search_trace: Dict[str, Any] = {}

    def _search_once(
        local_query: str,
        local_active_collections: Optional[List[str]],
        *,
        local_resolved_major: Optional[str] = None,
        use_outer_resolved_major: bool = True,
        local_disable_metadata_filter_collections: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        embed_t0 = time.perf_counter()
        bge_vec = bge_embedder.embed_query(local_query)
        timings_ms["embed_bge"] = round(
            timings_ms.get("embed_bge", 0.0) + _elapsed_ms(embed_t0),
            2,
        )

        embed_t0 = time.perf_counter()
        e5_vec = e5_embedder.embed_query(local_query)
        timings_ms["embed_e5"] = round(
            timings_ms.get("embed_e5", 0.0) + _elapsed_ms(embed_t0),
            2,
        )

        search_t0 = time.perf_counter()
        effective_resolved_major = (
            retrieval_major
            if use_outer_resolved_major
            else local_resolved_major
        )
        trace_piece: Dict[str, Any] = {}
        rows = searcher.search(
            query=local_query,
            bge_m3_query=bge_vec,
            e5_query=e5_vec,
            top_k=raw_candidate_k,
            vector_top_k=cfg.get("vector_top_k", 20),
            keyword_top_k=cfg.get("keyword_top_k", 20),
            vector_pool_k=cfg.get("vector_pool_k", 15),
            keyword_pool_k=cfg.get("keyword_pool_k", 15),
            active_collections=local_active_collections,
            resolved_major=effective_resolved_major,
            resolved_cohort=resolved_cohort,
            disable_metadata_filter_collections=local_disable_metadata_filter_collections,
            trace_out=trace_piece,
        )
        timings_ms["search"] = round(
            timings_ms.get("search", 0.0) + _elapsed_ms(search_t0),
            2,
        )
        _merge_search_trace(search_trace, trace_piece)
        return rows

    raw_results_buffer: List[Dict[str, Any]] = []
    if major_compare_plan:
        for subquery, subquery_major in major_compare_plan:
            raw_results_buffer.extend(
                _search_once(
                    subquery,
                    target_collections,
                    local_resolved_major=subquery_major,
                    use_outer_resolved_major=False,
                )
            )
    else:
        primary_queries = compare_subqueries or [retrieval_query]
        for subquery in primary_queries:
            raw_results_buffer.extend(
                _search_once(subquery, target_collections)
            )
    raw_results = _dedup_retrieval_candidates(
        raw_results_buffer,
        top_k=raw_candidate_k,
    )

    if not raw_results and (compare_subqueries or major_compare_plan):
        logger.info(
            "Comparison subqueries returned no candidates (stream); retrying original query."
        )
        fallback_compare_query = (
            search_query if major_compare_plan else retrieval_query
        )
        raw_results = _dedup_retrieval_candidates(
            _search_once(
                fallback_compare_query,
                target_collections,
                use_outer_resolved_major=not major_compare_plan,
            ),
            top_k=raw_candidate_k,
        )

    if not raw_results:
        logger.info(
            "No candidates (stream); retrying with quydinh metadata filter disabled."
        )
        raw_results = _dedup_retrieval_candidates(
            _search_once(
                retrieval_query,
                target_collections,
                local_disable_metadata_filter_collections=["quydinh"],
            ),
            top_k=raw_candidate_k,
        )
        if not raw_results and target_collections is not None:
            raw_results = _dedup_retrieval_candidates(
                _search_once(
                    retrieval_query,
                    None,
                    local_disable_metadata_filter_collections=["quydinh"],
                ),
                top_k=raw_candidate_k,
            )

    if not raw_results and target_collections is not None:
        logger.info(
            "No candidates for routed collections (stream); retrying all collections."
        )
        raw_results = _dedup_retrieval_candidates(
            _search_once(retrieval_query, None),
            top_k=raw_candidate_k,
        )

    if not raw_results and (compare_subqueries or major_compare_plan):
        compare_source_query = (
            search_query if major_compare_plan else retrieval_query
        )
        relaxed_query = (
            strip_major_comparison_scaffold_for_retrieval(search_query)
            if major_compare_plan
            else strip_cohort_comparison_scaffold_for_retrieval(retrieval_query)
        )
        if relaxed_query != compare_source_query:
            raw_results = _dedup_retrieval_candidates(
                _search_once(
                    relaxed_query,
                    target_collections,
                    use_outer_resolved_major=not major_compare_plan,
                ),
                top_k=raw_candidate_k,
            )
            if not raw_results and target_collections is not None:
                raw_results = _dedup_retrieval_candidates(
                    _search_once(
                        relaxed_query,
                        None,
                        use_outer_resolved_major=not major_compare_plan,
                    ),
                    top_k=raw_candidate_k,
                )

    # 4.5 Sibling chunk expansion (C1) â€” BEFORE rerank (streaming flow)
    if _cfg_bool(cfg, "sibling_expansion_enabled", False) and raw_results:
        expansion_t0 = time.perf_counter()
        pre_expansion_count = len(raw_results)
        raw_results = _expand_with_siblings_pre_rerank(
            candidates=raw_results,
            searcher=searcher,
            expand_top_n=3,
            window=1,
            max_expansion=6,
        )
        timings_ms["sibling_expansion"] = _elapsed_ms(expansion_t0)
        siblings_added = len(raw_results) - pre_expansion_count
        timings_ms["sibling_expansion_hit"] = 1.0 if siblings_added > 0 else 0.0
        timings_ms["sibling_expansion_count"] = float(siblings_added)

    rerank_t0 = time.perf_counter()

    rerank_query = expand_major_in_query_for_reranking(
        rerank_query, resolved_major
    )
    if reranker is not None:
        reranked = reranker.rerank(
            query=rerank_query,
            documents=raw_results,
            top_k=top_k_value,
            **_reranker_kwargs(cfg, top_k_value),
        )
        timings_ms["rerank"] = _elapsed_ms(rerank_t0)
        rerank_trace = _build_rerank_trace(
            reranker=reranker,
            candidate_count=len(raw_results),
            reranked=reranked,
        )
        logger.info("Reranked to %d documents", len(reranked))

        # Fallback: same logic as rag_flow - trigger when all surviving reranked
        # docs have negative scores (reflected query drift or only table-threshold
        # docs survived).
        _best_rerank_score_s = _best_explicit_rerank_score(reranked)
        _rerank_quality_ok_s = bool(reranked) and (
            _best_rerank_score_s is None or _best_rerank_score_s >= 0.0
        )
        if raw_results and not _rerank_quality_ok_s:
            fallback_reason_s = (
                "empty_rerank" if not reranked else "negative_rerank_score"
            )
            logger.info(
                "Stream: reranker gave no positive-score candidates (best=%.3f). "
                "Retrying with original question.",
                (
                    _best_rerank_score_s
                    if _best_rerank_score_s is not None
                    else -999.0
                ),
            )
            reranked = reranker.rerank(
                query=question,
                documents=raw_results,
                top_k=top_k_value,
                **_reranker_kwargs(cfg, top_k_value),
            )
            timings_ms["rerank_fallback"] = 1.0
            retry_best_score_s = _best_explicit_rerank_score(reranked)
            if not reranked or (
                retry_best_score_s is not None and retry_best_score_s < 0.0
            ):
                fallback_reason_s = (
                    "empty_rerank" if not reranked else "negative_rerank_score"
                )
                logger.info(
                    "Stream: reranker still no positive candidates. "
                    "Using raw fusion top-%d.",
                    top_k_value,
                )
                reranked = sorted(
                    raw_results, key=lambda d: d.get("score", 0.0), reverse=True
                )[:top_k_value]
                timings_ms["rerank_raw_fallback"] = 1.0
            rerank_trace = _update_rerank_trace_after_fallback(
                rerank_trace,
                candidate_count=len(raw_results),
                reranked=reranked,
                fallback_reason=fallback_reason_s,
                raw_fallback=bool(timings_ms.get("rerank_raw_fallback")),
            )
    else:
        reranked = sorted(
            raw_results, key=lambda d: d.get("score", 0.0), reverse=True
        )[:top_k_value]
        timings_ms["rerank_skipped"] = 1.0
        rerank_trace = _build_rerank_trace(
            reranker=None,
            candidate_count=len(raw_results),
            reranked=reranked,
        )
        rerank_trace["rerank_skipped"] = True
        logger.warning(
            "Stream: reranker unavailable; using top-%d raw candidates by fusion score.",
            top_k_value,
        )

    # 5.05 HyDE post-rerank fallback â€” second-pass retrieval for low-recall
    if _should_trigger_hyde(reranked, reranker, cfg):
        reranked = _hyde_fallback_post_rerank(
            reranked=reranked,
            raw_candidate_k=raw_candidate_k,
            retrieval_query=retrieval_query,
            rerank_query=rerank_query,
            top_k_value=top_k_value,
            bge_embedder=bge_embedder,
            e5_embedder=e5_embedder,
            searcher=searcher,
            reranker=reranker,
            chat_model=chat_model,
            target_collections=target_collections,
            resolved_major=resolved_major,
            resolved_cohort=resolved_cohort,
            cfg=cfg,
            timings_ms=timings_ms,
        )

    # 5.1 Document Validity Filtering
    if validity_filter is not None:
        valid_t0 = time.perf_counter()
        reranked = validity_filter.filter(reranked)
        timings_ms["validity_filter"] = _elapsed_ms(valid_t0)

    # 5.2 Cross-Reference Resolution
    if reference_resolver is not None:
        resolve_t0 = time.perf_counter()
        reranked = reference_resolver.resolve(reranked, query=retrieval_query)
        timings_ms["reference_resolver"] = _elapsed_ms(resolve_t0)

    # 5.3 Per-collection Score Cliff (B1)
    if _cfg_bool(cfg, "score_cliff_enabled", False):
        pre_cliff_count = len(reranked)
        reranked = _apply_score_cliff_per_collection(reranked)
        cliff_dropped = pre_cliff_count - len(reranked)
        timings_ms["cliff_triggered"] = 1.0 if cliff_dropped > 0 else 0.0
        timings_ms["cliff_dropped_count"] = float(cliff_dropped)

    # 5.4 Parent context expansion (C5) â€” fetch parent by ID after rerank
    parent_t0 = time.perf_counter()
    reranked = _expand_parent_context_post_rerank(reranked, cfg)
    timings_ms["parent_expansion"] = _elapsed_ms(parent_t0)

    web_fallback_used = False
    web_decision = _build_pre_generation_web_decision(
        question=question,
        search_query=search_query,
        reranked=reranked,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
        low_retrieval_confidence=bool(timings_ms.get("rerank_raw_fallback")),
    )
    web_fallback_query = str(
        web_decision.get("web_search_query") or search_query
    )
    web_fallback_reasons: List[str] = list(web_decision.get("reasons") or [])
    if web_decision.get("freshness_query"):
        timings_ms["freshness_query"] = 1.0

    web_context_override = ""
    if web_fallback_reasons:
        timings_ms["web_fallback_requested"] = 1.0
        if cfg.get("tavily_fallback_enabled", False):
            search_info = _tavily_search_context(
                query=web_fallback_query,
                tavily_tool=tavily_tool,
                max_results=_cfg_int(cfg, "tavily_max_results", 3),
                search_depth=str(
                    cfg.get("tavily_search_depth", "basic") or "basic"
                ),
                result_count=_cfg_int(cfg, "tavily_web_result_count", 3),
                content_char_limit=_cfg_int(
                    cfg, "tavily_web_content_char_limit", 1500
                ),
            )
            timings_ms.update(search_info["timings"])
            web_sources = list(search_info.get("sources") or [])
            if search_info.get("used"):
                web_fallback_used = True
                timings_ms["web_fallback_used"] = 1.0
                web_context_override = str(search_info.get("context") or "")
                if web_sources:
                    reranked = reranked + web_sources
        else:
            timings_ms["tavily_skipped"] = 1.0

    context_t0 = time.perf_counter()
    # For list queries (top_k was scaled up), use a larger char budget.
    context_doc_limit, context_char_budget = _resolve_context_budget(
        cfg,
        top_k_value=top_k_value,
    )
    context_trace: Dict[str, Any] = {}
    context_documents = reranked
    if web_context_override:
        context_documents = [
            doc
            for doc in reranked
            if str(doc.get("collection") or "").lower() != "web"
        ]
    # C2: Reorder so siblings appear after their parents (streaming)
    if _cfg_bool(cfg, "sibling_expansion_enabled", False):
        context_documents = _order_with_siblings(context_documents)
    context = _format_context(
        context_documents,
        per_doc_char_limit=context_doc_limit,
        total_char_budget=context_char_budget,
        sibling_per_doc_limit=_cfg_int(cfg, "sibling_per_doc_limit", 800),
        trace_out=context_trace,
    )
    context = _merge_local_and_web_context(context, web_context_override)
    profile_note = _profile_note_for_generation(
        question,
        search_query,
        routing_result,
        resolved_major,
        resolved_cohort,
        resolved_user_major,
        resolved_target_major,
        user_context,
        history,
    )
    full_context = (
        f"{profile_note}\n\n---\n\n{context}" if profile_note else context
    )
    context_trace["full_context_chars"] = len(full_context)
    timings_ms["format_context"] = _elapsed_ms(context_t0)
    timings_ms["retrieval_total"] = round(
        timings_ms.get("embed_bge", 0.0)
        + timings_ms.get("embed_e5", 0.0)
        + timings_ms.get("search", 0.0)
        + timings_ms.get("rerank", 0.0)
        + timings_ms.get("format_context", 0.0),
        2,
    )

    # â”€â”€ Final metadata update (post-rerank, pre-stream) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if metadata_out is not None:
        metadata_out["num_sources"] = len(reranked)
        metadata_out["collection_scores"] = _build_collection_scores(
            all_collections=cfg.get("collections"),
            target_collections=target_collections,
            routing_result=routing_result,
        )
        metadata_out["applied_filters"] = search_trace.get("filters")
        metadata_out["collection_results"] = search_trace.get(
            "collection_counts"
        )
        metadata_out["fusion_weights"] = search_trace.get("fusion_weights")
        metadata_out["context_trace"] = context_trace
        metadata_out["rerank_trace"] = rerank_trace
        metadata_out["answer_quality_gate"] = {
            "answer_status": web_decision["answer_status"],
            "should_web_search": bool(web_fallback_reasons),
            "web_search_query": web_fallback_query,
            "reasons": web_fallback_reasons,
            "dynamic_query": dynamic_web_query,
            "freshness_query": bool(web_decision.get("freshness_query")),
            "pre_generation_reasons": web_fallback_reasons,
            "pre_generation_web_used": web_fallback_used,
            "pre_generation_freshness_query": bool(
                web_decision.get("freshness_query")
            ),
            "no_sources": "no_sources" in web_fallback_reasons,
            "low_retrieval_confidence": "low_retrieval_confidence"
            in web_fallback_reasons,
        }
        metadata_out["tools_used"] = (
            ["tavily_search"] if timings_ms.get("tavily_search") else []
        )
        metadata_out["tool_calls"] = (
            [
                {
                    "tool": "tavily_search",
                    "args": {
                        "query": web_fallback_query,
                        "include_domains": "HUST_OFFICIAL_DOMAINS",
                    },
                    "result": "used" if web_fallback_used else "searched",
                    "iteration": 0,
                    "latency_ms": timings_ms.get("tavily_search"),
                }
            ]
            if timings_ms.get("tavily_search")
            else []
        )

    # â”€â”€ LLM Response Cache Check (Phase 2 - Stream) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if (
        llm_cache is not None
        and not dynamic_web_query
        and not web_fallback_used
        and not web_fallback_reasons
    ):
        doc_ids = [str(doc.get("id", "")) for doc in reranked if doc.get("id")]
        cached = llm_cache.get(
            question, doc_ids, chat_model.model, profile=cache_profile
        )
        if cached is not None:
            if _answer_has_no_info_signal(str(cached.get("answer", ""))):
                timings_ms["llm_cache_ignored_no_info"] = 1.0
            else:
                logger.info(
                    "LLM cache HIT (stream) for query: %r", question[:80]
                )
                timings_ms["llm_cache_hit"] = 1.0
                if metadata_out is not None:
                    metadata_out["rerank_trace"] = {
                        **(metadata_out.get("rerank_trace") or {}),
                        "cache_hit": True,
                        "llm_cache_hit": True,
                    }
                    metadata_out["answer_quality_gate"] = {
                        "answer_status": "answered",
                        "cache_hit": True,
                    }
                    metadata_out["context_trace"] = {
                        "cache_hit": True,
                        "context_docs_used": len(cached["sources"]),
                    }

                def _cached_stream() -> Generator[str, None, None]:
                    yield from _chunk_cached_answer(
                        _strip_raw_urls(cached["answer"])
                    )
                    timings_ms["stream_first_token"] = 0.1
                    timings_ms["stream_generate"] = 0.1
                    timings_ms["flow_total"] = _elapsed_ms(flow_t0)
                    _log_timings("rag_flow_stream_cached", timings_ms)

                return _cached_stream(), cached["sources"]

    def _open_stream(ctx: str, hist) -> Generator[str, None, None]:
        return chat_model.generate_stream(
            query=question, context=ctx, history=hist, mode="rag"
        )

    def _timed_stream() -> Generator[str, None, None]:
        stream_t0 = time.perf_counter()
        first_token_ms: Optional[float] = None
        generated_chars = 0
        full_cached_answer = []

        # Open the stream + pull the first chunk inside a guard so a context
        # overflow can be recovered with a reduced budget BEFORE any token is
        # sent to the client (mirrors the non-streaming rag_flow recovery).
        try:
            iterator = _open_stream(full_context, trimmed)
            pending = next(iterator, None)
        except Exception as exc:
            if not _is_context_length_error(exc):
                raise
            logger.warning(
                "Stream context too long, retrying with reduced budget",
                exc_info=True,
            )
            reduced_context = _format_context(
                reranked[:2],
                per_doc_char_limit=600,
                total_char_budget=1500,
            )
            timings_ms["context_recovery"] = 1.0
            try:
                iterator = _open_stream(
                    reduced_context, _trim_history(history, limit=3)
                )
                pending = next(iterator, None)
            except Exception as retry_exc:
                if _is_context_length_error(retry_exc):
                    raise RuntimeError(
                        "Ngá»¯ cáº£nh há»™i thoáº¡i Ä‘ang quÃ¡ dÃ i. "
                        "Vui lÃ²ng báº¯t Ä‘áº§u phiÃªn má»›i hoáº·c há»i ngáº¯n gá»n hÆ¡n."
                    ) from retry_exc
                raise

        sanitizer = _StreamUrlSanitizer()
        chunk = pending
        while chunk is not None:
            if first_token_ms is None:
                first_token_ms = _elapsed_ms(stream_t0)
            generated_chars += len(chunk)
            full_cached_answer.append(chunk)
            sanitized = sanitizer.feed(chunk)
            if sanitized:
                yield sanitized
            chunk = next(iterator, None)

        # Flush any buffered text remaining in the sanitizer.
        remaining = sanitizer.finalize()
        if remaining:
            yield remaining

        timings_ms["stream_first_token"] = round(first_token_ms or 0.0, 2)
        timings_ms["stream_generate"] = _elapsed_ms(stream_t0)
        timings_ms["flow_total"] = _elapsed_ms(flow_t0)
        logger.info("rag_flow_stream: streamed %d chars", generated_chars)
        _log_timings("rag_flow_stream", timings_ms)

        # Sanitize before caching: chunks were accumulated raw (the sanitizer
        # only ran on what was *yielded*), so encode/wrap URLs here too. Keeps
        # cached answers consistent with the streamed text — no raw URL can be
        # served from cache even if a read path forgets to re-sanitize.
        stream_answer = _sanitize_answer_urls("".join(full_cached_answer))

        # Note: Kehoach links are displayed via frontend source cards.
        # No footer appending needed.

        # Cache newly generated stream response (Phase 2)
        cache_stream_answer = _should_cache_final_answer(
            answer=stream_answer,
            answer_quality_gate=web_decision,
            dynamic_web_query=dynamic_web_query,
            pre_web_fallback_used=web_fallback_used,
            web_fallback_used=web_fallback_used,
            web_fallback_reasons=web_fallback_reasons,
        )
        if llm_cache is not None and cache_stream_answer:
            doc_ids = [
                str(doc.get("id", "")) for doc in reranked if doc.get("id")
            ]
            llm_cache.put(
                question,
                doc_ids,
                chat_model.model,
                stream_answer,
                reranked,
                profile=cache_profile,
            )

        # Also populate the pre-retrieval query-only cache.
        if (
            llm_cache is not None
            and hasattr(llm_cache, "put_by_query")
            and cache_stream_answer
            and not dynamic_web_query
            and not web_fallback_used
            and not web_fallback_reasons
        ):
            llm_cache.put_by_query(
                question,
                chat_model.model,
                stream_answer,
                reranked,
                profile=cache_profile,
            )

    return _timed_stream(), reranked
