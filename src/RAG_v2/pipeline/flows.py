"""Pipeline Flows — chitchat and RAG flow definitions."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

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

logger = logging.getLogger(__name__)

_collection_selector = CollectionSelector()

# Personal-pronoun pattern removed — entity extraction is now handled by QueryReflector._extract_entities

# ── History budget ──────────────────────────────────────────────────────────────
_DEFAULT_HISTORY_LIMIT = 8
_HISTORY_MESSAGE_CHAR_LIMIT = 400  # chars per message before truncation
_HISTORY_TOTAL_CHAR_BUDGET = 2000  # total chars across all kept messages

# ── Context budget ─────────────────────────────────────────────────────────────
_DEFAULT_CONTEXT_DOC_CHAR_LIMIT = 1500  # chars per retrieved chunk
_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET = 8000  # total context chars sent to LLM

# ── Self-eval ──────────────────────────────────────────────────────────────────
_SELF_EVAL_SCORE_THRESHOLD = 0.72  # run self-eval only when top score < this
_SELF_EVAL_MAX_DOCS = 2
_SELF_EVAL_DOC_CHAR_LIMIT = 600
_SELF_EVAL_TOTAL_CHAR_BUDGET = 1800

# ── Context-length error markers (shared across providers) ─────────────────────
_CTX_ERROR_MARKERS = (
    "context length",
    "maximum context length",
    "too many tokens",
    "tokens to keep",
    "prompt is too long",
    "context_length_exceeded",
)

_EXPLICIT_MAJOR_CODE_RE = re.compile(
    r"\b(?:IT|MI)\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]?\s*"
    r"(?:E10|E15|E6|E7|EP|1|2)\b",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════════


def _elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds rounded for compact logs/JSON."""
    return round((time.perf_counter() - start) * 1000, 2)


def _log_timings(flow_name: str, timings_ms: Dict[str, float]) -> None:
    """Log timing breakdown sorted by slowest stage first."""
    if not timings_ms:
        return
    ordered = sorted(
        timings_ms.items(), key=lambda item: item[1], reverse=True
    )
    summary = ", ".join(
        f"{stage}={duration:.1f}" for stage, duration in ordered
    )
    logger.info("%s timings (ms): %s", flow_name, summary)


def _retrieval_candidate_k(top_k: int) -> int:
    """Return candidate pool size before reranking.

    Keep the previous proportional heuristic (4x final top_k) while enforcing
    a minimum of 20 candidates for stronger reranker recall.
    """
    return max(top_k * 4, 20)


def _should_strip_major_for_retrieval(
    *,
    resolved_major: Optional[str],
    target_collections: Optional[List[str]],
) -> bool:
    """Return True when major phrases should be stripped from retrieval query.

    Keeping major mentions is important when routing is confidently quydinh-only,
    because quydinh does not use ``major_code`` metadata filters and therefore
    relies on lexical/semantic major cues in the query text itself.
    """
    if not resolved_major:
        return False

    if target_collections is None:
        return True

    normalized_targets = {
        str(col).strip().lower()
        for col in target_collections
        if str(col).strip()
    }
    if normalized_targets == {"quydinh"}:
        return False
    return True


