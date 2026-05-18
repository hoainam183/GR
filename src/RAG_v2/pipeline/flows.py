"""Pipeline Flows — chitchat and RAG flow definitions."""

from __future__ import annotations

import logging
import re
import time
import unicodedata
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
# BGE reranker scores are raw logits, not probabilities. The high default avoids
# skipping self-eval for logits like 5.25 that would dwarf a probability threshold.
_SELF_EVAL_SCORE_THRESHOLD = 100.0  # run self-eval only when top score < this
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
    r"\b(?:IT|MI|ME|EE|EV|CH|BF|MS|HE|TE|TX|TROY)"
    r"\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]?\s*"
    r"(?:E18|E15|E12|E11|E10|E8|E7|E6|E3|E1|EP|GU|LUH|NUT|IT|1|2|3|5)\b",
    re.IGNORECASE,
)

# Detect "list-all" queries: asking to enumerate multiple items.
# Examples: "các học phần tiếng nhật", "tất cả môn bắt buộc", "danh sách học phần"
_LIST_QUERY_RE = re.compile(
    r"\b(?:các|tất\s+cả|danh\s*sách|liệt\s*kê|những|bao\s+gồm\s+những|toàn\s+bộ|hết)\b",
    re.IGNORECASE,
)
_LIST_TOP_K_MULTIPLIER = 2   # double top_k for list queries
_LIST_TOP_K_MAX = 12         # cap to avoid excessive reranking latency

