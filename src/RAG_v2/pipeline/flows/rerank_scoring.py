"""Score-cliff pruning, rerank traces, and local-evidence scoring."""

from __future__ import annotations

import logging

from typing import Any, Dict, Generator, List, Optional, Set

from reranking.base import BaseReranker

from .common import (
    _cfg_float,
    _safe_float,
)

logger = logging.getLogger(__name__)



# â”€â”€ B1: Per-collection score cliff â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_CLIFF_MIN_GAP_BY_COLLECTION = {
    "kehoach": 0.5,  # Tight clusters â†’ smaller gap is significant
    "ctdt": 2.0,  # Wide spreads â†’ need larger gap
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