def _safe_float(value: Any) -> float:
    """Return *value* as float, or 0.0 when conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _dedup_retrieval_candidates(
    candidates: List[Dict[str, Any]],
    *,
    top_k: int,
) -> List[Dict[str, Any]]:
    """Deduplicate by ``id`` while keeping the highest-scoring candidate."""
    best_by_id: Dict[str, Dict[str, Any]] = {}
    for item in candidates:
        doc_id = str(item.get("id", "") or "")
        if not doc_id:
            continue
        prev = best_by_id.get(doc_id)
        if prev is None or _safe_float(item.get("score")) > _safe_float(prev.get("score")):
            best_by_id[doc_id] = item

    ranked = sorted(
        best_by_id.values(),
        key=lambda row: _safe_float(row.get("score")),
        reverse=True,
    )
    return ranked[:top_k]


def _merge_search_trace(
    aggregate_trace: Dict[str, Any],
    trace_piece: Dict[str, Any],
) -> None:
    """Merge one search trace chunk into aggregate trace state."""
    if not trace_piece:
        return

    incoming_filters = trace_piece.get("filters")
    if isinstance(incoming_filters, dict):
        merged_filters = aggregate_trace.setdefault("filters", {})
        for collection, finfo in incoming_filters.items():
            if not isinstance(finfo, dict):
                continue
            prev = merged_filters.get(collection)
            if not isinstance(prev, dict):
                merged_filters[collection] = finfo
                continue

            prev_applied = bool(prev.get("applied"))
            new_applied = bool(finfo.get("applied"))
            prev_hits = int(_safe_float(prev.get("matched_ids")))
            new_hits = int(_safe_float(finfo.get("matched_ids")))
            if (new_applied and not prev_applied) or new_hits > prev_hits:
                merged_filters[collection] = finfo

    incoming_counts = trace_piece.get("collection_counts")
    if isinstance(incoming_counts, dict):
        merged_counts = aggregate_trace.setdefault("collection_counts", {})
        for collection, count_info in incoming_counts.items():
            if not isinstance(count_info, dict):
                continue
            row = merged_counts.setdefault(collection, {"vector": 0, "keyword": 0})
            row["vector"] = int(_safe_float(row.get("vector"))) + int(
                _safe_float(count_info.get("vector"))
            )
            row["keyword"] = int(_safe_float(row.get("keyword"))) + int(
                _safe_float(count_info.get("keyword"))
            )


def _format_context(
    documents: List[Dict[str, Any]],
    *,
    per_doc_char_limit: int = _DEFAULT_CONTEXT_DOC_CHAR_LIMIT,
    total_char_budget: int = _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET,
) -> str:
    """Convert retrieved documents into a token-budgeted context string.

    Limits per-document and total context size to prevent context-length
    errors and keep LLM latency predictable regardless of chunk sizes.
    """
    parts: List[str] = []
    used = 0
    for i, doc in enumerate(documents, 1):
        meta = doc.get("metadata", {})
        title = meta.get("title") or meta.get("source") or "Tài liệu không rõ nguồn"
        text = str(doc.get("text", "") or "").strip()
        if len(text) > per_doc_char_limit:
            text = text[:per_doc_char_limit] + "\u2026"  # ellipsis
        chunk = f"--- Văn bản: {title}\n{text}"
        separator_cost = 7 if parts else 0  # len("\n\n---\n\n")
        if used + len(chunk) + separator_cost > total_char_budget:
            break
        parts.append(chunk)
        used += len(chunk) + separator_cost
    return "\n\n---\n\n".join(parts)


def _trim_history(
    history: Optional[List[Dict[str, str]]],
    limit: int = _DEFAULT_HISTORY_LIMIT,
) -> List[Dict[str, str]]:
    """Keep recent history within message-count and character budgets.

    Truncates individual messages that are too long and stops adding
    older messages once the total character budget is exhausted. This
    prevents context-length errors that grow with conversation length.
    """
    if not history:
        return []

    recent = history[-limit:]
    normalised: List[Dict[str, str]] = []
    for msg in recent:
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if len(content) > _HISTORY_MESSAGE_CHAR_LIMIT:
            content = content[:_HISTORY_MESSAGE_CHAR_LIMIT] + "\u2026"
        normalised.append({"role": role, "content": content})

    if not normalised:
        return []

    # Apply total char budget from newest to oldest.
    kept_reversed: List[Dict[str, str]] = []
    used = 0
    for msg in reversed(normalised):
        msg_len = len(msg["content"])
        if used + msg_len > _HISTORY_TOTAL_CHAR_BUDGET and kept_reversed:
            break
        kept_reversed.append(msg)
        used += msg_len

    return list(reversed(kept_reversed))


def _is_context_length_error(exc: Exception) -> bool:
    """Detect provider errors caused by prompt/context length overflow."""
    message = str(exc).lower()
    return any(marker in message for marker in _CTX_ERROR_MARKERS)


def _try_direct_answer(question: str) -> Optional[str]:
    """Handle simple out-of-domain questions locally — no LLM or retrieval."""
    q = question.lower().strip()
    now = datetime.now()
    days_vi = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

    if any(kw in q for kw in ("mấy giờ", "may gio", "bây giờ là mấy", "bay gio la may")):
        return f"Bây giờ là {now.strftime('%H:%M')} ngày {now.strftime('%d/%m/%Y')}."

    if any(kw in q for kw in ("hôm nay", "hom nay", "ngày mấy", "ngay may", "thứ mấy", "thu may")):
        day_name = days_vi[now.weekday()]
        return f"Hôm nay là {day_name}, ngày {now.strftime('%d/%m/%Y')}."

    return None


def _extract_session_profile_dict(
    history: Optional[List[Dict[str, str]]],
) -> Dict[str, str]:
    """Scan full conversation history and return a raw dict of user-stated facts.

    Keys: ``"nganh"``, ``"nam"``, ``"khoa"``, ``"gpa"`` (all optional).
    Returns empty dict when nothing useful is found.
    """
    if not history:
        return {}

    profile: Dict[str, str] = {}
    user_messages = [
        m.get("content", "") for m in history
        if m.get("role") == "user" and m.get("content")
    ]

    for text in user_messages:
        t = text.lower()
        if not profile.get("nganh"):
            m = re.search(r"(?:h\u1ecdc ng\u00e0nh|ng\u00e0nh|chuy\u00ean ng\u00e0nh)\s+([^\.,\n]{2,30})", t)
            if m:
                profile["nganh"] = m.group(1).strip()
        if not profile.get("nam"):
            m = re.search(r"sinh vi\u00ean n\u0103m\s*(\d)|n\u0103m\s*(\d)\b|n\u0103m th\u1ee9\s*(\d)", t)
            if m:
                profile["nam"] = next(g for g in m.groups() if g)
        if not profile.get("khoa"):
            m = re.search(r"\bk(\d{2,3})\b|kh\u00f3a\s*(\d{2,3})", t)
            if m:
                profile["khoa"] = next(g for g in m.groups() if g)
        if not profile.get("gpa"):
            m = re.search(r"\b(?:cpa|gpa)\s*(?:l\u00e0|=|:)?\s*(\d+[\.,]\d+)\b", t)
            if m:
                profile["gpa"] = m.group(1).replace(",", ".")

    return profile


def _extract_session_profile(history: Optional[List[Dict[str, str]]]) -> str:
    """Scan full conversation history for user-stated facts (major, year, GPA).

    Returns a compact note like:
        "Thông tin sinh viên: ngành CNTT, năm 3, CPA=2.4."
    or empty string when nothing useful is found.

    This allows the LLM to answer personal questions (\"tôi học ngành gì?\") even
    after the original turn has been trimmed from the context window.
    """
    profile = _extract_session_profile_dict(history)
    if not profile:
        return ""

    parts: List[str] = []
    if "nganh" in profile:
        parts.append(f"ng\u00e0nh {profile['nganh']}")
    if "nam" in profile:
        parts.append(f"n\u0103m {profile['nam']}")
    if "khoa" in profile:
        parts.append(f"K{profile['khoa']}")
    if "gpa" in profile:
        parts.append(f"CPA={profile['gpa']}")

    return "Th\u00f4ng tin sinh vi\u00ean: " + ", ".join(parts) + "."


def _build_profile_note_from_user_context(
    user_context: Optional[Dict[str, Any]],
) -> str:
    """Build a compact profile note from the authenticated user's profile dict.
    Used only inside the reflector prompt — NOT for post-reflection bracketing.
    """
    if not user_context:
        return ""

    parts: List[str] = []
    if user_context.get("full_name"):
        parts.append(f"Sinh viên: {user_context['full_name']}")
    if user_context.get("student_id"):
        parts.append(f"Mã SV: {user_context['student_id']}")
    if user_context.get("major"):
        major_note = user_context["major"]
        if user_context.get("major_code"):
            major_note += f" [{user_context['major_code']}]"
        parts.append(f"Ngành: {major_note}")
    if user_context.get("cohort"):
        parts.append(f"Khoá: {user_context['cohort']}")

    return " | ".join(parts) if parts else ""


def _should_prepend_profile_note(question: str) -> bool:
    """Return False when question already provides an explicit major code."""
    return _EXPLICIT_MAJOR_CODE_RE.search(question or "") is None


def _build_collection_scores(
    *,
    all_collections: Optional[List[str]],
    target_collections: Optional[List[str]],
    routing_result: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build ranked query scores for all configured collections."""
    selected = target_collections or []

    candidates = [c for c in (all_collections or []) if c]
    if not candidates:
        candidates = [c for c in selected if c]

    if not candidates:
        return []

    if not routing_result:
        return [{"collection": col, "score": 0.0} for col in candidates]

    confidence_raw = routing_result.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0

    probabilities = routing_result.get("probabilities") or {}
    if not isinstance(probabilities, dict):
        probabilities = {}

    if routing_result.get("tier3_override"):
        # Tier-3 LLM override can change selected domains without updating the
        # classifier probability map. Use confidence for selected collections.
        probabilities = {
            col: confidence for col in selected if isinstance(col, str)
        }

    scores: List[Dict[str, Any]] = []
    for collection in candidates:
        # Non-selected collections default to 0 so ranking is explicit.
        default_score = confidence if collection in selected else 0.0
        score_raw = probabilities.get(collection, default_score)
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            score = default_score
        score = max(0.0, min(1.0, score))
        scores.append(
            {
                "collection": collection,
                "score": round(score, 4),
            }
        )

    scores.sort(key=lambda item: item["score"], reverse=True)
    return scores


# ═══════════════════════════════════════════════════════════════════════════════
# Chitchat Flow
# ═══════════════════════════════════════════════════════════════════════════════


def chitchat_flow(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    chat_model: BaseLLM,
) -> Dict[str, Any]:
    """Router → Chat Model → response (no retrieval).

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


# ═══════════════════════════════════════════════════════════════════════════════
# RAG Flow
# ═══════════════════════════════════════════════════════════════════════════════


def rag_flow(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    reflector: Any | None,
    bge_embedder: BaseEmbedder,
    e5_embedder: BaseEmbedder,
    searcher: Any,
    reranker: BaseReranker,
    chat_model: BaseLLM,
    self_evaluator: Optional[SelfEvaluator],
    tavily_tool: Any | None,
    cfg: Dict[str, Any],
    routing_result: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    validity_filter: Any | None = None,
    reference_resolver: Any | None = None,
) -> Dict[str, Any]:
    """Full RAG flow: Reflect → Embed → Search → Rerank → Generate → SelfEval → (Tavily fallback).

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
        user_context: Authenticated user profile (major, cohort, student_id …).

    Returns:
        Dict with ``answer``, ``sources``, ``intent``, etc.
    """
    flow_t0 = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    step_t0 = time.perf_counter()
    trimmed = _trim_history(history)
    timings_ms["trim_history"] = _elapsed_ms(step_t0)

    # 1. Reflection — rewrite query + extract entities
    search_query = question
    reflection_prompt: Optional[str] = None
    resolved_major: Optional[str] = None
    resolved_cohort: Optional[str] = None
    if reflector is not None:
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
            resolved_major = entities.get("major_code") or entities.get("major_name")
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
            logger.warning("Reflection failed, using original query", exc_info=True)
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
            resolved_major = (
                fallback_entities.get("major_code")
                or fallback_entities.get("major_name")
            )
        if not resolved_cohort:
            cohort_entity = fallback_entities.get("cohort")
            if cohort_entity is not None:
                resolved_cohort = str(cohort_entity).strip() or None

        if resolved_major:
            logger.info("Major fallback resolved: %s", resolved_major)
        if resolved_cohort:
            logger.info("Cohort fallback resolved: %s", resolved_cohort)

    retrieval_query = search_query

    # 2. Collection-aware routing (Phase 8 — Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    routing_probabilities: Optional[Dict[str, Any]] = None
    if routing_result:
        routing_t0 = time.perf_counter()
        domain = routing_result.get("domain")
        domains = routing_result.get("domains") or ([domain] if domain else [])
        confidence = routing_result.get("confidence", 0.0)
        target_collections = _collection_selector.select(
            domain=domain,
            confidence=confidence,
            domains=domains,
        )
        routing_probabilities = routing_result.get("probabilities")
        logger.info(
            "Domains: %s (conf=%.3f) → searching collections: %s",
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

    top_k_value = cfg.get("top_k", 5)
    raw_candidate_k = _retrieval_candidate_k(top_k_value)
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
        stripped = strip_cohort_comparison_scaffold_for_retrieval(retrieval_query)
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
            resolved_major if use_outer_resolved_major else local_resolved_major
        )
        result_rows = searcher.search(
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
        return result_rows

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
            "Comparison subqueries returned no candidates; retrying original query."
        )
        fallback_compare_query = search_query if major_compare_plan else retrieval_query
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
        compare_source_query = search_query if major_compare_plan else retrieval_query
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

    # 5. Rerank
    rerank_t0 = time.perf_counter()
    
    rerank_query = expand_major_in_query_for_reranking(rerank_query, resolved_major)

    reranked = reranker.rerank(
        query=rerank_query,
        documents=raw_results,
        top_k=top_k_value,
    )
    timings_ms["rerank"] = _elapsed_ms(rerank_t0)
    logger.info("Reranked to %d documents", len(reranked))

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


    # 6. Format context — inject profile so user facts survive trimming.
    #    Priority 1: use authenticated user_context (precise, always present).
    #    Priority 2: fall back to regex scan of history.
    context_t0 = time.perf_counter()
    context = _format_context(reranked)
    profile_note = ""
    if _should_prepend_profile_note(question):
        profile_note = (
            _build_profile_note_from_user_context(user_context)
            or _extract_session_profile(history)
        )
    full_context = f"{profile_note}\n\n---\n\n{context}" if profile_note else context
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
                    "Ngữ cảnh hội thoại đang quá dài. "
                    "Vui lòng bắt đầu phiên mới hoặc hỏi ngắn gọn hơn."
                ) from retry_exc
            raise
    if recovered:
        timings_ms["context_recovery"] = 1.0
    timings_ms["generate"] = _elapsed_ms(generate_t0)

    # 8. Self-evaluation — only when retrieval confidence is low.
    # Saves 11-20s per query when retrieval already found a relevant chunk.
    top_score = 0.0
    if reranked:
        try:
            top_score = float(reranked[0].get("score", 0.0))
        except (TypeError, ValueError):
            top_score = 0.0
    run_self_eval = (
        self_evaluator is not None
        and top_score < cfg.get("self_eval_min_top_score", _SELF_EVAL_SCORE_THRESHOLD)
    )
    if run_self_eval:
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
            if not eval_result.get("pass", True):
                logger.info(
                    "Self-eval FAILED (%s), attempting Tavily fallback",
                    eval_result.get("reason", "")[:60],
                )
                answer, fallback_timings = _tavily_fallback(
                    question=question,
                    answer=answer,
                    tavily_tool=tavily_tool,
                    chat_model=chat_model,
                    history=trimmed,
                )
                timings_ms.update(fallback_timings)
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
            cfg.get("self_eval_min_top_score", _SELF_EVAL_SCORE_THRESHOLD),
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
        "answer": answer,
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
    }


def rag_flow_stream(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    reflector: Any | None,
    bge_embedder: BaseEmbedder,
    e5_embedder: BaseEmbedder,
    searcher: Any,
    reranker: BaseReranker,
    chat_model: BaseLLM,
    cfg: Dict[str, Any],
    routing_result: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    validity_filter: Any | None = None,
    reference_resolver: Any | None = None,
    timings_ms_out: Optional[Dict[str, float]] = None,
    metadata_out: Optional[Dict[str, Any]] = None,
) -> tuple[Generator[str, None, None], List[Dict[str, Any]]]:
    """Streaming RAG flow — retrieval runs first, then generation is streamed.

    Returns:
        A tuple of (text_chunk_generator, reranked_sources).
    """
    flow_t0 = time.perf_counter()
    timings_ms = timings_ms_out if timings_ms_out is not None else {}

    step_t0 = time.perf_counter()
    trimmed = _trim_history(history)
    timings_ms["trim_history"] = _elapsed_ms(step_t0)

    # Reflection
    search_query = question
    resolved_major: Optional[str] = None
    resolved_cohort: Optional[str] = None
    if reflector is not None:
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
            resolved_major = entities.get("major_code") or entities.get("major_name")
            cohort_entity = entities.get("cohort")
            if cohort_entity is not None:
                resolved_cohort = str(cohort_entity).strip() or None
        except Exception:
            logger.warning("Reflection failed, using original query", exc_info=True)
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
            resolved_major = (
                fallback_entities.get("major_code")
                or fallback_entities.get("major_name")
            )
        if not resolved_cohort:
            cohort_entity = fallback_entities.get("cohort")
            if cohort_entity is not None:
                resolved_cohort = str(cohort_entity).strip() or None

        if resolved_major:
            logger.info("Major fallback resolved: %s", resolved_major)
        if resolved_cohort:
            logger.info("Cohort fallback resolved: %s", resolved_cohort)

    retrieval_query = search_query

    # Collection-aware routing (Phase 8 — Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    if routing_result:
        routing_t0 = time.perf_counter()
        domain = routing_result.get("domain")
        domains = routing_result.get("domains") or ([domain] if domain else [])
        confidence = routing_result.get("confidence", 0.0)
        target_collections = _collection_selector.select(
            domain=domain,
            confidence=confidence,
            domains=domains,
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

    # ── Populate metadata_out early (pre-generation) so caller can read it ──────
    # The search_trace dict is mutated later; we update metadata_out after rerank.
    if metadata_out is not None:
        metadata_out["reflected_question"] = search_query
        metadata_out["target_collections"] = target_collections
        metadata_out["routing_probabilities"] = (
            routing_result.get("probabilities") if routing_result else None
        )

    top_k_value = cfg.get("top_k", 5)
    raw_candidate_k = _retrieval_candidate_k(top_k_value)
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
        stripped = strip_cohort_comparison_scaffold_for_retrieval(retrieval_query)
        if len(stripped.split()) >= 2:
            rerank_query = stripped

    # Embed → Search → Rerank
    search_trace: Dict[str, Any] = {}  # filters/counts not wired in stream path

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
            resolved_major if use_outer_resolved_major else local_resolved_major
        )
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
        )
        timings_ms["search"] = round(
            timings_ms.get("search", 0.0) + _elapsed_ms(search_t0),
            2,
        )
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
        fallback_compare_query = search_query if major_compare_plan else retrieval_query
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
        compare_source_query = search_query if major_compare_plan else retrieval_query
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

    rerank_t0 = time.perf_counter()
    
    rerank_query = expand_major_in_query_for_reranking(rerank_query, resolved_major)

    reranked = reranker.rerank(
        query=rerank_query,
        documents=raw_results,
        top_k=top_k_value,
    )
    timings_ms["rerank"] = _elapsed_ms(rerank_t0)
    logger.info("Reranked to %d documents", len(reranked))

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

    context_t0 = time.perf_counter()
    context = _format_context(reranked)
    profile_note = ""
    if _should_prepend_profile_note(question):
        profile_note = (
            _build_profile_note_from_user_context(user_context)
            or _extract_session_profile(history)
        )
    full_context = f"{profile_note}\n\n---\n\n{context}" if profile_note else context
    timings_ms["format_context"] = _elapsed_ms(context_t0)
    timings_ms["retrieval_total"] = round(
        timings_ms.get("embed_bge", 0.0)
        + timings_ms.get("embed_e5", 0.0)
        + timings_ms.get("search", 0.0)
        + timings_ms.get("rerank", 0.0)
        + timings_ms.get("format_context", 0.0),
        2,
    )

    # ── Final metadata update (post-rerank, pre-stream) ──────────────────────────
    if metadata_out is not None:
        metadata_out["num_sources"] = len(reranked)
        metadata_out["collection_scores"] = _build_collection_scores(
            all_collections=cfg.get("collections"),
            target_collections=target_collections,
            routing_result=routing_result,
        )
        metadata_out["applied_filters"] = search_trace.get("filters")
        metadata_out["collection_results"] = search_trace.get("collection_counts")

    generate_stream = chat_model.generate_stream(
        query=question, context=full_context, history=trimmed, mode="rag"
    )
    def _timed_stream() -> Generator[str, None, None]:
        stream_t0 = time.perf_counter()
        first_token_ms: Optional[float] = None
        generated_chars = 0

        for chunk in generate_stream:
            if first_token_ms is None:
                first_token_ms = _elapsed_ms(stream_t0)
            generated_chars += len(chunk)
            yield chunk

        timings_ms["stream_first_token"] = round(first_token_ms or 0.0, 2)
        timings_ms["stream_generate"] = _elapsed_ms(stream_t0)
        timings_ms["flow_total"] = _elapsed_ms(flow_t0)
        logger.info("rag_flow_stream: streamed %d chars", generated_chars)
        _log_timings("rag_flow_stream", timings_ms)

    return _timed_stream(), reranked


# ═══════════════════════════════════════════════════════════════════════════════
# Tavily Fallback
# ═══════════════════════════════════════════════════════════════════════════════


def _tavily_fallback(
    *,
    question: str,
    answer: str,
    tavily_tool: Any | None,
    chat_model: BaseLLM,
    history: List[Dict[str, str]],
) -> tuple[str, Dict[str, float]]:
    """Use Tavily web search to re-generate the answer when self-eval fails."""
    fallback_t0 = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    if tavily_tool is None:
        logger.info("No Tavily tool configured, returning original answer")
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return answer, timings_ms

    try:
        search_t0 = time.perf_counter()
        search_result = tavily_tool.search(question)
        timings_ms["tavily_search"] = _elapsed_ms(search_t0)

        web_context = search_result.get("context", "")
        if not web_context:
            timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
            return answer, timings_ms

        regenerate_t0 = time.perf_counter()
        new_answer = chat_model.generate(
            query=question,
            context=web_context,
            history=history,
            mode="rag",
        )
        timings_ms["tavily_generate"] = _elapsed_ms(regenerate_t0)
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        logger.info("Tavily fallback generated %d chars", len(new_answer))
        return new_answer, timings_ms
    except Exception:
        logger.warning(
            "Tavily fallback failed, returning original answer", exc_info=True
        )
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return answer, timings_ms
