"""Pipeline Flows — chitchat and RAG flow definitions."""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Set

from embedding.base import BaseEmbedder
from llm.base import BaseLLM
from llm.prompts import build_rag_messages
from llm.self_eval import SelfEvaluator
from query.signals import (
    analyze_query_signals,
    extract_key_phrases,
    fold_vietnamese_text,
)
from reranking.base import BaseReranker
from retrieval.collection_selector import CollectionSelector
from retrieval.metadata_filters import (
    MAJOR_CODE_TO_NAME,
    build_major_comparison_subqueries_for_retrieval,
    build_cohort_comparison_subqueries_for_retrieval,
    has_freshness_intent,
    strip_cohort_comparison_scaffold_for_retrieval,
    strip_major_comparison_scaffold_for_retrieval,
    strip_major_from_query_for_retrieval,
    expand_major_in_query_for_reranking,
)

logger = logging.getLogger(__name__)

_collection_selector = CollectionSelector()

# ── Answer post-processing: strip markdown links ──────────────────────────────
# Safety net: LLMs sometimes generate inline links despite prompt instructions.
# Strip them so the frontend only shows links via FriendlySourceCard components.
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_RAW_URL_RE = re.compile(r"(?<!\()(https?://\S+)")


def _strip_answer_links(answer: str) -> str:
    """Remove markdown links and raw URLs from LLM answer text.

    Preserves the visible label text from markdown links and removes raw URLs
    that would clutter the response. The frontend displays source documents
    with proper link buttons via FriendlySourceCard.
    """
    # [label](url) → label
    result = _MARKDOWN_LINK_RE.sub(r"\1", answer)
    # Remove standalone raw URLs (not already inside parentheses)
    result = _RAW_URL_RE.sub("", result)
    # Clean up leftover artifacts like empty parentheses or double spaces
    result = re.sub(r"\(\s*\)", "", result)
    result = re.sub(r"  +", " ", result)
    return result.strip()


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
_PROFILE_DEPENDENT_QUERY_RE = re.compile(
    r"\b(?:"
    r"(?:nganh|chuong\s*trinh|khoa|nam\s*thu|cpa|gpa|"
    r"ma\s*(?:sv|sinh\s*vien)|mssv|thong\s*tin)"
    r"\s+(?:hoc\s+)?(?:cua\s+)?(?:toi|minh|em)|"
    r"(?:toi|minh|em)\s+(?:hoc|dang\s+hoc|thuoc|la\s+sinh\s+vien)|"
    r"(?:nganh|khoa)\s+(?:toi|minh|em)"
    r")\b",
    re.IGNORECASE,
)

# Detect "list-all" queries: asking to enumerate multiple items.
# Examples: "các học phần tiếng nhật", "tất cả môn bắt buộc", "danh sách học phần"
_LIST_QUERY_RE = re.compile(
    r"\b(?:các|tất\s+cả|danh\s*sách|liệt\s*kê|những|bao\s+gồm\s+những|toàn\s+bộ|hết)\b",
    re.IGNORECASE,
)
_LIST_TOP_K_MULTIPLIER = 2  # double top_k for list queries
_LIST_TOP_K_MAX = 12  # cap to avoid excessive reranking latency

