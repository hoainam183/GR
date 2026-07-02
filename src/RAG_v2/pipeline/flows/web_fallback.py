"""Web/Tavily decision logic: dynamic/freshness detection, route lock, quality gate."""

from __future__ import annotations

from datetime import datetime
import logging
import re

from typing import Any, Dict, Generator, List, Optional, Set

from query.signals import (
    analyze_query_signals,
    extract_key_phrases,
    fold_vietnamese_text,
)
from retrieval.metadata_filters import (
    has_freshness_intent,
)

from .common import (
    _cfg_bool,
    _cfg_float,
    _cfg_str_list,
    _dedup_text_values,
    _fold_vietnamese,
    _is_date_within_days,
)
from .rerank_scoring import _best_explicit_rerank_score

logger = logging.getLogger(__name__)


_WEB_FALLBACK_DEFAULT_DYNAMIC_COLLECTIONS = ("kehoach",)
_WEB_FALLBACK_NO_INFO_PATTERNS = (
    # â”€â”€ Existing (8) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "toi khong tim thay thong tin nay trong tai lieu hien co",
    "khong tim thay thong tin",
    "khong co thong tin",
    "chua co thong tin",
    "khong du co so",
    "khong du thong tin",
    "tai lieu hien co khong",
    "chua tim thay",
    # â”€â”€ Rephrase variants (11) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Academic year injection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if has_freshness:
        if not re.search(r"\b20\d{2}\b", folded):
            now = datetime.now()
            current_year = now.year
            # HUST academic year: Aug â†’ Jul
            if now.month >= 8:
                ay_start, ay_end = current_year, current_year + 1
            else:
                ay_start, ay_end = current_year - 1, current_year

            # Transition period: "nÄƒm há»c má»›i/tá»›i" in July+ â†’ next AY
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

            extras.append(f"nÄƒm há»c {ay_start}-{ay_end}")
        extras.append("CTT ÄHBKHN")

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
            extras.append("Ä‘Äƒng kÃ½ káº¿ hoáº¡ch há»c táº­p")

    # â”€â”€ Content-type signal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if any(kw in folded for kw in ("lich", "ke hoach", "thong bao", "dang ky")):
        if "thong bao" not in folded and "ke hoach" not in folded:
            extras.append("thÃ´ng bÃ¡o káº¿ hoáº¡ch")

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

    # â”€â”€ C3: Freshness date_str validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # If kehoach docs exist but none have date_str, we can't verify freshness
    # â†’ conservative: allow Tavily (don't suppress)
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
    "hiáº¿n mÃ¡u Ä‘Æ°á»£c máº¥y Ä‘iá»ƒm rÃ¨n luyá»‡n".
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