_WEB_FALLBACK_DEFAULT_DYNAMIC_COLLECTIONS = ("kehoach",)
_WEB_FALLBACK_NO_INFO_PATTERNS = (
    "toi khong tim thay thong tin nay trong tai lieu hien co",
    "khong tim thay thong tin",
    "khong co thong tin",
    "chua co thong tin",
    "khong du co so",
    "khong du thong tin",
    "tai lieu hien co khong",
    "chua tim thay",
)
_WEB_FALLBACK_DYNAMIC_QUERY_RE = re.compile(
    r"\b(?:"
    r"ke\s*hoach|thong\s*bao|lich\s*(?:thi|dang\s*ky|hoc)|"
    r"han\s*(?:dang\s*ky|nop)|deadline|ky\s*he|ki\s*he|hoc\s*ky\s*he|"
    r"nam\s*hoc\s*\d{4}\s*[-/]\s*\d{4}|20\d{2}3|20\d{2}1"
    r")\b",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════════


def _elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds rounded for compact logs/JSON."""
    return round((time.perf_counter() - start) * 1000, 2)


def _log_timings(flow_name: str, timings_ms: Dict[str, Any]) -> None:
    """Log timing breakdown sorted by slowest stage first."""
    if not timings_ms:
        return
    numeric_timings = {
        stage: duration
        for stage, duration in timings_ms.items()
        if isinstance(duration, (int, float))
    }
    if not numeric_timings:
        return
    ordered = sorted(
        numeric_timings.items(), key=lambda item: item[1], reverse=True
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
    return max(top_k * 4, 40)


def _resolve_top_k(base_top_k: int, query: str) -> int:
    """Return an effective top_k, scaled up for list/enumerate queries.

    When the user asks to enumerate multiple items ("các học phần",
    "tất cả môn", "danh sách", …) a single topic can span many chunks.
    Doubling top_k (capped at _LIST_TOP_K_MAX) prevents truncating the
    result set before the LLM sees all relevant items.
    """
    if _LIST_QUERY_RE.search(query or ""):
        scaled = base_top_k * _LIST_TOP_K_MULTIPLIER
        effective = min(scaled, _LIST_TOP_K_MAX)
        if effective > base_top_k:
            logger.info(
                "List query detected — top_k scaled %d → %d",
                base_top_k,
                effective,
            )
        return effective
    return base_top_k


def _should_strip_major_for_retrieval(
    *,
    resolved_major: Optional[str],
    target_collections: Optional[List[str]],
) -> bool:
    """Return True when major phrases should be stripped from retrieval query.

    Keeping major mentions is important when routing includes quydinh,
    because quydinh does not use ``major_code`` metadata filters and therefore
    relies on lexical/semantic major cues in the query text itself.

    We protect major mentions whenever quydinh is *present* (not only when
    it is the *sole* target), because multi-domain routing (e.g. quydinh +
    ctdt) should still allow quydinh chunks to match via keyword signals.
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
    if "quydinh" in normalized_targets:
        return False
    return True


def _safe_float(value: Any) -> float:
    """Return *value* as float, or 0.0 when conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cfg_bool(cfg: Dict[str, Any], key: str, default: bool) -> bool:
    """Read a boolean config value with string/env compatibility."""
    value = cfg.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _cfg_str_list(
    cfg: Dict[str, Any],
    key: str,
    default: tuple[str, ...],
) -> List[str]:
    """Read a list config value from a list/tuple/set or comma string."""
    value = cfg.get(key, default)
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = list(default)
    return [str(item).strip().lower() for item in items if str(item).strip()]


def _fold_vietnamese(text: str) -> str:
    """Lowercase and strip Vietnamese accents for robust text matching."""
    decomposed = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(
        ch for ch in decomposed if unicodedata.category(ch) != "Mn"
    )
    return without_marks.replace("đ", "d").replace("Đ", "d").lower()


def _answer_has_no_info_signal(answer: str) -> bool:
    """Detect local-RAG no-information answers without another LLM call."""
    folded = _fold_vietnamese(answer)
    return any(pattern in folded for pattern in _WEB_FALLBACK_NO_INFO_PATTERNS)


def _selected_collections(
    *,
    target_collections: Optional[List[str]],
    routing_result: Optional[Dict[str, Any]],
) -> set[str]:
    """Return collection names selected by routing/collection selection."""
    selected = {
        str(col).strip().lower()
        for col in (target_collections or [])
        if str(col).strip()
    }
    if routing_result:
        domain = routing_result.get("domain")
        if domain:
            selected.add(str(domain).strip().lower())
        domains = routing_result.get("domains") or []
        for item in domains:
            if str(item).strip():
                selected.add(str(item).strip().lower())
    return selected


def _is_dynamic_web_query(
    *,
    question: str,
    search_query: str,
    target_collections: Optional[List[str]],
    routing_result: Optional[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> bool:
    """Return True for queries whose answer may change faster than local index."""
    dynamic_collections = set(
        _cfg_str_list(
            cfg,
            "web_fallback_dynamic_collections",
            _WEB_FALLBACK_DEFAULT_DYNAMIC_COLLECTIONS,
        )
    )
    selected = _selected_collections(
        target_collections=target_collections,
        routing_result=routing_result,
    )
    if selected & dynamic_collections:
        return True

    folded = _fold_vietnamese(f"{question}\n{search_query}")
    return bool(_WEB_FALLBACK_DYNAMIC_QUERY_RE.search(folded))


def _should_bypass_query_cache(
    *,
    question: str,
    search_query: str,
    target_collections: Optional[List[str]],
    routing_result: Optional[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> bool:
    """Avoid early cache hits for dynamic data that may need live refresh."""
    return _is_dynamic_web_query(
        question=question,
        search_query=search_query,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
    )


def _build_web_search_query(question: str, search_query: str) -> str:
    """Build a compact official-web query without another LLM call."""
    query = (search_query or question or "").strip().strip(" ?!.")
    if not query:
        query = (question or "").strip()
    folded = _fold_vietnamese(query)
    has_hust_context = any(
        token in folded
        for token in ("hust", "bach khoa", "dai hoc bach khoa", "dhbk")
    )
    return query if has_hust_context else f"HUST {query}"


def _build_pre_generation_web_decision(
    *,
    question: str,
    search_query: str,
    reranked: List[Dict[str, Any]],
    target_collections: Optional[List[str]],
    routing_result: Optional[Dict[str, Any]],
    cfg: Dict[str, Any],
    low_retrieval_confidence: bool = False,
) -> Dict[str, Any]:
    """Decide whether official web context should be fetched before generation."""
    dynamic_query = _is_dynamic_web_query(
        question=question,
        search_query=search_query,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
    )
    no_sources = len(reranked) == 0
    reasons: List[str] = []
    if no_sources:
        reasons.append("no_sources")
    if dynamic_query and _cfg_bool(cfg, "web_fallback_on_dynamic", True):
        reasons.append("dynamic_query")
    if low_retrieval_confidence:
        reasons.append("low_retrieval_confidence")

    answer_status = "answered"
    if no_sources:
        answer_status = "insufficient"
    elif dynamic_query:
        answer_status = "stale_risk"

    return {
        "answer_status": answer_status,
        "should_web_search": bool(reasons),
        "web_search_query": _build_web_search_query(question, search_query),
        "reasons": reasons,
        "dynamic_query": dynamic_query,
        "no_sources": no_sources,
        "low_retrieval_confidence": low_retrieval_confidence,
    }


def _build_answer_quality_gate(
    *,
    question: str,
    search_query: str,
    answer: str,
    reranked: List[Dict[str, Any]],
    target_collections: Optional[List[str]],
    routing_result: Optional[Dict[str, Any]],
    eval_result: Optional[Dict[str, Any]],
    cfg: Dict[str, Any],
    pre_web_fallback_used: bool = False,
) -> Dict[str, Any]:
    """Decide whether local RAG needs official web fallback."""
    no_info = (
        _cfg_bool(cfg, "web_fallback_on_no_info", True)
        and _answer_has_no_info_signal(answer)
    )
    no_sources = len(reranked) == 0
    dynamic_query = _is_dynamic_web_query(
        question=question,
        search_query=search_query,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
    )
    eval_failed = bool(eval_result is not None and not eval_result.get("pass", True))
    eval_wants_web = bool(eval_result and eval_result.get("should_web_search"))
    eval_status = str(eval_result.get("answer_status") or "") if eval_result else ""
    eval_web_request = eval_wants_web and eval_status in {"insufficient", "stale_risk"}

    # Post-generation Tavily only runs for explicit insufficiency signals.
    # Dynamic queries are handled by the pre-generation web decision path.
    reasons: List[str] = []
    if no_info:
        reasons.append("answer_no_info")
    if no_sources:
        reasons.append("no_sources")
    if eval_web_request:
        reasons.append("self_eval_requested_web")

    # Tracked for answer_status / debugging. A structured self-eval web request
    # only triggers fallback when paired with an insufficient/stale status above.
    informational_notes: List[str] = []
    if eval_failed:
        informational_notes.append("self_eval_failed")
    if eval_wants_web:
        informational_notes.append("self_eval_requested_web")
    if dynamic_query:
        informational_notes.append("dynamic_query")
    if pre_web_fallback_used:
        informational_notes.append("pre_generation_web_used")

    answer_status = "answered"
    if no_info or no_sources:
        answer_status = "insufficient"
    elif dynamic_query:
        answer_status = "stale_risk"
    elif eval_result:
        answer_status = str(eval_result.get("answer_status") or "answered")
        if answer_status not in {"answered", "insufficient", "stale_risk"}:
            answer_status = "answered"

    should_web_search = bool(reasons) and not pre_web_fallback_used
    web_query = ""
    if eval_result:
        web_query = str(eval_result.get("web_search_query") or "").strip()
    if not web_query:
        web_query = _build_web_search_query(question, search_query)

    return {
        "answer_status": answer_status,
        "should_web_search": should_web_search,
        "web_search_query": web_query,
        "reasons": reasons,
        "informational_notes": informational_notes,
        "no_info": no_info,
        "no_sources": no_sources,
        "dynamic_query": dynamic_query,
        "self_eval_failed": eval_failed,
    }


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

    incoming_weights = trace_piece.get("fusion_weights")
    if isinstance(incoming_weights, dict):
        aggregate_trace.setdefault("fusion_weights", incoming_weights)
        events = aggregate_trace.setdefault("fusion_weight_events", [])
        if isinstance(events, list):
            events.append(incoming_weights)


def _format_context(
    documents: List[Dict[str, Any]],
    *,
    per_doc_char_limit: int = _DEFAULT_CONTEXT_DOC_CHAR_LIMIT,
    total_char_budget: int = _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET,
    trace_out: Optional[Dict[str, Any]] = None,
) -> str:
    """Convert retrieved documents into a token-budgeted context string.

    Limits per-document and total context size to prevent context-length
    errors and keep LLM latency predictable regardless of chunk sizes.
    """
    parts: List[str] = []
    used = 0
    docs_used = 0
    for i, doc in enumerate(documents, 1):
        meta = doc.get("metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or "Tài liệu không rõ nguồn"
        
        # Inject metadata into document header so the LLM is aware of the program/major context
        meta_parts = []
        if meta.get("major_code"):
            meta_parts.append(f"Mã ngành: {meta['major_code']}")
        if meta.get("major_name"):
            meta_parts.append(f"Ngành: {meta['major_name']}")
        if meta.get("applicable_cohort"):
            meta_parts.append(f"Khóa: {meta['applicable_cohort']}")
        # For kehoach docs: include posting date and URL so the LLM can cite
        # the newest source and the user can verify freshness.
        if doc.get("collection") == "kehoach":
            if meta.get("date_str"):
                meta_parts.append(f"Ngày đăng: {meta['date_str']}")
            if meta.get("url"):
                meta_parts.append(f"URL: {meta['url']}")
        meta_str = f" [{', '.join(meta_parts)}]" if meta_parts else ""
        
        text = str(doc.get("text", "") or "").strip()
        if len(text) > per_doc_char_limit:
            text = text[:per_doc_char_limit] + "\u2026"  # ellipsis
        chunk = f"--- Văn bản: {title}{meta_str}\n{text}"
        separator_cost = 7 if parts else 0  # len("\n\n---\n\n")
        if used + len(chunk) + separator_cost > total_char_budget:
            break
        parts.append(chunk)
        docs_used += 1
        used += len(chunk) + separator_cost
    context = "\n\n---\n\n".join(parts)
    if trace_out is not None:
        trace_out["context_chars"] = len(context)
        trace_out["context_docs_used"] = docs_used
        trace_out["context_docs_dropped"] = max(0, len(documents) - docs_used)
        trace_out["context_doc_char_limit"] = per_doc_char_limit
        trace_out["context_total_char_budget"] = total_char_budget
    return context


def _cfg_int(cfg: Dict[str, Any], key: str, default: int) -> int:
    """Read an integer config value with a safe fallback."""
    try:
        return int(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _resolve_context_budget(
    cfg: Dict[str, Any],
    *,
    top_k_value: int,
) -> tuple[int, int]:
    """Return (per_doc_limit, total_budget) for the current query."""
    base_top_k = _cfg_int(cfg, "top_k", 5)
    per_doc_limit = _cfg_int(
        cfg, "context_doc_char_limit", _DEFAULT_CONTEXT_DOC_CHAR_LIMIT
    )
    base_budget = _cfg_int(
        cfg, "context_total_char_budget", _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET
    )
    list_budget = _cfg_int(
        cfg,
        "context_list_total_char_budget",
        base_budget * _LIST_TOP_K_MULTIPLIER,
    )
    total_budget = list_budget if top_k_value > base_top_k else base_budget
    return per_doc_limit, total_budget


def _build_rerank_trace(
    *,
    reranker: Optional[BaseReranker],
    candidate_count: int,
    reranked: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build compact reranker observability fields."""
    last_stats = getattr(reranker, "last_stats", None)
    if isinstance(last_stats, dict):
        return dict(last_stats)

    scores = [
        float(doc["rerank_score"])
        for doc in reranked
        if isinstance(doc, dict) and doc.get("rerank_score") is not None
    ]
    trace: Dict[str, Any] = {
        "rerank_candidate_count": candidate_count,
        "rerank_returned_count": len(reranked),
        "rerank_dropped_count": max(0, candidate_count - len(reranked)),
    }
    if scores:
        trace.update(
            {
                "rerank_score_min": round(min(scores), 6),
                "rerank_score_max": round(max(scores), 6),
                "rerank_score_mean": round(sum(scores) / len(scores), 6),
            }
        )
    return trace


def _best_explicit_rerank_score(
    documents: List[Dict[str, Any]],
) -> Optional[float]:
    """Return max rerank_score, or None when docs do not expose that field."""
    scores = [
        _safe_float(doc.get("rerank_score"))
        for doc in documents
        if isinstance(doc, dict) and doc.get("rerank_score") is not None
    ]
    return max(scores) if scores else None


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

    # ── Pre-retrieval query cache (P0) ───────────────────────────────────────
    # Check before reflection + retrieval to save the full ~13-25 s pipeline
    # cost for repeated identical queries.  Only fires when the cache backend
    # exposes get_by_query (LLMResponseCache with Redis).
    if (
        llm_cache is not None
        and not bypass_query_cache
        and hasattr(llm_cache, "get_by_query")
    ):
        _qcached = llm_cache.get_by_query(question, chat_model.model)
        if _qcached is not None:
            if _answer_has_no_info_signal(str(_qcached.get("answer", ""))):
                timings_ms["query_cache_ignored_no_info"] = 1.0
            else:
                timings_ms["query_cache_hit"] = 1.0
                timings_ms["flow_total"] = _elapsed_ms(flow_t0)
                return {
                    "question": question,
                    "answer": _qcached["answer"],
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
                    "llm_prompt": "(query_cached)",
                    "applied_filters": None,
                    "collection_results": None,
                }

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
            raw_results_buffer.extend(
                _search_once(sq_query, sq_collections)
            )
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
    assert reranker is not None, "reranker must be provided"
    reranked = reranker.rerank(
        query=rerank_query,
        documents=raw_results,
        top_k=top_k_value,
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
    # from the original intent), retry with the original question.  This prevents
    # an issue where reflection adds speculative terms that reduce cross-encoder
    # scores below the threshold for otherwise topically-relevant documents.
    # Also trigger when all surviving docs have negative scores (only table-docs
    # passed through the relaxed table_score_threshold but no regular content matched).
    _best_rerank_score = _best_explicit_rerank_score(reranked)
    _rerank_quality_ok = _best_rerank_score is None or _best_rerank_score >= 0.0
    if raw_results and not _rerank_quality_ok:
        logger.info(
            "Reranker gave no positive-score candidates (best=%.3f, n=%d). "
            "Retrying rerank with original question.",
            _best_rerank_score if _best_rerank_score is not None else -999.0,
            len(raw_results),
        )
        reranked = reranker.rerank(
            query=question,
            documents=raw_results,
            top_k=top_k_value,
        )
        timings_ms["rerank_fallback"] = 1.0
        retry_best_score = _best_explicit_rerank_score(reranked)
        if not reranked or (
            retry_best_score is not None and retry_best_score < 0.0
        ):
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

    # ── LLM Response Cache Check (Phase 2) ─────────────────────────
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
    web_fallback_query = str(pre_web_decision.get("web_search_query") or search_query)
    pre_web_fallback_reasons = list(pre_web_decision.get("reasons") or [])
    if pre_web_decision["should_web_search"]:
        timings_ms["web_fallback_requested"] = 1.0
        if cfg.get("tavily_fallback_enabled", False):
            search_info = _tavily_search_context(
                query=web_fallback_query,
                tavily_tool=tavily_tool,
                max_results=_cfg_int(cfg, "tavily_max_results", 3),
                search_depth=str(cfg.get("tavily_search_depth", "basic") or "basic"),
            )
            timings_ms.update(search_info["timings"])
            web_fallback_sources = list(search_info.get("sources") or [])
            if search_info.get("used"):
                web_fallback_used = True
                pre_web_fallback_used = True
                timings_ms["web_fallback_used"] = 1.0
                web_context_override = str(search_info.get("context") or "")
                if web_fallback_sources:
                    reranked = web_fallback_sources + reranked
        else:
            timings_ms["tavily_skipped"] = 1.0

    if llm_cache is not None and not dynamic_web_query and not pre_web_fallback_reasons:
        doc_ids = [str(doc.get("id", "")) for doc in reranked if doc.get("id")]
        cached = llm_cache.get(question, doc_ids, chat_model.model)
        if cached is not None:
            if _answer_has_no_info_signal(str(cached.get("answer", ""))):
                timings_ms["llm_cache_ignored_no_info"] = 1.0
            else:
                logger.info("LLM cache HIT for query: %r", question[:80])
                timings_ms["llm_cache_hit"] = 1.0
                timings_ms["flow_total"] = _elapsed_ms(flow_t0)
                return {
                    "question": question,
                    "answer": cached["answer"],
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
                    "cache_hit": True,
                }


    # 6. Format context — inject profile so user facts survive trimming.
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
            doc for doc in reranked
            if str(doc.get("collection") or "").lower() != "web"
        ]
    context = _format_context(
        context_documents,
        per_doc_char_limit=context_doc_limit,
        total_char_budget=context_char_budget,
        trace_out=context_trace,
    )
    if web_context_override:
        if context:
            context = (
                f"## Nguồn Web (thông tin mới nhất từ trang chính thức HUST)\n"
                f"{web_context_override}\n\n---\n\n"
                f"## Nguồn Cơ Sở Dữ Liệu Nội Bộ (thông tin đã được kiểm duyệt)\n"
                f"{context}\n\n"
                f"Lưu ý: Nếu hai nguồn mâu thuẫn về thời gian/năm học, ưu tiên Nguồn Web."
            )
        else:
            context = web_context_override
    profile_note = ""
    if _should_prepend_profile_note(question):
        profile_note = (
            _build_profile_note_from_user_context(user_context)
            or _extract_session_profile(history)
        )
    full_context = f"{profile_note}\n\n---\n\n{context}" if profile_note else context
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
    self_eval_threshold = cfg.get(
        "self_eval_min_top_score",
        _SELF_EVAL_SCORE_THRESHOLD,
    )
    run_self_eval = self_evaluator is not None and top_score < self_eval_threshold
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
    timings_ms[f"answer_status_{answer_quality_gate['answer_status']}"] = 1.0
    if answer_quality_gate["should_web_search"]:
        timings_ms["web_fallback_requested"] = 1.0
        logger.info(
            "AnswerQualityGate requested web fallback: status=%s reasons=%s",
            answer_quality_gate["answer_status"],
            answer_quality_gate["reasons"],
        )

    answer_quality_gate["pre_generation_reasons"] = pre_web_fallback_reasons
    answer_quality_gate["pre_generation_web_used"] = pre_web_fallback_used
    web_fallback_query = str(
        answer_quality_gate.get("web_search_query") or web_fallback_query or search_query
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
                search_depth=str(cfg.get("tavily_search_depth", "basic") or "basic"),
                search_query=web_fallback_query,
            )
            timings_ms.update(fallback_result["timings"])
            if fallback_result["used"]:
                answer = str(fallback_result["answer"])
                web_fallback_used = True
                timings_ms["web_fallback_used"] = 1.0
                web_fallback_sources = list(fallback_result.get("sources") or [])
                if web_fallback_sources:
                    reranked = web_fallback_sources + reranked
        else:
            timings_ms["tavily_skipped"] = 1.0
            logger.info("AnswerQualityGate requested web fallback, but Tavily is disabled")

    cache_final_answer = (
        not answer_quality_gate["should_web_search"]
        or web_fallback_used
    )
    if llm_cache is not None and cache_final_answer:
        doc_ids = [str(doc.get("id", "")) for doc in reranked if doc.get("id")]
        llm_cache.put(question, doc_ids, chat_model.model, answer, reranked)

    if (
        llm_cache is not None
        and hasattr(llm_cache, "put_by_query")
        and cache_final_answer
        and not web_fallback_used
        and not dynamic_web_query
        and not answer_quality_gate["should_web_search"]
    ):
        llm_cache.put_by_query(question, chat_model.model, answer, reranked)
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
        "fusion_weights": search_trace.get("fusion_weights"),
        "context_trace": context_trace,
        "rerank_trace": rerank_trace,
        "answer_status": answer_quality_gate["answer_status"],
        "answer_quality_gate": answer_quality_gate,
        "tools_used": ["tavily_search"] if timings_ms.get("tavily_search") else [],
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
) -> tuple[Generator[str, None, None], List[Dict[str, Any]]]:
    """Streaming RAG flow — retrieval runs first, then generation is streamed.

    Returns:
        A tuple of (text_chunk_generator, reranked_sources).
    """
    flow_t0 = time.perf_counter()
    timings_ms: Dict[str, Any] = timings_ms_out if timings_ms_out is not None else {}

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

    # ── Pre-retrieval query cache (P0 — stream variant) ──────────────────────
    if (
        llm_cache is not None
        and not bypass_query_cache
        and hasattr(llm_cache, "get_by_query")
    ):
        _qcached = llm_cache.get_by_query(question, chat_model.model)
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
                    metadata_out["tools_used"] = []
                    metadata_out["tool_calls"] = []

                def _cached_stream_early() -> Generator[str, None, None]:
                    yield _qcached["answer"]

                return _cached_stream_early(), _qcached["sources"]

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

    dynamic_web_query = _is_dynamic_web_query(
        question=question,
        search_query=search_query,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
    )
    if dynamic_web_query:
        timings_ms["dynamic_web_query"] = 1.0

    # ── Populate metadata_out early (pre-generation) so caller can read it ──────
    # The search_trace dict is mutated later; we update metadata_out after rerank.
    if metadata_out is not None:
        metadata_out["reflected_question"] = search_query
        metadata_out["target_collections"] = target_collections
        metadata_out["routing_probabilities"] = (
            routing_result.get("probabilities") if routing_result else None
        )

    top_k_value = _resolve_top_k(cfg.get("top_k", 5), question)
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
            resolved_major if use_outer_resolved_major else local_resolved_major
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
    assert reranker is not None, "reranker must be provided"
    reranked = reranker.rerank(
        query=rerank_query,
        documents=raw_results,
        top_k=top_k_value,
    )
    timings_ms["rerank"] = _elapsed_ms(rerank_t0)
    rerank_trace = _build_rerank_trace(
        reranker=reranker,
        candidate_count=len(raw_results),
        reranked=reranked,
    )
    logger.info("Reranked to %d documents", len(reranked))

    # Fallback: same logic as rag_flow — trigger when all surviving reranked
    # docs have negative scores (reflected query drift or only table-threshold
    # docs survived).
    _best_rerank_score_s = _best_explicit_rerank_score(reranked)
    if (
        raw_results
        and _best_rerank_score_s is not None
        and _best_rerank_score_s < 0.0
    ):
        logger.info(
            "Stream: reranker gave no positive-score candidates (best=%.3f). "
            "Retrying with original question.",
            _best_rerank_score_s,
        )
        reranked = reranker.rerank(
            query=question,
            documents=raw_results,
            top_k=top_k_value,
        )
        timings_ms["rerank_fallback"] = 1.0
        retry_best_score_s = _best_explicit_rerank_score(reranked)
        if not reranked or (
            retry_best_score_s is not None and retry_best_score_s < 0.0
        ):
            logger.info(
                "Stream: reranker still no positive candidates. Using raw fusion top-%d.",
                top_k_value,
            )
            reranked = sorted(
                raw_results, key=lambda d: d.get("score", 0.0), reverse=True
            )[:top_k_value]
            timings_ms["rerank_raw_fallback"] = 1.0

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
    web_fallback_query = str(web_decision.get("web_search_query") or search_query)
    web_fallback_reasons: List[str] = list(web_decision.get("reasons") or [])

    web_context_override = ""
    if web_fallback_reasons:
        timings_ms["web_fallback_requested"] = 1.0
        if cfg.get("tavily_fallback_enabled", False):
            search_info = _tavily_search_context(
                query=web_fallback_query,
                tavily_tool=tavily_tool,
                max_results=_cfg_int(cfg, "tavily_max_results", 3),
                search_depth=str(cfg.get("tavily_search_depth", "basic") or "basic"),
            )
            timings_ms.update(search_info["timings"])
            web_sources = list(search_info.get("sources") or [])
            if search_info.get("used"):
                web_fallback_used = True
                timings_ms["web_fallback_used"] = 1.0
                web_context_override = str(search_info.get("context") or "")
                if web_sources:
                    reranked = web_sources + reranked
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
            doc for doc in reranked
            if str(doc.get("collection") or "").lower() != "web"
        ]
    context = _format_context(
        context_documents,
        per_doc_char_limit=context_doc_limit,
        total_char_budget=context_char_budget,
        trace_out=context_trace,
    )
    if web_context_override:
        if context:
            context = (
                f"## Nguồn Web (thông tin mới nhất từ trang chính thức HUST)\n"
                f"{web_context_override}\n\n---\n\n"
                f"## Nguồn Cơ Sở Dữ Liệu Nội Bộ (thông tin đã được kiểm duyệt)\n"
                f"{context}\n\n"
                f"Lưu ý: Nếu hai nguồn mâu thuẫn về thời gian/năm học, ưu tiên Nguồn Web."
            )
        else:
            context = web_context_override
    profile_note = ""
    if _should_prepend_profile_note(question):
        profile_note = (
            _build_profile_note_from_user_context(user_context)
            or _extract_session_profile(history)
        )
    full_context = f"{profile_note}\n\n---\n\n{context}" if profile_note else context
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
        metadata_out["fusion_weights"] = search_trace.get("fusion_weights")
        metadata_out["context_trace"] = context_trace
        metadata_out["rerank_trace"] = rerank_trace
        metadata_out["answer_quality_gate"] = {
            "answer_status": web_decision["answer_status"],
            "should_web_search": bool(web_fallback_reasons),
            "web_search_query": web_fallback_query,
            "reasons": web_fallback_reasons,
            "dynamic_query": dynamic_web_query,
            "no_sources": "no_sources" in web_fallback_reasons,
            "low_retrieval_confidence": "low_retrieval_confidence" in web_fallback_reasons,
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

    # ── LLM Response Cache Check (Phase 2 - Stream) ─────────────────
    if (
        llm_cache is not None
        and not dynamic_web_query
        and not web_fallback_used
        and not web_fallback_reasons
    ):
        doc_ids = [str(doc.get("id", "")) for doc in reranked if doc.get("id")]
        cached = llm_cache.get(question, doc_ids, chat_model.model)
        if cached is not None:
            if _answer_has_no_info_signal(str(cached.get("answer", ""))):
                timings_ms["llm_cache_ignored_no_info"] = 1.0
            else:
                logger.info("LLM cache HIT (stream) for query: %r", question[:80])
                timings_ms["llm_cache_hit"] = 1.0

                def _cached_stream() -> Generator[str, None, None]:
                    yield cached["answer"]
                    timings_ms["stream_first_token"] = 0.1
                    timings_ms["stream_generate"] = 0.1
                    timings_ms["flow_total"] = _elapsed_ms(flow_t0)
                    _log_timings("rag_flow_stream_cached", timings_ms)

                return _cached_stream(), cached["sources"]

    generate_stream = chat_model.generate_stream(
        query=question, context=full_context, history=trimmed, mode="rag"
    )
    def _timed_stream() -> Generator[str, None, None]:
        stream_t0 = time.perf_counter()
        first_token_ms: Optional[float] = None
        generated_chars = 0
        full_cached_answer = []

        for chunk in generate_stream:
            if first_token_ms is None:
                first_token_ms = _elapsed_ms(stream_t0)
            generated_chars += len(chunk)
            full_cached_answer.append(chunk)
            yield chunk

        timings_ms["stream_first_token"] = round(first_token_ms or 0.0, 2)
        timings_ms["stream_generate"] = _elapsed_ms(stream_t0)
        timings_ms["flow_total"] = _elapsed_ms(flow_t0)
        logger.info("rag_flow_stream: streamed %d chars", generated_chars)
        _log_timings("rag_flow_stream", timings_ms)

        # Cache newly generated stream response (Phase 2)
        cache_stream_answer = not web_fallback_reasons or web_fallback_used
        if llm_cache is not None and cache_stream_answer:
            doc_ids = [str(doc.get("id", "")) for doc in reranked if doc.get("id")]
            llm_cache.put(
                question,
                doc_ids,
                chat_model.model,
                "".join(full_cached_answer),
                reranked,
            )

        # Also populate the pre-retrieval query-only cache.
        if (
            llm_cache is not None
            and hasattr(llm_cache, "put_by_query")
            and not dynamic_web_query
            and not web_fallback_used
            and not web_fallback_reasons
        ):
            llm_cache.put_by_query(question, chat_model.model, "".join(full_cached_answer), reranked)

    return _timed_stream(), reranked


# ═══════════════════════════════════════════════════════════════════════════════
# Tavily Fallback
# ═══════════════════════════════════════════════════════════════════════════════


def _tavily_results_to_docs(search_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert Tavily results into source docs compatible with response mapping."""
    docs: List[Dict[str, Any]] = []
    for idx, item in enumerate(search_result.get("results", []) or [], 1):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        title = str(item.get("title") or url or "Tavily result")
        content = str(item.get("content") or "")
        if not title and not content:
            continue
        docs.append(
            {
                "id": f"tavily:{url or idx}",
                "text": content,
                "score": round(1.0 / idx, 6),
                "rerank_score": None,
                "collection": "web",
                "metadata": {
                    "title": title,
                    "source": url,
                    "url": url,
                    "provider": "tavily",
                    "collection": "web",
                },
            }
        )
    return docs


def _tavily_search_context(
    *,
    query: str,
    tavily_tool: Any | None,
    max_results: int = 3,
    search_depth: str = "basic",
    extract_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Search official HUST domains and return context, sources, timings.

    If ``extract_urls`` is provided those URLs are fetched directly via the
    Tavily Extract API (useful for dynamic pages like
    ``ctt.hust.edu.vn/DisplayWeb/DisplayKehoach?kehoach=...`` that may not
    appear in Tavily's search index).

    When no explicit ``extract_urls`` are given the function runs a normal
    search first.  If search returns empty context it then attempts to extract
    content directly from the top URL(s) returned by the search results.
    """
    fallback_t0 = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    if tavily_tool is None:
        logger.info("No Tavily tool configured, skipping web search")
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return {
            "context": "",
            "timings": timings_ms,
            "sources": [],
            "used": False,
        }

    try:
        from tools.tavily_search import HUST_OFFICIAL_DOMAINS

        tavily_query = query.strip()
        web_context = ""
        tavily_sources: List[Dict[str, Any]] = []

        # ── Path A: caller supplied specific URLs → extract directly ──────
        if extract_urls:
            extract_t0 = time.perf_counter()
            extract_result = tavily_tool.extract(
                urls=extract_urls,
                extract_depth="advanced",
                query=tavily_query or None,
            )
            timings_ms["tavily_extract"] = _elapsed_ms(extract_t0)
            web_context = str(extract_result.get("context") or "")
            tavily_sources = _tavily_results_to_docs(extract_result)
            logger.info(
                "Tavily extract: %d URL(s) → context_len=%d",
                len(extract_urls),
                len(web_context),
            )

        # ── Path B: normal keyword search ─────────────────────────────────
        else:
            search_t0 = time.perf_counter()
            search_result = tavily_tool.search(
                tavily_query,
                max_results=max_results,
                search_depth=search_depth,
                include_domains=HUST_OFFICIAL_DOMAINS,
            )
            timings_ms["tavily_search"] = _elapsed_ms(search_t0)

            raw_results = search_result.get("results") or []
            timings_ms["web_results_raw_count"] = float(len(raw_results))
            content_lengths = [
                len(str(r.get("content", "")))
                for r in raw_results
                if isinstance(r, dict)
            ]
            if content_lengths:
                timings_ms["web_avg_content_length"] = round(
                    sum(content_lengths) / len(content_lengths), 1
                )

            web_context = str(search_result.get("context") or "")
            tavily_sources = _tavily_results_to_docs(search_result)

            # ── Path B2: search found URLs but empty content → extract top URL
            if not web_context and search_result.get("results"):
                top_url = str(search_result["results"][0].get("url", ""))
                if top_url:
                    logger.info(
                        "Tavily search returned empty context, extracting top URL: %s",
                        top_url,
                    )
                    extract_t0 = time.perf_counter()
                    extract_result = tavily_tool.extract(
                        urls=[top_url],
                        extract_depth="advanced",
                        query=tavily_query or None,
                    )
                    timings_ms["tavily_extract"] = _elapsed_ms(extract_t0)
                    web_context = str(extract_result.get("context") or "")
                    if extract_result.get("results"):
                        tavily_sources = _tavily_results_to_docs(extract_result)

        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return {
            "context": web_context,
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": bool(web_context),
        }
    except Exception:
        logger.warning("Tavily search/extract failed", exc_info=True)
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return {
            "context": "",
            "timings": timings_ms,
            "sources": [],
            "used": False,
        }


def _tavily_fallback_result(
    *,
    question: str,
    answer: str,
    tavily_tool: Any | None,
    chat_model: BaseLLM,
    history: List[Dict[str, str]],
    max_results: int = 3,
    search_depth: str = "basic",
    search_query: Optional[str] = None,
) -> Dict[str, Any]:
    """Use Tavily web search and return answer, timings, source docs, status."""
    fallback_t0 = time.perf_counter()
    search_info = _tavily_search_context(
        query=(search_query or question).strip() or question,
        tavily_tool=tavily_tool,
        max_results=max_results,
        search_depth=search_depth,
    )
    timings_ms: Dict[str, float] = dict(search_info["timings"])
    web_context = str(search_info.get("context") or "")
    tavily_sources = list(search_info.get("sources") or [])
    # Early-exit: web context empty or too short → don't waste an LLM call
    if not web_context or len(web_context.strip()) < 200:
        if web_context:
            logger.info(
                "Tavily web context too short (%d chars), skipping re-generation",
                len(web_context),
            )
        return {
            "answer": answer,
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": False,
        }

    try:
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
        return {
            "answer": new_answer,
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": True,
        }
    except Exception:
        logger.warning(
            "Tavily answer regeneration failed, returning original answer",
            exc_info=True,
        )
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return {
            "answer": answer,
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": False,
        }


def _tavily_fallback(
    *,
    question: str,
    answer: str,
    tavily_tool: Any | None,
    chat_model: BaseLLM,
    history: List[Dict[str, str]],
    max_results: int = 3,
    search_depth: str = "basic",
) -> tuple[str, Dict[str, float]]:
    """Backward-compatible wrapper for Tavily fallback."""
    result = _tavily_fallback_result(
        question=question,
        answer=answer,
        tavily_tool=tavily_tool,
        chat_model=chat_model,
        history=history,
        max_results=max_results,
        search_depth=search_depth,
    )
    return str(result["answer"]), result["timings"]
