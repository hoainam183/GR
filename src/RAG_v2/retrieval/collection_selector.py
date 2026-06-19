"""Collection Selector — choose target collections based on domain classification."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Union

from query.signals import (
    QuerySignals,
    analyze_query_signals,
    coerce_query_signals,
    fold_vietnamese_text,
)

logger = logging.getLogger(__name__)

# ─── Domain → Collection mapping ────────────────────────────────────────────────
DOMAIN_TO_COLLECTIONS: Dict[str, List[str]] = {
    "ctdt": ["ctdt"],
    "quydinh": ["quydinh", "stsv"],   # regulations ↔ student support overlap
    "kehoach": ["kehoach"],
    "stsv": ["stsv", "quydinh"],       # student support ↔ regulations overlap
}

ALL_COLLECTIONS: List[str] = ["stsv", "quydinh", "kehoach", "ctdt"]
# Include curriculum collection in low-confidence fallback so course queries
# still retrieve ctdt chunks when router confidence is borderline.
MULTI_DOMAIN_FALLBACK: List[str] = ["quydinh", "stsv", "ctdt"]

CONFIDENCE_THRESHOLD: float = 0.55  # Tier-1 calibration makes this meaningful
KEHOACH_CLOSE_PROBABILITY_MARGIN: float = 0.10


def _dedup(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def _coerce_probabilities(
    probabilities: Optional[Dict[str, Any]],
) -> Dict[str, float]:
    if not isinstance(probabilities, dict):
        return {}
    output: Dict[str, float] = {}
    for domain, value in probabilities.items():
        key = str(domain).strip().lower()
        if not key:
            continue
        try:
            output[key] = float(value)
        except (TypeError, ValueError):
            continue
    return output


def _top_probability(probabilities: Dict[str, float]) -> tuple[Optional[str], float]:
    if not probabilities:
        return None, 0.0
    domain, score = max(probabilities.items(), key=lambda item: item[1])
    return domain, score


def _has_kehoach_routing_intent(signals: QuerySignals) -> bool:
    return bool(
        signals.freshness
        or signals.schedule_intent
        or signals.deadline_intent
        or signals.announcement_intent
    )


def _should_add_kehoach_low_confidence(
    *,
    signals: QuerySignals,
    probabilities: Dict[str, float],
    active_domains: List[str],
    confidence_threshold: float,
) -> bool:
    if "kehoach" in active_domains:
        return False

    top_domain, top_score = _top_probability(probabilities)
    kehoach_score = probabilities.get("kehoach", 0.0)
    kehoach_close_to_top = bool(
        kehoach_score > 0.0
        and top_score - kehoach_score <= KEHOACH_CLOSE_PROBABILITY_MARGIN
    )
    if kehoach_close_to_top:
        return True

    if not _has_kehoach_routing_intent(signals):
        return False

    if not probabilities:
        return True

    strong_non_kehoach = bool(
        top_domain
        and top_domain != "kehoach"
        and top_score >= confidence_threshold
        and top_score - kehoach_score > KEHOACH_CLOSE_PROBABILITY_MARGIN
    )
    return not strong_non_kehoach


def _is_ctdt_course_lookup(query: str, collections: List[str]) -> bool:
    """Return True for course/credit lookup that should stay in CTDT."""
    if "ctdt" not in collections:
        return False
    folded = fold_vietnamese_text(query)

    # "tín chỉ" có hai nghĩa: khối lượng môn học (ctdt) và đơn vị tính học phí
    # (quydinh). Khi query mang ngữ cảnh học phí/mức thu, đây KHÔNG phải tra cứu
    # chương trình đào tạo — để quydinh được augment vào collections.
    fee_context = bool(
        re.search(r"\b(hoc phi|muc thu|dong tien|tien hoc)\b", folded)
    )

    course_like = bool(
        re.search(r"\b(mon|hoc phan|ma hoc phan|tin chi|tien quyet|song hanh)\b", folded)
    )
    rule_like = bool(
        re.search(r"\b(tot nghiep|xet tot nghiep|dieu kien|quy dinh|diem ren luyen)\b", folded)
    )
    return course_like and not rule_like and not fee_context


def _is_foreign_language_policy_lookup(query: str) -> bool:
    """Return True for cohort/FL-code queries whose rules live in ``quydinh``."""
    folded = fold_vietnamese_text(query)
    has_fl_code = bool(re.search(r"\bfl\d{4}\b", folded))
    if has_fl_code:
        return True

    has_cohort = bool(re.search(r"\bk(?:6[5-9]|70)\b", folded))
    if not has_cohort:
        return False

    foreign_language_hint = bool(
        re.search(
            r"\b("
            r"ngoai ngu|tieng\s+(?:anh|duc|nhat|phap|trung|han|nga)|"
            r"ielts|toeic|vstep|bac\s*\d+(?:\.\d+)?|"
            r"nhom\s*(?:may|\d+)|thuoc nhom|xep hoc|"
            r"mien hoc phan|quy doi|chuan dau ra"
            r")\b",
            folded,
        )
    )
    return foreign_language_hint


def augment_collections_for_query(
    query: Optional[str],
    collections: List[str],
    query_signals: Optional[Union[QuerySignals, Dict[str, Any]]] = None,
) -> List[str]:
    """Expand target collections using generic query traits.

    Policy/table lookups should not miss ``quydinh``. Procedural support
    queries should include ``stsv``. CTDT course/credit lookups are kept focused
    unless the query also has explicit rule/eligibility intent.
    """
    if not query:
        return list(collections)

    signals = (
        coerce_query_signals(query_signals)
        if query_signals is not None
        else analyze_query_signals(query)
    )
    output = _dedup(list(collections))
    ctdt_course_lookup = _is_ctdt_course_lookup(query, output)
    foreign_language_policy_lookup = _is_foreign_language_policy_lookup(query)

    # "Môn X học/đăng ký vào kỳ mấy?" — semester placement lives in the standard
    # study plan (ctdt), not in registration schedules (kehoach). When the query
    # asks WHICH semester a course sits in and carries no schedule/deadline timing
    # markers, ensure ctdt is searched and prioritized regardless of router output.
    curriculum_semester_lookup = bool(
        signals.curriculum_semester_intent
        and not (
            signals.schedule_intent
            or signals.deadline_intent
            or signals.announcement_intent
            or signals.freshness
        )
    )

    needs_regulations = (
        signals.eligibility_check
        or signals.table_lookup
        or signals.exact_policy_lookup
    )
    if foreign_language_policy_lookup:
        output = _dedup(["quydinh", *output])

    if needs_regulations and not ctdt_course_lookup:
        output = _dedup(["quydinh", *output])

    if signals.procedural_support:
        output = _dedup([*output, "stsv"])

    if signals.multi_domain and signals.eligibility_check:
        output = _dedup([*output, "ctdt"])

    if curriculum_semester_lookup:
        output = _dedup(["ctdt", *output])

    # Schedule / deadline / announcement / freshness questions live in kehoach.
    # The low-confidence branch already adds it; mirror that here so a confident
    # mis-route of a timing question (e.g. "lịch thi cuối kỳ khi nào" → quydinh)
    # still searches kehoach. curriculum_semester_lookup requires these signals to
    # be OFF, so "môn X kỳ mấy" stays in ctdt and is unaffected.
    if _has_kehoach_routing_intent(signals) and not curriculum_semester_lookup:
        output = _dedup([*output, "kehoach"])

    return output


class CollectionSelector:
    """Selects target Qdrant/ES collections based on domain classification result.

    Supports both single-domain (``domain: str``) and multi-domain
    (``domains: List[str]``) inputs from the router.  When multiple domains
    are active, the returned collections are the union of all mapped collections.

    Parameters:
        confidence_threshold: Minimum confidence to trust the domain prediction.
        fallback_collections: Collections used when confidence is below threshold
                              AND the LLM fallback is not available.
        all_collections: Full list of available collections.
    """

    def __init__(
        self,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        fallback_collections: Optional[List[str]] = None,
        all_collections: Optional[List[str]] = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.fallback_collections = (
            fallback_collections or MULTI_DOMAIN_FALLBACK
        )
        self.all_collections = all_collections or ALL_COLLECTIONS

    def select(
        self,
        domain: Optional[Union[str, List[str]]] = None,
        confidence: float = 0.0,
        domains: Optional[List[str]] = None,
        query: Optional[str] = None,
        query_signals: Optional[Union[QuerySignals, Dict[str, Any]]] = None,
        probabilities: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Return the list of collections to search.

        Accepts either the legacy ``domain`` (single string) interface or the
        new ``domains`` (list of strings) interface.  When ``domains`` is
        provided it takes precedence over ``domain``.

        Args:
            domain: Primary domain label from ``DomainClassifier`` or a list
                    of domain labels (backward-compatible overload).
            confidence: Calibrated classification confidence (0–1).
            domains: Explicit list of active domains (Tier-2 multi-label).
            probabilities: Optional raw per-domain probabilities from the
                           classifier. Used only for low-confidence widening.

        Returns:
            List of collection name strings (order preserved, duplicates removed).
        """
        # Normalise: prefer explicit `domains` list, otherwise fall back to
        # `domain` which may itself be a string or list.
        active_domains: List[str]
        if domains is not None:
            active_domains = [d for d in domains if d]
        elif isinstance(domain, list):
            active_domains = [d for d in domain if d]
        elif domain:
            active_domains = [domain]
        else:
            active_domains = []

        signals = (
            coerce_query_signals(query_signals)
            if query_signals is not None
            else analyze_query_signals(query or "")
        )
        probability_map = _coerce_probabilities(probabilities)

        if not active_domains:
            logger.info(
                "CollectionSelector: no domain → searching all %d collections",
                len(self.all_collections),
            )
            return augment_collections_for_query(
                query,
                list(self.all_collections),
                query_signals=signals,
            )

        # Resolve each domain to its collection(s) and take the union.
        seen: set = set()
        target: List[str] = []
        for dom in active_domains:
            cols = DOMAIN_TO_COLLECTIONS.get(dom)
            if cols is None:
                logger.warning(
                    "CollectionSelector: unknown domain=%s → skipping", dom
                )
                continue
            for col in cols:
                if col not in seen:
                    seen.add(col)
                    target.append(col)

        if confidence < self.confidence_threshold:
            # Low confidence still carries useful signal: keep the active
            # domain(s) first, then broaden with fallback collections.
            broadened = list(target)
            for col in self.fallback_collections:
                if col not in seen:
                    seen.add(col)
                    broadened.append(col)
            if _should_add_kehoach_low_confidence(
                signals=signals,
                probabilities=probability_map,
                active_domains=active_domains,
                confidence_threshold=self.confidence_threshold,
            ) and "kehoach" not in seen:
                insert_at = len(target) if target else 0
                broadened.insert(insert_at, "kehoach")
                seen.add("kehoach")
            if not broadened:
                broadened = list(self.fallback_collections)
            logger.info(
                "CollectionSelector: domains=%s conf=%.3f < threshold=%.3f "
                "→ fallback collections: %s",
                active_domains,
                confidence,
                self.confidence_threshold,
                broadened,
            )
            return augment_collections_for_query(
                query,
                broadened,
                query_signals=signals,
            )

        if not target:
            logger.warning(
                "CollectionSelector: could not resolve domains=%s "
                "→ searching all collections",
                active_domains,
            )
            return augment_collections_for_query(
                query,
                list(self.all_collections),
                query_signals=signals,
            )

        logger.info(
            "CollectionSelector: domains=%s conf=%.3f → collections: %s",
            active_domains,
            confidence,
            target,
        )
        return augment_collections_for_query(
            query,
            target,
            query_signals=signals,
        )
