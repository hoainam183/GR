"""Retrieval helpers: top_k, candidate pool, reranker kwargs, expansion, dedup, ordering."""

from __future__ import annotations

import logging
import re

from typing import Any, Dict, Generator, List, Optional, Set

from .common import (
    _cfg_bool,
    _cfg_float,
    _cfg_int,
    _safe_float,
)

logger = logging.getLogger(__name__)


# Detect "list-all" queries: asking to enumerate multiple items.
# Examples: "cÃ¡c há»c pháº§n tiáº¿ng nháº­t", "táº¥t cáº£ mÃ´n báº¯t buá»™c", "danh sÃ¡ch há»c pháº§n"
_LIST_QUERY_RE = re.compile(
    r"\b(?:cÃ¡c|táº¥t\s+cáº£|danh\s*sÃ¡ch|liá»‡t\s*kÃª|nhá»¯ng|bao\s+gá»“m\s+nhá»¯ng|toÃ n\s+bá»™|háº¿t)\b",
    re.IGNORECASE,
)
_LIST_TOP_K_MULTIPLIER = 2  # double top_k for list queries
_LIST_TOP_K_MAX = 12  # cap to avoid excessive reranking latency


def _resolve_top_k(base_top_k: int, query: str) -> int:
    """Return an effective top_k, scaled up for list/enumerate queries.

    When the user asks to enumerate multiple items ("cÃ¡c há»c pháº§n",
    "táº¥t cáº£ mÃ´n", "danh sÃ¡ch", â€¦) a single topic can span many chunks.
    Doubling top_k (capped at _LIST_TOP_K_MAX) prevents truncating the
    result set before the LLM sees all relevant items.
    """
    if _LIST_QUERY_RE.search(query or ""):
        scaled = base_top_k * _LIST_TOP_K_MULTIPLIER
        effective = min(scaled, _LIST_TOP_K_MAX)
        if effective > base_top_k:
            logger.info(
                "List query detected â€” top_k scaled %d â†’ %d",
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


# â”€â”€ C4: Routing confidence candidate pool increase â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
            "Low routing confidence (%.3f) â†’ expanding candidate pool %d â†’ %d",
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


# â”€â”€ C5: Parent context expansion (post-rerank) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _expand_parent_context_post_rerank(
    reranked: List[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Expand child results with parent chunk context (AFTER rerank).

    Best practice order: Search children â†’ Rerank â†’ Expand parent â†’ Format.
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
        from retrieval.parent_context import get_parent_expander
        from config.settings import Settings

        settings = Settings()
        expander = get_parent_expander(
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


# â”€â”€ C1: Sibling chunk expansion â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
    by (source, chunk_index Â± window) in the same collection.

    Args:
        candidates: Raw search results (pre-rerank).
        searcher: MultiCollectionSearch instance with get_by_metadata().
        expand_top_n: Only expand top N candidates.
        window: Â±N sibling offset (default Â±1).
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