_WEB_FALLBACK_DEFAULT_DYNAMIC_COLLECTIONS = ("kehoach",)
_WEB_FALLBACK_NO_INFO_PATTERNS = (
    # ── Existing (8) ──────────────────────────────────────
    "toi khong tim thay thong tin nay trong tai lieu hien co",
    "khong tim thay thong tin",
    "khong co thong tin",
    "chua co thong tin",
    "khong du co so",
    "khong du thong tin",
    "tai lieu hien co khong",
    "chua tim thay",
    # ── Rephrase variants (11) ────────────────────────────
    "khong the xac nhan",
    "chua duoc cap nhat",
    "khong nam trong tai lieu",
    "ngoai pham vi",
    "khong co du lieu",
    "chua co du lieu",
    "khong the tra loi",
    "chua the xac dinh",
    "tai lieu khong de cap",
    "thong tin con han che",
    "can kiem tra them",
)
_GENERIC_POLICY_EVIDENCE_PHRASES = {
    "diem ren luyen",
    "diem ren",
    "ren luyen",
    "diem cong",
    "tin chi",
    "hoc phi",
    "dieu kien",
    "tot nghiep",
    "hoc bong",
    "quy dinh",
}
_WEB_FALLBACK_DYNAMIC_QUERY_RE = re.compile(
    r"\b(?:"
    r"ke\s*hoach|thong\s*bao|moi\s*nhat|latest|recent|hien\s*tai|"
    r"lich\s*(?:thi|dang\s*ky|hoc)[^\n]{0,40}"
    r"(?:moi\s*nhat|latest|recent|hien\s*tai|20\d{2}|hk|hoc\s*ky|ky\s*he|ki\s*he)|"
    r"han\s*(?:dang\s*ky|nop)|deadline|ky\s*he|ki\s*he|hoc\s*ky\s*he|"
    r"nam\s*hoc\s*\d{4}\s*[-/]\s*\d{4}|20\d{2}[123]"
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
    return without_marks.replace("đ", "d").replace("Đ", "D").casefold()


def _is_date_within_days(date_str: str, days: int) -> bool:
    """Check if date_str (dd/mm/yyyy) is within N days of now."""
    try:
        doc_date = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return (datetime.now() - doc_date).days <= days
    except (ValueError, TypeError, AttributeError):
        return False


# ── B1: Per-collection score cliff ────────────────────────────────────────────
_CLIFF_MIN_GAP_BY_COLLECTION = {
    "kehoach": 0.5,  # Tight clusters → smaller gap is significant
    "ctdt": 2.0,  # Wide spreads → need larger gap
    "quydinh": 1.5,  # Moderate spreads
    "stsv": 1.5,  # Moderate
}
_CLIFF_MIN_GAP_DEFAULT = 1.5
_CLIFF_MIN_KEEP_PER_COLL = 1
_CLIFF_MIN_KEEP_TOTAL = 2


def _apply_score_cliff_per_collection(
    reranked: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Apply cliff detection per-collection, then merge results.

    Documents must be sorted by rerank_score descending before calling.
    """
    if len(reranked) <= _CLIFF_MIN_KEEP_TOTAL:
        return reranked

    # Group by collection
    by_collection: Dict[str, List[Dict[str, Any]]] = {}
    for doc in reranked:
        coll = doc.get("collection", "_unknown")
        by_collection.setdefault(coll, []).append(doc)

    kept: List[Dict[str, Any]] = []
    for coll, docs in by_collection.items():
        min_gap = _CLIFF_MIN_GAP_BY_COLLECTION.get(coll, _CLIFF_MIN_GAP_DEFAULT)
        scores = [_safe_float(d.get("rerank_score", 0)) for d in docs]

        if len(docs) <= _CLIFF_MIN_KEEP_PER_COLL or all(s <= 0 for s in scores):
            kept.extend(docs)
            continue

        # Find cliff within this collection's docs (sorted desc by score)
        best_cut = len(scores)
        max_gap_val = 0.0
        for i in range(_CLIFF_MIN_KEEP_PER_COLL, len(scores)):
            gap = scores[i - 1] - scores[i]
            if gap > max_gap_val and gap > min_gap:
                max_gap_val = gap
                best_cut = i

        if best_cut < len(docs):
            logger.info(
                "Score cliff [%s] at pos %d (gap=%.2f, min_gap=%.1f), "
                "keeping %d/%d docs",
                coll,
                best_cut,
                max_gap_val,
                min_gap,
                best_cut,
                len(docs),
            )
        kept.extend(docs[:best_cut])

    # Re-sort by rerank score (global order)
    kept.sort(key=lambda d: _safe_float(d.get("rerank_score", 0)), reverse=True)

    # Safety: keep at least _CLIFF_MIN_KEEP_TOTAL docs total
    if len(kept) < _CLIFF_MIN_KEEP_TOTAL:
        kept = reranked[:_CLIFF_MIN_KEEP_TOTAL]

    return kept


# ── C4: Routing confidence candidate pool increase ────────────────────────────


def _resolve_candidate_pool(
    cfg: Dict[str, Any],
    top_k: int,
    routing_confidence: float,
) -> int:
    """Increase candidate pool when routing is uncertain."""
    multiplier = max(_cfg_float(cfg, "raw_candidate_multiplier", 4.0), 1.0)
    min_pool = max(_cfg_int(cfg, "raw_candidate_min", 20), 1)
    base_pool = max(int(round(top_k * multiplier)), min_pool)

    if (
        _cfg_bool(cfg, "low_conf_pool_expand_enabled", False)
        and routing_confidence < 0.65
    ):
        expanded = base_pool * 2
        logger.info(
            "Low routing confidence (%.3f) → expanding candidate pool %d → %d",
            routing_confidence,
            base_pool,
            expanded,
        )
        return expanded

    return base_pool


def _reranker_min_top_k(cfg: Dict[str, Any], top_k_value: int) -> Optional[int]:
    """Return the configured reranker lower bound, capped to top_k."""
    configured = _cfg_int(cfg, "reranker_min_top_k", 0)
    if configured <= 0:
        return None
    return min(configured, top_k_value)


def _reranker_kwargs(
    cfg: Dict[str, Any],
    top_k_value: int,
) -> Dict[str, Any]:
    """Build optional reranker kwargs from runtime config."""
    kwargs: Dict[str, Any] = {}
    if cfg.get("reranker_score_threshold") is not None:
        kwargs["score_threshold"] = cfg.get("reranker_score_threshold")
    if cfg.get("reranker_table_score_threshold") is not None:
        kwargs["table_score_threshold"] = cfg.get(
            "reranker_table_score_threshold"
        )
    min_top_k = _reranker_min_top_k(cfg, top_k_value)
    if min_top_k is not None:
        kwargs["min_top_k"] = min_top_k
    return kwargs


# ── C5: Parent context expansion (post-rerank) ───────────────────────────────


def _expand_parent_context_post_rerank(
    reranked: List[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Expand child results with parent chunk context (AFTER rerank).

    Best practice order: Search children → Rerank → Expand parent → Format.
    Parent expansion is a READ operation (fetch by ID), not a search operation.
    """
    if not _cfg_bool(cfg, "parent_context_enabled", True):
        return reranked
    if not reranked:
        return reranked

    # Quick check: any child with parent_id?
    has_parent = any(
        r.get("metadata", {}).get("parent_id")
        and str(r.get("metadata", {}).get("level", "child")).strip().lower()
        == "child"
        for r in reranked
    )
    if not has_parent:
        return reranked

    try:
        from retrieval.parent_context import ParentContextExpander
        from config.settings import Settings

        settings = Settings()
        expander = ParentContextExpander(
            qdrant_host=settings.qdrant_host,
            qdrant_port=settings.qdrant_port,
            max_parent_chars=_cfg_int(cfg, "parent_max_chars", 1500),
        )

        # Group by collection for batch fetch
        collection_groups: Dict[str, List[int]] = {}
        for idx, r in enumerate(reranked):
            coll = r.get("collection", "") or r.get("metadata", {}).get(
                "collection", ""
            )
            if coll:
                collection_groups.setdefault(coll, []).append(idx)

        for coll, indices in collection_groups.items():
            group = [reranked[i] for i in indices]
            expanded = expander.expand_with_parents(group, coll)
            for i, exp in zip(indices, expanded):
                reranked[i] = exp

    except Exception:
        logger.warning(
            "Parent context expansion failed, continuing without parent",
            exc_info=True,
        )

    return reranked


# ── C1: Sibling chunk expansion ──────────────────────────────────────────────


def _expand_with_siblings_pre_rerank(
    candidates: List[Dict[str, Any]],
    searcher: Any,
    *,
    expand_top_n: int = 3,
    window: int = 1,
    max_expansion: int = 6,
) -> List[Dict[str, Any]]:
    """Expand top candidates with sibling chunks BEFORE reranking.

    Only expands the top N candidates by fusion score. Siblings are looked up
    by (source, chunk_index ± window) in the same collection.

    Args:
        candidates: Raw search results (pre-rerank).
        searcher: MultiCollectionSearch instance with get_by_metadata().
        expand_top_n: Only expand top N candidates.
        window: ±N sibling offset (default ±1).
        max_expansion: Max total siblings to add.

    Returns:
        Original candidates + new sibling chunks (deduped by ID).
    """
    sorted_candidates = sorted(
        candidates, key=lambda d: d.get("score", 0.0), reverse=True
    )

    existing_ids = {str(d.get("id", "")) for d in candidates}
    new_siblings: List[Dict[str, Any]] = []
    added = 0

    for doc in sorted_candidates[:expand_top_n]:
        if added >= max_expansion:
            break
        meta = doc.get("metadata", {}) or {}
        source = meta.get("source")
        chunk_idx = meta.get("chunk_index")
        collection = doc.get("collection")

        if source is None or chunk_idx is None or collection is None:
            continue

        # Ensure chunk_index is int
        try:
            chunk_idx = int(chunk_idx)
        except (TypeError, ValueError):
            continue

        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            if added >= max_expansion:
                break
            target_idx = chunk_idx + offset
            if target_idx < 0:
                continue
            total = meta.get("total_chunks")
            if total is not None and target_idx >= int(total):
                continue

            siblings = searcher.get_by_metadata(
                collection=collection,
                filters={
                    "metadata.source": source,
                    "metadata.chunk_index": target_idx,
                },
                limit=1,
            )
            for sib in siblings:
                sib_id = str(sib.get("id", ""))
                if sib_id and sib_id not in existing_ids:
                    sib["_expansion_source"] = str(doc.get("id", ""))
                    sib["score"] = (
                        doc.get("score", 0.0) * 0.5
                    )  # Lower initial score
                    new_siblings.append(sib)
                    existing_ids.add(sib_id)
                    added += 1

    if new_siblings:
        logger.info("Sibling expansion: added %d chunks", len(new_siblings))

    return candidates + new_siblings


def _answer_has_no_info_signal(answer: str) -> bool:
    """Detect local-RAG no-information answers without another LLM call."""
    folded = _fold_vietnamese(answer)
    return any(pattern in folded for pattern in _WEB_FALLBACK_NO_INFO_PATTERNS)


def _should_cache_final_answer(
    *,
    answer: str,
    answer_quality_gate: Dict[str, Any],
    dynamic_web_query: bool = False,
    pre_web_fallback_used: bool = False,
    web_fallback_used: bool = False,
    web_fallback_reasons: Optional[List[str]] = None,
) -> bool:
    """Return True only for stable, fully answered local-RAG responses."""
    reasons = web_fallback_reasons or []
    if dynamic_web_query:
        return False
    if pre_web_fallback_used or web_fallback_used or reasons:
        return False
    if _answer_has_no_info_signal(answer):
        return False
    if answer_quality_gate.get("answer_status") != "answered":
        return False
    if answer_quality_gate.get("should_web_search"):
        return False
    if answer_quality_gate.get("no_info") or answer_quality_gate.get(
        "no_sources"
    ):
        return False
    if answer_quality_gate.get("self_eval_failed"):
        return False
    return True


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


def _has_textual_freshness_or_dynamic_intent(
    question: str, search_query: str
) -> bool:
    """Return True when the current text asks for fresh/dynamic information."""
    combined = f"{question}\n{search_query}"
    if has_freshness_intent(combined):
        return True
    return bool(
        _WEB_FALLBACK_DYNAMIC_QUERY_RE.search(_fold_vietnamese(combined))
    )


def _routing_top_domain(
    routing_result: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Return the highest-probability domain, falling back to primary domain."""
    if not routing_result:
        return None
    probabilities = routing_result.get("probabilities") or {}
    scored: List[tuple[str, float]] = []
    if isinstance(probabilities, dict):
        for domain, value in probabilities.items():
            try:
                scored.append((str(domain).strip().lower(), float(value)))
            except (TypeError, ValueError):
                continue
    if scored:
        return max(scored, key=lambda item: item[1])[0]
    domain = routing_result.get("domain")
    return str(domain).strip().lower() if domain else None


def _routing_probability_scores(
    routing_result: Optional[Dict[str, Any]],
) -> Dict[str, float]:
    if not routing_result:
        return {}
    probabilities = routing_result.get("probabilities") or {}
    if not isinstance(probabilities, dict):
        return {}
    scores: Dict[str, float] = {}
    for domain, value in probabilities.items():
        key = str(domain).strip().lower()
        if not key:
            continue
        try:
            scores[key] = float(value)
        except (TypeError, ValueError):
            continue
    return scores


def _has_non_kehoach_policy_lock_signal(combined_query: str) -> bool:
    folded = _fold_vietnamese(combined_query)
    return bool(
        re.search(
            r"\b("
            r"chuong trinh thu hai|de tai luan van|hoc ky chinh|"
            r"quy che|quy dinh|dieu kien|ctdt"
            r")\b",
            folded,
        )
    )


def _should_lock_kehoach_route(
    *,
    question: str,
    search_query: str,
    routing_result: Optional[Dict[str, Any]],
) -> bool:
    """Keep clear schedule/freshness kehoach queries on kehoach only."""
    if not routing_result:
        return False

    signals = analyze_query_signals(f"{question}\n{search_query}")
    has_kehoach_intent = bool(
        signals.freshness
        or signals.schedule_intent
        or signals.deadline_intent
        or signals.announcement_intent
    )
    if not has_kehoach_intent:
        return False
    if (
        not signals.freshness
        and not signals.deadline_intent
        and not signals.announcement_intent
        and _has_non_kehoach_policy_lock_signal(f"{question}\n{search_query}")
    ):
        return False

    domain = str(routing_result.get("domain") or "").strip().lower()
    domains = [
        str(item).strip().lower()
        for item in (routing_result.get("domains") or [])
        if str(item).strip()
    ]
    selected_domains = domains or ([domain] if domain else [])
    only_kehoach = bool(selected_domains) and set(selected_domains) == {
        "kehoach"
    }
    if only_kehoach:
        return True

    scores = _routing_probability_scores(routing_result)
    if not scores:
        return False

    top_domain = _routing_top_domain(routing_result)
    if top_domain != "kehoach":
        return False

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    kehoach_score = scores.get("kehoach", 0.0)
    runner_up = ordered[1][1] if len(ordered) > 1 else 0.0
    return kehoach_score - runner_up >= 0.20 or kehoach_score >= 0.65


def _should_bypass_query_cache(
    *,
    question: str,
    search_query: str,
    target_collections: Optional[List[str]],
    routing_result: Optional[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> bool:
    """Avoid early cache hits for dynamic data that may need live refresh."""
    freshness_query = has_freshness_intent(f"{question}\n{search_query}")
    return freshness_query or _is_dynamic_web_query(
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
    web_query = query if has_hust_context else f"HUST {query}"

    extras: List[str] = []
    if re.search(r"\b(?:ky|ki|hoc\s*ky)\s*he\b", folded):
        year_match = re.search(r"\b(20\d{2})\b", folded)
        if year_match:
            end_year = int(year_match.group(1))
            start_year = end_year - 1
            extras.extend([f"{start_year}3", f"{start_year}-{end_year}"])

    has_freshness = any(
        token in folded
        for token in ("moi nhat", "latest", "recent", "hien tai")
    )

    # ── Academic year injection ──────────────────────────────
    if has_freshness:
        if not re.search(r"\b20\d{2}\b", folded):
            now = datetime.now()
            current_year = now.year
            # HUST academic year: Aug → Jul
            if now.month >= 8:
                ay_start, ay_end = current_year, current_year + 1
            else:
                ay_start, ay_end = current_year - 1, current_year

            # Transition period: "năm học mới/tới" in July+ → next AY
            wants_next_year = any(
                kw in folded
                for kw in (
                    "nam hoc moi",
                    "nam hoc toi",
                    "ky toi",
                    "ki toi",
                    "hoc ky toi",
                )
            )
            if wants_next_year and now.month >= 7:
                ay_start, ay_end = current_year, current_year + 1

            extras.append(f"năm học {ay_start}-{ay_end}")
        extras.append("CTT ĐHBKHN")

    # For registration-specific freshness queries, add key HUST academic-planning
    # terms so Tavily finds the official registration notice rather than generic pages.
    has_registration = any(
        token in folded
        for token in (
            "dang ki",
            "dang ky",
            "ke hoach hoc",
            "lich dang",
            "lich trinh",
        )
    )
    if has_registration and has_freshness:
        if (
            "dang ky ke hoach" not in folded
            and "ke hoach hoc tap" not in folded
        ):
            extras.append("đăng ký kế hoạch học tập")

    # ── Content-type signal ──────────────────────────────────
    if any(kw in folded for kw in ("lich", "ke hoach", "thong bao", "dang ky")):
        if "thong bao" not in folded and "ke hoach" not in folded:
            extras.append("thông báo kế hoạch")

    for extra in extras:
        if extra and extra.lower() not in web_query.lower():
            web_query = f"{web_query} {extra}"

    return web_query


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
    freshness_query = has_freshness_intent(f"{question}\n{search_query}")
    no_sources = len(reranked) == 0
    # If local retrieval already has high-confidence results, suppress the
    # dynamic_query Tavily trigger to avoid generic web results overriding
    # precise local curriculum/policy documents.
    best_local_score = _best_explicit_rerank_score(reranked)
    high_local_confidence = (
        best_local_score is not None
        and best_local_score
        >= _cfg_float(cfg, "web_bypass_min_local_score", 0.5)
    )
    reasons: List[str] = []
    if no_sources:
        reasons.append("no_sources")
    # freshness_query no longer unconditionally triggers Tavily: suppress when
    # local kehoach evidence already exists with acceptable quality.  The
    # freshness pre-filter (sort_by_date_desc) already fetched latest-dated IDs
    # from ES, so those results are fresh by construction.  Tavily remains the
    # fallback for: no sources, low/no reranker confidence, or explicit dynamic
    # queries without local evidence.
    local_kehoach_docs = [
        d
        for d in reranked
        if isinstance(d, dict) and d.get("collection") == "kehoach"
    ]
    freshness_acceptable_local = bool(local_kehoach_docs) and (
        high_local_confidence or best_local_score is None
    )

    # ── C3: Freshness date_str validation ──────────────────────────
    # If kehoach docs exist but none have date_str, we can't verify freshness
    # → conservative: allow Tavily (don't suppress)
    if (
        freshness_acceptable_local
        and freshness_query
        and _cfg_bool(cfg, "freshness_tavily_check_enabled", False)
    ):
        dates = [
            d.get("metadata", {}).get("date_str")
            for d in local_kehoach_docs
            if d.get("metadata", {}).get("date_str")
        ]
        if not dates:
            freshness_acceptable_local = False
            logger.info(
                "Freshness override: %d kehoach docs but none have date_str, "
                "allowing Tavily (conservative)",
                len(local_kehoach_docs),
            )
        else:
            has_recent = any(_is_date_within_days(ds, days=90) for ds in dates)
            if not has_recent:
                freshness_acceptable_local = False
                logger.info(
                    "Freshness override: kehoach dates %s all >90 days, "
                    "allowing Tavily",
                    dates,
                )

    if freshness_query and not freshness_acceptable_local:
        reasons.append("freshness_query")
    if (
        dynamic_query
        and not high_local_confidence
        and _cfg_bool(cfg, "web_fallback_on_dynamic", True)
    ):
        reasons.append("dynamic_query")
    if low_retrieval_confidence:
        reasons.append("low_retrieval_confidence")

    answer_status = "answered"
    if no_sources:
        answer_status = "insufficient"
    elif freshness_query or dynamic_query:
        answer_status = "stale_risk"

    return {
        "answer_status": answer_status,
        "should_web_search": bool(reasons),
        "web_search_query": _build_web_search_query(question, search_query),
        "reasons": reasons,
        "dynamic_query": dynamic_query,
        "freshness_query": freshness_query,
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
    no_info = _cfg_bool(
        cfg, "web_fallback_on_no_info", True
    ) and _answer_has_no_info_signal(answer)
    no_sources = len(reranked) == 0
    dynamic_query = _is_dynamic_web_query(
        question=question,
        search_query=search_query,
        target_collections=target_collections,
        routing_result=routing_result,
        cfg=cfg,
    )
    freshness_query = has_freshness_intent(f"{question}\n{search_query}")
    eval_failed = bool(
        eval_result is not None and not eval_result.get("pass", True)
    )
    eval_wants_web = bool(eval_result and eval_result.get("should_web_search"))
    eval_status = (
        str(eval_result.get("answer_status") or "") if eval_result else ""
    )
    eval_web_request = eval_wants_web and eval_status in {
        "insufficient",
        "stale_risk",
    }
    local_exact_policy_evidence = _has_local_exact_policy_evidence(
        question=question,
        search_query=search_query,
        reranked=reranked,
        cfg=cfg,
    )
    suppress_eval_web_request = bool(
        eval_web_request
        and local_exact_policy_evidence
        and not no_info
        and not no_sources
        and not dynamic_query
        and not freshness_query
    )

    # Post-generation Tavily only runs for explicit insufficiency signals.
    # Dynamic queries are handled by the pre-generation web decision path.
    reasons: List[str] = []
    if no_info:
        reasons.append("answer_no_info")
    if no_sources:
        reasons.append("no_sources")
    if eval_web_request and not suppress_eval_web_request:
        reasons.append("self_eval_requested_web")

    # Tracked for answer_status / debugging. A structured self-eval web request
    # only triggers fallback when paired with an insufficient/stale status above.
    informational_notes: List[str] = []
    if eval_failed:
        informational_notes.append("self_eval_failed")
    if eval_wants_web:
        informational_notes.append("self_eval_requested_web")
    if suppress_eval_web_request:
        informational_notes.append(
            "self_eval_web_suppressed_local_exact_policy"
        )
    if dynamic_query:
        informational_notes.append("dynamic_query")
    if freshness_query:
        informational_notes.append("freshness_query")
    if pre_web_fallback_used:
        informational_notes.append("pre_generation_web_used")

    answer_status = "answered"
    if no_info or no_sources:
        answer_status = "insufficient"
    elif freshness_query or dynamic_query:
        answer_status = "stale_risk"
    elif eval_result and not suppress_eval_web_request:
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
        "freshness_query": freshness_query,
        "self_eval_failed": eval_failed,
        "local_exact_policy_evidence": local_exact_policy_evidence,
    }


def _has_local_exact_policy_evidence(
    *,
    question: str,
    search_query: str,
    reranked: List[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> bool:
    """Return True when local retrieved docs directly support exact policy answers.

    This prevents a conservative self-eval miss from replacing strong local
    table evidence with weaker web search snippets for questions like
    "hiến máu được mấy điểm rèn luyện".
    """
    if not reranked:
        return False

    combined_query = f"{question}\n{search_query}"
    signals = analyze_query_signals(combined_query)
    if not (signals.exact_policy_lookup or signals.table_lookup):
        return False

    phrases = _dedup_text_values(
        [
            *extract_key_phrases(question),
            *extract_key_phrases(search_query),
        ]
    )
    specific_phrases = [
        phrase
        for phrase in phrases
        if fold_vietnamese_text(phrase) not in _GENERIC_POLICY_EVIDENCE_PHRASES
    ]
    evidence_phrases = specific_phrases or phrases
    if not evidence_phrases:
        return False

    min_score = _cfg_float(cfg, "web_bypass_min_local_score", 0.5)
    for doc in reranked[:3]:
        if not isinstance(doc, dict):
            continue
        metadata = doc.get("metadata") or {}
        text = str(doc.get("text") or "")
        score_value = doc.get("rerank_score", doc.get("score", 0.0))
        try:
            score = float(score_value or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if score < min_score:
            continue

        has_table_or_keyword_hit = bool(
            metadata.get("_keyword_table_lookup_hit")
            or metadata.get("has_table")
            or "|" in text
        )
        if not has_table_or_keyword_hit:
            continue

        haystack = " ".join(
            [
                text,
                str(metadata.get("title") or ""),
                str(metadata.get("doc_title") or ""),
                str(metadata.get("hierarchy_path") or ""),
                str(metadata.get("section_h2") or ""),
                str(metadata.get("section_h3") or ""),
            ]
        )
        folded_haystack = fold_vietnamese_text(haystack)
        if any(
            fold_vietnamese_text(phrase) in folded_haystack
            for phrase in evidence_phrases
        ):
            return True

    return False


def _dedup_text_values(values: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values:
        key = fold_vietnamese_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _merge_local_and_web_context(local_context: str, web_context: str) -> str:
    """Combine local RAG context with supplemental live web context deterministically."""
    if not web_context:
        return local_context
    if not local_context:
        return (
            f"## web_live_context (Tavily / nguồn web chính thức)\n"
            f"{web_context}"
        )
    return (
        f"## Nguồn Cơ Sở Dữ Liệu Nội Bộ (ưu tiên date_str khi có)\n"
        f"{local_context}\n\n---\n\n"
        f"## web_live_context (Tavily / nguồn web chính thức)\n"
        f"{web_context}\n\n"
        f"Lưu ý: Ưu tiên Nguồn Cơ Sở Dữ Liệu Nội Bộ cho các câu hỏi về quy chế, "
        f"chương trình đào tạo và điều kiện tốt nghiệp — đây là nguồn chính xác "
        f"và cụ thể nhất. Chỉ dùng web_live_context khi nguồn nội bộ không có "
        f"thông tin hoặc cần xác nhận dữ liệu thời gian thực (lịch thi, thông báo mới)."
    )


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
        if prev is None or _safe_float(item.get("score")) > _safe_float(
            prev.get("score")
        ):
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
            row = merged_counts.setdefault(
                collection, {"vector": 0, "keyword": 0}
            )
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


def _order_with_siblings(
    reranked: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Order docs: originals in rerank order first, then siblings grouped by parent.

    This prevents the lost-in-the-middle effect where siblings at intermediate
    positions compete with more relevant docs for LLM attention.
    """
    originals = []
    sibling_map: Dict[str, List[Dict[str, Any]]] = {}

    for doc in reranked:
        expansion_source = doc.get("_expansion_source")
        if expansion_source:
            sibling_map.setdefault(expansion_source, []).append(doc)
        else:
            originals.append(doc)

    # Siblings: grouped by parent, sorted by chunk_index within group
    sibling_section: List[Dict[str, Any]] = []
    for doc in originals:
        doc_id = str(doc.get("id", ""))
        siblings = sibling_map.pop(doc_id, [])
        siblings.sort(key=lambda s: s.get("metadata", {}).get("chunk_index", 0))
        sibling_section.extend(siblings)

    # Orphan siblings (parent cut by cliff)
    for orphans in sibling_map.values():
        sibling_section.extend(orphans)

    return originals + sibling_section


def _format_context(
    documents: List[Dict[str, Any]],
    *,
    per_doc_char_limit: int = _DEFAULT_CONTEXT_DOC_CHAR_LIMIT,
    total_char_budget: int = _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET,
    sibling_per_doc_limit: int = 800,
    trace_out: Optional[Dict[str, Any]] = None,
) -> str:
    """Convert retrieved documents into a token-budgeted context string.

    Limits per-document and total context size to prevent context-length
    errors and keep LLM latency predictable regardless of chunk sizes.

    When sibling expansion is active, siblings (docs with _expansion_source)
    get a separate, lower per-doc limit to preserve budget for primary docs.
    """
    parts: List[str] = []
    used = 0
    docs_used = 0
    seen_parent_ids: Set[str] = (
        set()
    )  # C5: dedup parent context across children sharing same parent
    for i, doc in enumerate(documents, 1):
        meta = doc.get("metadata", {}) or {}
        title = (
            meta.get("title") or meta.get("source") or "Tài liệu không rõ nguồn"
        )

        # Inject metadata into document header so the LLM is aware of the program/major context
        meta_parts = []
        if meta.get("major_code"):
            meta_parts.append(f"Mã ngành: {meta['major_code']}")
        if meta.get("major_name"):
            meta_parts.append(f"Ngành: {meta['major_name']}")
        if meta.get("applicable_cohort"):
            meta_parts.append(f"Khóa: {meta['applicable_cohort']}")
        # Posting date is kehoach-specific (freshness signal for notifications).
        if doc.get("collection") == "kehoach" and meta.get("date_str"):
            meta_parts.append(f"Ngày đăng: {meta['date_str']}")
        # NOTE: URLs are no longer injected into context. The frontend displays
        # source links via dedicated FriendlySourceCard components, providing
        # better UX than inline markdown links in the answer text.
        meta_str = f" [{', '.join(meta_parts)}]" if meta_parts else ""

        text = str(doc.get("text", "") or "").strip()

        # C5: Prepend parent context for broader section context.
        # Dedup: only render parent text once even when multiple children share the same parent.
        parent_ctx = str((meta.get("parent_context") or "")).strip()
        parent_title = str(
            (meta.get("parent_title") or meta.get("parent_section_h2") or "")
        ).strip()
        parent_id = str(meta.get("parent_id") or "").strip()
        if parent_ctx and parent_id and parent_id in seen_parent_ids:
            parent_ctx = ""  # already rendered for a previous sibling
        if parent_ctx:
            if parent_id:
                seen_parent_ids.add(parent_id)
            parent_header = (
                f"[Ngữ cảnh section: {parent_title}]"
                if parent_title
                else "[Ngữ cảnh section]"
            )
            text = f"{parent_header}\n{parent_ctx}\n\n[Chi tiết]\n{text}"

        # Siblings get reduced per-doc limit (C2: 70/30 budget split)
        effective_limit = (
            sibling_per_doc_limit
            if doc.get("_expansion_source")
            else per_doc_char_limit
        )
        # When parent context is prepended, allow more chars per doc
        if parent_ctx:
            effective_limit = min(
                effective_limit + 1500, per_doc_char_limit + 1500
            )
        if len(text) > effective_limit:
            text = text[:effective_limit] + "\u2026"  # ellipsis
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


# ─── Kehoach source-link footer ─────────────────────────────────────────────
# kehoach (notification) docs always carry a real URL in metadata, but the LLM
# does not reliably embed it. When the answer actually references such a doc, we
# deterministically append a verifiable link footer so the user can open the
# original notice.

_KEHOACH_LINK_HEADER = "**Nguồn thông báo:**"
# A title counts as "mentioned" when the answer shares at least this fraction of
# the title's adjacent word-pairs (bigrams). Bigrams are far more discriminative
# than single words, which the kehoach titles share heavily ("học kỳ", "năm học").
_TITLE_MENTION_MIN_BIGRAM_OVERLAP = 0.5
# Vietnamese titles use space-separated syllables; need enough to form bigrams.
_TITLE_MENTION_MIN_TOKENS = 4
_MATCH_NORMALIZE_RE = re.compile(r"[^0-9a-zà-ỹ]+")


def _normalize_for_match(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace for fuzzy matching."""
    lowered = unicodedata.normalize("NFC", text).lower()
    return _MATCH_NORMALIZE_RE.sub(" ", lowered).strip()


def _bigrams(tokens: List[str]) -> Set[str]:
    return {f"{a} {b}" for a, b in zip(tokens, tokens[1:])}


def _title_mentioned(
    answer_norm: str, answer_bigrams: Set[str], title: str
) -> bool:
    """True when ``title`` is referenced in the (normalized) answer text."""
    title_norm = _normalize_for_match(title)
    if not title_norm:
        return False
    if title_norm in answer_norm:
        return True
    title_tokens = title_norm.split()
    if len(title_tokens) < _TITLE_MENTION_MIN_TOKENS:
        return False  # too short to bigram-match; substring already failed
    title_bigrams = _bigrams(title_tokens)
    if not title_bigrams:
        return False
    overlap = len(title_bigrams & answer_bigrams) / len(title_bigrams)
    return overlap >= _TITLE_MENTION_MIN_BIGRAM_OVERLAP


def _kehoach_links_footer(answer: str, sources: List[Dict[str, Any]]) -> str:
    """Return a Markdown link footer for kehoach docs the answer references.

    Idempotent: a doc whose URL already appears in ``answer`` is skipped, so the
    footer is never duplicated (e.g. when the LLM already embedded the link, or
    on a cache hit where the answer was stored with the footer).
    
    Uses generic link text to hide full URLs and improve UX.
    """
    if not answer or not sources:
        return ""
    answer_norm = _normalize_for_match(answer)
    answer_bigrams = _bigrams(answer_norm.split())
    seen_urls: Set[str] = set()
    links: List[tuple[str, str]] = []
    for doc in sources:
        meta = doc.get("metadata") or {}
        collection = (
            doc.get("collection")
            or meta.get("collection")
            or meta.get("source")
        )
        if collection != "kehoach":
            continue
        url = str(meta.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        if url in answer or url in seen_urls:
            continue
        title = str(meta.get("title") or "").strip()
        if not title or not _title_mentioned(
            answer_norm, answer_bigrams, title
        ):
            continue
        seen_urls.add(url)
        links.append((title, url))
    if not links:
        return ""
    # Format links as simple items that can be rendered as cards on frontend
    formatted_links = [f"- [{title}]({url})" for title, url in links]
    return f"\n\n{_KEHOACH_LINK_HEADER}\n" + "\n".join(formatted_links)


def _append_kehoach_source_links(
    answer: str, sources: List[Dict[str, Any]]
) -> str:
    """Append the kehoach link footer to ``answer`` (no-op when none apply)."""
    return answer + _kehoach_links_footer(answer, sources)


def _cfg_int(cfg: Dict[str, Any], key: str, default: int) -> int:
    """Read an integer config value with a safe fallback."""
    try:
        return int(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _cfg_float(cfg: Dict[str, Any], key: str, default: float) -> float:
    """Read a float config value with a safe fallback."""
    try:
        return float(cfg.get(key, default))
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

    # C2: Expand budget when sibling expansion is active
    if _cfg_bool(cfg, "sibling_expansion_enabled", False):
        expanded_budget = _cfg_int(
            cfg, "context_total_char_budget_with_expansion", 16000
        )
        total_budget = max(total_budget, expanded_budget)

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


def _update_rerank_trace_after_fallback(
    rerank_trace: Dict[str, Any],
    *,
    candidate_count: int,
    reranked: List[Dict[str, Any]],
    fallback_reason: str,
    raw_fallback: bool,
) -> Dict[str, Any]:
    """Update rerank trace so it describes the final fallback result."""
    updated = dict(rerank_trace)
    for key in ("rerank_score_min", "rerank_score_max", "rerank_score_mean"):
        updated.pop(key, None)

    scores = [
        float(doc["rerank_score"])
        for doc in reranked
        if isinstance(doc, dict) and doc.get("rerank_score") is not None
    ]
    updated.update(
        {
            "rerank_candidate_count": candidate_count,
            "rerank_returned_count": len(reranked),
            "rerank_dropped_count": max(0, candidate_count - len(reranked)),
            "rerank_fallback": True,
            "fallback_reason": fallback_reason,
        }
    )
    if raw_fallback:
        updated["rerank_raw_fallback"] = True
    if scores:
        updated.update(
            {
                "rerank_score_min": round(min(scores), 6),
                "rerank_score_max": round(max(scores), 6),
                "rerank_score_mean": round(sum(scores) / len(scores), 6),
            }
        )
    return updated


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


# ── HyDE post-rerank fallback ─────────────────────────────────────────────────


def _should_trigger_hyde(
    reranked: List[Dict[str, Any]],
    reranker: Optional[Any],
    cfg: Dict[str, Any],
) -> bool:
    """Decide whether HyDE second-pass retrieval should run.

    Triggers when ``hyde_enabled`` is True AND retrieval recall looks poor:
      1. No documents survived reranking, OR
      2. The best explicit rerank score is negative (all docs irrelevant), OR
      3. Fewer than ``hyde_min_results`` documents survived (sparse recall).

    The ``hyde_confidence_threshold`` (mean-score) path of ``should_use_hyde``
    is intentionally NOT used here: cross-encoder rerank scores are unnormalised
    logits, so a fixed 0.3 mean threshold would fire on almost every query. It
    stays a reserved rollout flag.
    """
    if not _cfg_bool(cfg, "hyde_enabled", False):
        return False

    best = _best_explicit_rerank_score(reranked)
    if not reranked or (best is not None and best < 0.0):
        logger.info(
            "HyDE trigger: best rerank score=%.4f (negative or empty)",
            best if best is not None else -999.0,
        )
        return True

    min_results = _cfg_int(cfg, "hyde_min_results", 3)
    if len(reranked) < min_results:
        logger.info(
            "HyDE trigger: only %d result(s) < hyde_min_results=%d",
            len(reranked),
            min_results,
        )
        return True

    return False


def _hyde_fallback_post_rerank(
    *,
    reranked: List[Dict[str, Any]],
    raw_candidate_k: int,
    retrieval_query: str,
    rerank_query: str,
    top_k_value: int,
    bge_embedder: Any,
    e5_embedder: Any,
    searcher: Any,
    reranker: Optional[Any],
    chat_model: Any,
    target_collections: Optional[List[str]],
    resolved_major: Optional[str],
    resolved_cohort: Optional[str],
    cfg: Dict[str, Any],
    timings_ms: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Run HyDE second-pass retrieval and merge with existing results.

    1. Generate a hypothetical answer via LLM.
    2. Embed the hypothesis with BGE-M3 (E5 uses original query).
    3. Search with the HyDE vector.
    4. Merge + dedup with existing reranked pool.
    5. Re-rerank the merged pool.

    Returns the updated reranked list (or original if HyDE adds nothing).
    """
    from retrieval.hyde import HyDEExpander

    hyde_t0 = time.perf_counter()
    try:
        hyde = HyDEExpander(llm=chat_model, embedder=bge_embedder)
        hyde_vec = hyde.generate_embedding(retrieval_query)
        e5_vec = e5_embedder.embed_query(retrieval_query)

        search_kwargs: Dict[str, Any] = {
            "query": retrieval_query,
            "bge_m3_query": hyde_vec,
            "e5_query": e5_vec,
            "top_k": raw_candidate_k,
            "vector_top_k": cfg.get("vector_top_k", 20),
            "keyword_top_k": cfg.get("keyword_top_k", 20),
            "vector_pool_k": cfg.get("vector_pool_k", 15),
            "keyword_pool_k": cfg.get("keyword_pool_k", 15),
            "active_collections": target_collections,
        }
        if resolved_major:
            search_kwargs["resolved_major"] = resolved_major
        if resolved_cohort:
            search_kwargs["resolved_cohort"] = resolved_cohort

        hyde_results = searcher.search(**search_kwargs)

        if not hyde_results:
            logger.info("HyDE fallback: no new candidates found")
            timings_ms["hyde"] = _elapsed_ms(hyde_t0)
            timings_ms["hyde_triggered"] = 1.0
            timings_ms["hyde_new_candidates"] = 0.0
            return reranked

        # Merge + dedup with existing reranked pool
        merged = _dedup_retrieval_candidates(
            reranked + hyde_results,
            top_k=raw_candidate_k,
        )
        new_count = len(merged) - len(reranked)
        logger.info(
            "HyDE fallback: merged %d new candidates (total pool=%d)",
            max(new_count, 0),
            len(merged),
        )

        # Re-rerank the merged pool
        if reranker is not None:
            reranked = reranker.rerank(
                query=rerank_query,
                documents=merged,
                top_k=top_k_value,
                **_reranker_kwargs(cfg, top_k_value),
            )
        else:
            reranked = sorted(
                merged, key=lambda d: d.get("score", 0.0), reverse=True
            )[:top_k_value]

        timings_ms["hyde"] = _elapsed_ms(hyde_t0)
        timings_ms["hyde_triggered"] = 1.0
        timings_ms["hyde_new_candidates"] = float(max(new_count, 0))
        return reranked

    except Exception:
        logger.warning(
            "HyDE fallback failed, continuing with original results",
            exc_info=True,
        )
        timings_ms["hyde"] = _elapsed_ms(hyde_t0)
        timings_ms["hyde_failed"] = 1.0
        return reranked


def _is_web_document(document: Dict[str, Any]) -> bool:
    metadata = document.get("metadata") or {}
    return (
        str(document.get("collection") or "").lower() == "web"
        or str(metadata.get("collection") or "").lower() == "web"
        or str(metadata.get("provider") or "").lower() == "tavily"
    )


def _best_local_evidence_score(
    documents: List[Dict[str, Any]],
) -> Optional[float]:
    scores: List[float] = []
    for doc in documents:
        if not isinstance(doc, dict) or _is_web_document(doc):
            continue
        score_value = doc.get("rerank_score")
        if score_value is None:
            score_value = doc.get("score")
        if score_value is None:
            continue
        scores.append(_safe_float(score_value))
    return max(scores) if scores else None


def _has_strong_local_evidence(
    documents: List[Dict[str, Any]],
    context: str,
    cfg: Dict[str, Any],
) -> bool:
    """Return True when local retrieved evidence is strong enough to retry locally."""
    if not context.strip():
        return False
    best_score = _best_local_evidence_score(documents)
    if best_score is None:
        return False
    return best_score >= _cfg_float(cfg, "web_bypass_min_local_score", 0.5)


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
        m.get("content", "")
        for m in history
        if m.get("role") == "user" and m.get("content")
    ]

    for text in user_messages:
        t = text.lower()
        if not profile.get("nganh"):
            m = re.search(
                r"(?:h\u1ecdc ng\u00e0nh|ng\u00e0nh|chuy\u00ean ng\u00e0nh)\s+([^\.,\n]{2,30})",
                t,
            )
            if m:
                profile["nganh"] = m.group(1).strip()
        if not profile.get("nam"):
            m = re.search(
                r"sinh vi\u00ean n\u0103m\s*(\d)|n\u0103m\s*(\d)\b|n\u0103m th\u1ee9\s*(\d)",
                t,
            )
            if m:
                profile["nam"] = next(g for g in m.groups() if g)
        if not profile.get("khoa"):
            m = re.search(r"\bk(\d{2,3})\b|kh\u00f3a\s*(\d{2,3})", t)
            if m:
                profile["khoa"] = next(g for g in m.groups() if g)
        if not profile.get("gpa"):
            m = re.search(
                r"\b(?:cpa|gpa)\s*(?:l\u00e0|=|:)?\s*(\d+[\.,]\d+)\b", t
            )
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


def _build_cache_profile(user_context: Optional[Dict[str, Any]]) -> str:
    """Normalized ``major|cohort`` scope for answer-cache keys.

    Without this scope the query-only cache (no doc_ids) would serve a personal
    answer generated for one student ("điều kiện tốt nghiệp của tôi") verbatim to
    any other student asking the same words — a cross-student data leak. An empty
    string (anonymous / no profile) keeps the legacy key space.
    """
    if not user_context:
        return ""
    major = (
        (user_context.get("major_code") or user_context.get("major") or "")
        .strip()
        .lower()
    )
    cohort = (user_context.get("cohort") or "").strip().lower()
    return f"{major}|{cohort}" if (major or cohort) else ""


def _should_prepend_profile_note(question: str) -> bool:
    """Return True only when the question explicitly depends on user profile."""
    if _EXPLICIT_MAJOR_CODE_RE.search(question or "") is not None:
        return False
    return bool(
        _PROFILE_DEPENDENT_QUERY_RE.search(_fold_vietnamese(question or ""))
    )


def _build_resolved_profile_note(
    resolved_major: Optional[str],
    resolved_cohort: Optional[str],
    user_context: Optional[Dict[str, Any]],
) -> str:
    """Build the generation profile note from facts resolved during reflection.

    Prefers the authenticated ``user_context`` (precise display name + code). When
    that is absent (anonymous request) it falls back to the major/cohort that
    reflection already resolved, so the LLM still learns the program it must
    answer for. This is what stops the model from re-asking "which program?" after
    reflection has already injected the major into the retrieval query.
    """
    note = _build_profile_note_from_user_context(user_context)
    if note:
        return note

    parts: List[str] = []
    if resolved_major:
        major_text = MAJOR_CODE_TO_NAME.get(resolved_major, resolved_major)
        if major_text and major_text != resolved_major:
            major_text = f"{major_text} [{resolved_major}]"
        parts.append(f"Ngành: {major_text}")
    if resolved_cohort:
        parts.append(f"Khoá: {resolved_cohort}")
    if not parts:
        return ""
    return "Thông tin sinh viên: " + " | ".join(parts) + "."


def _profile_note_for_generation(
    question: str,
    search_query: Optional[str],
    routing_result: Optional[Dict[str, Any]],
    resolved_major: Optional[str],
    resolved_cohort: Optional[str],
    resolved_user_major: Optional[str],
    resolved_target_major: Optional[str],
    user_context: Optional[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]],
) -> str:
    """Decide and build the profile note prepended to the generation context.

    Topic-driven via ``query.profile_dependency``: inject the user's program/cohort
    only when the answer depends on a profile attribute that resolves to the
    authenticated profile (not a target named in the query). A legacy phrasing
    check is kept as a floor so self-referential identity questions
    ("ngành của tôi là gì") still surface the profile.

    This is the consistency fix (BUG-1 / BUG-4): retrieval major-filtering and the
    generation note now share one gate, so a major reflection already resolved is
    never silently dropped — the model stops re-asking the program.
    """
    from query.profile_dependency import (
        should_inject_profile_note,
    )  # noqa: PLC0415

    user_major = resolved_user_major or (
        (user_context or {}).get("major_code")
        or (user_context or {}).get("major")
    )
    inject = should_inject_profile_note(
        question,
        search_query,
        routing_result,
        user_major=user_major,
        target_major=resolved_target_major,
        cohort=resolved_cohort,
    ) or _should_prepend_profile_note(question)
    if not inject:
        return ""
    return _build_resolved_profile_note(
        resolved_major, resolved_cohort, user_context
    ) or _extract_session_profile(history)


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
    reroute_reflected: Optional[Any] = None,
    pre_ref_result: Optional[Dict[str, Any]] = None,
    pre_reflection_ms: Optional[float] = None,
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
    # Profile scope (major|cohort) so a personal answer is never served to a
    # student with a different profile — see _build_cache_profile.
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
                    "answer": _strip_answer_links(_qcached["answer"]),
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

    # 1. Reflection — rewrite query + extract entities
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
    # program (e.g. học bổng) so universal answers are not narrowed to one major.
    # When major IS required, retrieval_major == resolved_major. See
    # query.profile_dependency. Decided once here, reused for every sub-query.
    from query.profile_dependency import (
        effective_major_for_retrieval,
    )  # noqa: PLC0415

    retrieval_major = effective_major_for_retrieval(
        question, search_query, routing_result, resolved_major
    )

    # 2. Collection-aware routing (Phase 8 — Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    routing_probabilities: Optional[Dict[str, Any]] = None
    if cfg.get("find_all", False):
        routing_t0 = time.perf_counter()
        target_collections = list(cfg.get("collections") or [])
        routing_probabilities = (
            routing_result.get("probabilities") if routing_result else None
        )
        logger.info(
            "find_all=true → bypassing routing, searching all collections: %s",
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

    # 4.5 Sibling chunk expansion (C1) — BEFORE rerank
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

    # 5.05 HyDE post-rerank fallback — second-pass retrieval for low-recall
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

    # 5.4 Parent context expansion (C5) — fetch parent by ID after rerank
    parent_t0 = time.perf_counter()
    reranked = _expand_parent_context_post_rerank(reranked, cfg)
    timings_ms["parent_expansion"] = _elapsed_ms(parent_t0)

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
                    "answer": _strip_answer_links(cached["answer"]),
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
        "answer": _strip_answer_links(answer),
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
    """Streaming RAG flow — retrieval runs first, then generation is streamed.

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

    # ── Pre-retrieval query cache (P0 — stream variant) ──────────────────────
    # Profile scope (major|cohort) so a personal answer is never served to a
    # student with a different profile — see _build_cache_profile.
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
                        _strip_answer_links(_qcached["answer"])
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
    # program (e.g. học bổng) so universal answers are not narrowed to one major.
    # When major IS required, retrieval_major == resolved_major. See
    # query.profile_dependency. Decided once here, reused for every sub-query.
    from query.profile_dependency import (
        effective_major_for_retrieval,
    )  # noqa: PLC0415

    retrieval_major = effective_major_for_retrieval(
        question, search_query, routing_result, resolved_major
    )

    # Collection-aware routing (Phase 8 — Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    if cfg.get("find_all", False):
        routing_t0 = time.perf_counter()
        target_collections = list(cfg.get("collections") or [])
        logger.info(
            "find_all=true (stream) → bypassing routing, searching all collections: %s",
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

    # ── Populate metadata_out early (pre-generation) so caller can read it ──────
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

    # 4.5 Sibling chunk expansion (C1) — BEFORE rerank (streaming flow)
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

    # 5.05 HyDE post-rerank fallback — second-pass retrieval for low-recall
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

    # 5.4 Parent context expansion (C5) — fetch parent by ID after rerank
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

    # ── Final metadata update (post-rerank, pre-stream) ──────────────────────────
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

    # ── LLM Response Cache Check (Phase 2 - Stream) ─────────────────
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
                        _strip_answer_links(cached["answer"])
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
                        "Ngữ cảnh hội thoại đang quá dài. "
                        "Vui lòng bắt đầu phiên mới hoặc hỏi ngắn gọn hơn."
                    ) from retry_exc
                raise

        chunk = pending
        while chunk is not None:
            if first_token_ms is None:
                first_token_ms = _elapsed_ms(stream_t0)
            generated_chars += len(chunk)
            full_cached_answer.append(chunk)
            yield chunk
            chunk = next(iterator, None)

        timings_ms["stream_first_token"] = round(first_token_ms or 0.0, 2)
        timings_ms["stream_generate"] = _elapsed_ms(stream_t0)
        timings_ms["flow_total"] = _elapsed_ms(flow_t0)
        logger.info("rag_flow_stream: streamed %d chars", generated_chars)
        _log_timings("rag_flow_stream", timings_ms)

        stream_answer = "".join(full_cached_answer)

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


# ═══════════════════════════════════════════════════════════════════════════════
# Tavily Fallback
# ═══════════════════════════════════════════════════════════════════════════════


def _tavily_results_to_docs(
    search_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
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


def _extract_query_year(text: str) -> Optional[int]:
    """Return the most recent academic year (20XX) mentioned in the query.

    Used to drive Tavily's freshness filter so stale official pages from older
    years are dropped. Returns None when the query mentions no year.
    """
    years = re.findall(r"\b(20\d{2})\b", _fold_vietnamese(text or ""))
    return max(int(y) for y in years) if years else None


def _tavily_search_context(
    *,
    query: str,
    tavily_tool: Any | None,
    max_results: int = 3,
    search_depth: str = "basic",
    extract_urls: Optional[List[str]] = None,
    result_count: Optional[int] = None,
    content_char_limit: Optional[int] = None,
    query_year: Optional[int] = None,
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
                result_count=result_count,
                content_char_limit=content_char_limit,
                query_year=(
                    query_year
                    if query_year
                    else _extract_query_year(tavily_query)
                ),
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
    local_context: Optional[str] = None,
    result_count: Optional[int] = None,
    content_char_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Use Tavily web search and return answer, timings, source docs, status."""
    fallback_t0 = time.perf_counter()
    search_info = _tavily_search_context(
        query=(search_query or question).strip() or question,
        tavily_tool=tavily_tool,
        max_results=max_results,
        search_depth=search_depth,
        result_count=result_count,
        content_char_limit=content_char_limit,
    )
    timings_ms: Dict[str, float] = dict(search_info["timings"])
    web_context = str(search_info.get("context") or "")
    tavily_sources = list(search_info.get("sources") or [])
    # Early-exit only when web context is empty. Short official snippets are
    # still useful for notices/deadlines and should be allowed to regenerate.
    if not web_context:
        return {
            "answer": _strip_answer_links(answer),
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": False,
        }
    generation_context = _merge_local_and_web_context(
        str(local_context or "").strip(),
        web_context,
    )
    try:
        regenerate_t0 = time.perf_counter()
        new_answer = chat_model.generate(
            query=question,
            context=generation_context,
            history=history,
            mode="rag",
        )
        timings_ms["tavily_generate"] = _elapsed_ms(regenerate_t0)
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        logger.info("Tavily fallback generated %d chars", len(new_answer))
        return {
            "answer": _strip_answer_links(new_answer),
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
            "answer": _strip_answer_links(answer),
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": False,
        }
