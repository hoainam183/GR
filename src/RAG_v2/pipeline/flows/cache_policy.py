"""Answer-cache gating and query-cache bypass policy."""

from __future__ import annotations

import logging

from typing import Any, Dict, Generator, List, Optional, Set

from retrieval.metadata_filters import (
    has_freshness_intent,
)

from .web_fallback import (
    _answer_has_no_info_signal,
    _is_dynamic_web_query,
)

logger = logging.getLogger(__name__)



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



def _build_cache_profile(user_context: Optional[Dict[str, Any]]) -> str:
    """Normalized ``major|cohort`` scope for answer-cache keys.

    Without this scope the query-only cache (no doc_ids) would serve a personal
    answer generated for one student ("Ä‘iá»u kiá»‡n tá»‘t nghiá»‡p cá»§a tÃ´i") verbatim to
    any other student asking the same words â€” a cross-student data leak. An empty
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
