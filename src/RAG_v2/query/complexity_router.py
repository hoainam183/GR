"""Complexity Router — classifies queries into chitchat / simple / complex tiers.

Improvements over original:
- Added logging for routing decisions (enables analysis & debugging).
- Added confidence signal (pattern-based vs heuristic-based).
- Better pattern coverage for ambiguous queries.
- Optional DomainClassifier integration for borderline cases.
- ``complex_subtype`` field for planner vs agent-loop routing.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from .signals import analyze_query_signals, fold_vietnamese_text

logger = logging.getLogger(__name__)

# ─── Chitchat patterns ────────────────────────────────────────────────────────
# Short-circuit: matched queries never reach the RAG pipeline.

CHITCHAT_PATTERNS: list[str] = [
    r"^(xin chào|hello|hi|chào|hey)\b",
    r"^(ok|oke|okay|okie)\b",
    r"^(bạn là ai|you are|who are you)",
    r"^(cảm ơn|thank|thanks)\b",
    r"^(tạm biệt|bye|goodbye)\b",
]

# ─── Complex patterns ─────────────────────────────────────────────────────────
# Queries matching any of these need the Planner-Executor agent.
# Design principle: be SPECIFIC to avoid false positives on simple questions.
#
# Each pattern is tagged with a complex_subtype so the downstream planner can
# decide whether to decompose first or plan directly.

# Patterns → complex_subtype mapping.
# Order matters: first match wins.
_COMPLEX_PATTERN_SPECS: list[tuple[str, str]] = [
    # ── comparison subtype ────────────────────────────────────────────────────
    # Explicit comparison keyword
    (r"\bso\s*sánh\b", "comparison"),
    # Two cohort codes mentioned in the same query (K65 … K70)
    (r"\bK\d{2,3}\b.{1,120}\bK\d{2,3}\b", "comparison"),
    # Two programme codes mentioned (IT-E6 … IT-E7, MI-E10 ...)
    (r"\b(?:IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH|ME|CH|BF|MS|HE|TE|TX|TROY)\s*-?\s*(?:E\d{1,2}|EP|GU|LUH|NUT|IT|\d{1,2})\b.{1,80}\b(?:IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH|ME|CH|BF|MS|HE|TE|TX|TROY)\s*-?\s*(?:E\d{1,2}|EP|GU|LUH|NUT|IT|\d{1,2})\b", "comparison"),
    # Difference / similarity ONLY when paired with cohort / programme context
    (r"(khác nhau|khác biệt|giống nhau).{0,40}(K\d{2}|khóa|ngành|chương trình|học kỳ|quy định)", "comparison"),
    (r"(K\d{2}|khóa|ngành|chương trình).{0,40}(khác nhau|khác biệt|giống nhau)", "comparison"),

    # ── multi_source override — curriculum+regulation compound queries ─────────
    # These queries combine an equivalence lookup (ctdt) WITH a graduation
    # condition lookup (quydinh). They are better handled by decomposition than
    # direct planning.
    (
        r"(?:tương\s+đương|chuyển\s+đổi|thay\s+thế).{0,60}"
        r"(?:đồ\s+án|tốt\s+nghiệp|xét\s+(?:tốt\s+nghiệp|nhận)|thời\s+hạn)",
        "multi_source",
    ),
    (
        r"(?:đồ\s+án|tốt\s+nghiệp|xét\s+(?:tốt\s+nghiệp|nhận)).{0,60}"
        r"(?:tương\s+đương|chuyển\s+đổi|thay\s+thế)",
        "multi_source",
    ),

    # ── personal eligibility wording ─────────────────────────────────────────
    # The old personal_check subtype is intentionally removed. These route as
    # multi_source so query_v3 uses the normal Planner-Executor path.
    (
        r"\b(tôi|mình|em)\b.{0,80}\b(có\s+thể|đủ\s+điều\s+kiện|đạt\s+điều\s+kiện|đạt\s+chuẩn|được\s+không|có\s+được)\b",
        "multi_source",
    ),

    # ── multi_source subtype ──────────────────────────────────────────────────
    (r"\bđủ\s+điều\s+kiện\b", "multi_source"),
    (r"\b(có\s+thể|có\s+được)\b.{0,30}\b(tốt nghiệp|đăng ký|đăng kí|xét duyệt|nhận học bổng)\b", "multi_source"),
    (r"(môn|học phần).{0,30}\b(được|có)\s+(đăng ký|đăng kí|mở)\b", "multi_source"),
    (r"\btất\s+cả.{0,20}điều\s+kiện\b", "multi_source"),

    # ── general subtype (ambiguous / multi-step) ──────────────────────────────
    (r"^(học bổng|môn học|lịch|quy định|chương trình)\s*\??$", "general"),
    (r"^cho\s+tôi\s+biết\s+về\s+\w{1,15}\s*$", "general"),
    (r"\bvà\b.{0,30}\b(cho biết|liệt kê|so sánh|giải thích)\b", "general"),
]

# Build compiled caches from the specs
COMPLEX_PATTERNS: list[str] = [pat for pat, _ in _COMPLEX_PATTERN_SPECS]

# ─── Compiled caches ──────────────────────────────────────────────────────────

_CHITCHAT_RE: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in CHITCHAT_PATTERNS
]
_COMPLEX_SPECS_RE: list[tuple[re.Pattern, str]] = [
    (re.compile(pat, re.IGNORECASE), subtype)
    for pat, subtype in _COMPLEX_PATTERN_SPECS
]
# Detect query có nhiều chủ đề — dùng để tinh chỉnh word_count heuristic.
# Nếu query dài nhưng chỉ 1 chủ đề (không có connector này) → giữ route simple.
_MULTI_TOPIC_RE: re.Pattern = re.compile(
    r"\b(cũng|ngoài ra|đồng thời|bên cạnh đó|kết hợp)\b",
    re.IGNORECASE,
)

_FOLDED_MULTI_TOPIC_RE: re.Pattern = re.compile(
    r"\b(cung|ngoai ra|dong thoi|ben canh do|ket hop)\b",
    re.IGNORECASE,
)
_FOLDED_COMPARISON_RE: re.Pattern = re.compile(
    r"\b(so sanh|so voi|khac nhau|khac biet|giong nhau)\b",
    re.IGNORECASE,
)
# Bare "may" (how many) is intentionally omitted: it collides with "máy"
# (machine) after accent folding, so the how-many sense is detected via
# ``query_signals.exact_policy_lookup`` (accent-aware) instead. "nhom may"
# (which group) is kept — "máy" does not follow "nhóm".
_FOLDED_SINGLE_FACT_RE: re.Pattern = re.compile(
    r"\b(bao nhieu|bao lau|bao lan|muc nao|muc diem|thang diem|can bao nhieu|nhom may)\b",
    re.IGNORECASE,
)
# Accent-insensitive fallback for the diacritic-only personal-eligibility pattern
# in ``_COMPLEX_PATTERN_SPECS`` (the "tôi/mình/em … đủ điều kiện/được không" rule).
# Without this, no-diacritic input (common on mobile) such as
# "toi co du dieu kien tot nghiep khong" falls through to ``simple``.
_FOLDED_PERSONAL_ABILITY_RE: re.Pattern = re.compile(
    r"\b(toi|minh|em)\b.{0,80}\b(co the|du dieu kien|dat dieu kien|dat chuan|du chuan|duoc khong|co duoc)\b",
    re.IGNORECASE,
)


def _is_single_fact_policy_lookup(
    q_folded: str,
    query_signals: Any,
) -> bool:
    """Return True for one-shot policy/table lookups that should stay RAG."""
    has_lookup_signal = bool(
        query_signals.exact_policy_lookup
        or query_signals.table_lookup
        or _FOLDED_SINGLE_FACT_RE.search(q_folded)
    )
    if not has_lookup_signal:
        return False
    if _FOLDED_COMPARISON_RE.search(q_folded):
        return False
    if _FOLDED_MULTI_TOPIC_RE.search(q_folded):
        return False
    if q_folded.count("?") > 1:
        return False
    if q_folded.count(" va ") >= 3:
        return False
    return True


class ComplexityRouter:
    """
    Classifies an incoming query into one of three routing tiers:

    - ``"chitchat"``  — greeting / acknowledgement, handled by a simple
                        canned-response handler; no RAG needed.
    - ``"simple"``    — single-domain factual question; handled by the
                        existing RAG v2 pipeline.
    - ``"complex"``   — multi-domain, comparative, or ambiguous query;
                        routed to the Planner-Executor agent.

    When tier is ``"complex"``, the result also contains a
    ``complex_subtype`` field:

    - ``"comparison"``   — explicit A-vs-B comparison → planner path
    - ``"multi_source"`` — needs data from ≥2 collections → planner path
    - ``"general"``      — ambiguous / multi-step → planner path without decomposition

    The ``route()`` method now returns a dict with ``tier``, ``reason``,
    ``confidence``, and optionally ``complex_subtype`` keys for better
    observability. The ``route_tier()`` convenience method returns just
    the tier string for backwards compatibility.
    """

    def route(self, query: str) -> Dict[str, Any]:
        """Classify query and return ``{tier, reason, confidence[, complex_subtype]}``.

        Returns:
            Dict with keys:

            - ``tier``: ``"chitchat"`` | ``"simple"`` | ``"complex"`` | ``"unknown"``
              (``"unknown"`` = no decisive Tier-0 signal; the pipeline resolves it
              via the ML multi-label classifier and an LLM judge)
            - ``reason``: human-readable explanation of the routing decision
            - ``confidence``: ``"high"`` (pattern match) or ``"medium"`` (heuristic)
            - ``complex_subtype`` (only when tier=complex):
              ``"comparison"`` | ``"multi_source"`` | ``"general"``
        """
        q = query.strip()
        q_lower = q.lower()
        q_folded = fold_vietnamese_text(q)
        query_signals = analyze_query_signals(q)
        query_signals_dict = query_signals.to_dict()

        # 1. Chitchat — fast path, checked first
        for pattern in _CHITCHAT_RE:
            if pattern.search(q_lower):
                result = {
                    "tier": "chitchat",
                    "reason": f"chitchat_pattern: {pattern.pattern[:40]}",
                    "confidence": "high",
                    "query_signals": query_signals_dict,
                }
                logger.info(
                    "ComplexityRouter: %r -> %s (%s)",
                    q[:60], result["tier"], result["reason"],
                )
                return result

        # 2. Complex signals — regex patterns with subtype tagging
        # 2. Signal-based overrides for broad/personal requests. These cover
        # variants like "điều kiện tốt nghiệp của tôi", where the personal
        # reference appears after the eligibility concept.
        if len(re.findall(r'\bcho\b', q_lower)) >= 2 and (re.search(r"\bvà\b", q_lower) or re.search(r"\bva\b", q_folded)):
            result = {
                "tier": "complex",
                "reason": "signals: repeated_request_connector",
                "confidence": "high",
                "complex_subtype": "general",
                "query_signals": query_signals_dict,
            }
            logger.info(
                "ComplexityRouter: %r -> %s/%s (%s)",
                q[:60], result["tier"], result["complex_subtype"], result["reason"],
            )
            return result

        if _is_single_fact_policy_lookup(q_folded, query_signals):
            result = {
                "tier": "simple",
                "reason": "signals: single_fact_policy_lookup",
                "confidence": "high",
                "query_signals": query_signals_dict,
            }
            logger.info(
                "ComplexityRouter: %r -> %s (%s)",
                q[:60], result["tier"], result["reason"],
            )
            return result

        if query_signals.personal_reference and query_signals.eligibility_check:
            result = {
                "tier": "complex",
                "reason": "signals: personal_reference + eligibility_check",
                "confidence": "high",
                "complex_subtype": "multi_source",
                "query_signals": query_signals_dict,
            }
            logger.info(
                "ComplexityRouter: %r -> %s/%s (%s)",
                q[:60], result["tier"], result["complex_subtype"], result["reason"],
            )
            return result

        # Accent-insensitive parity with the diacritic-only personal-eligibility
        # rule in _COMPLEX_PATTERN_SPECS: bare pronoun + ability/eligibility wording
        # (e.g. "toi co du dieu kien tot nghiep khong") must reach the agent path.
        if _FOLDED_PERSONAL_ABILITY_RE.search(q_folded):
            result = {
                "tier": "complex",
                "reason": "signals: folded_personal_eligibility",
                "confidence": "high",
                "complex_subtype": "multi_source",
                "query_signals": query_signals_dict,
            }
            logger.info(
                "ComplexityRouter: %r -> %s/%s (%s)",
                q[:60], result["tier"], result["complex_subtype"], result["reason"],
            )
            return result

        # NOTE: The old graduation/eligibility multi-source gate lived here. It
        # re-derived a *narrower* program-context regex than ``signals.py`` and
        # had to enumerate program/major tokens — so a bare major code like
        # "IT1" slipped through to ``simple`` while "của tôi" did not. That entity
        # enumeration is an anti-pattern (every new major needed a regex edit), so
        # the multi-collection decision is now made data-drivenly by the pipeline's
        # tiered complexity decision (ML multi-label domains + LLM on borderline).
        # Queries that reach the fall-through below return ``tier="unknown"`` so
        # ``RAGPipeline._decide_complexity`` can apply Tier-1/Tier-2.

        if (
            _FOLDED_COMPARISON_RE.search(q_folded)
            and re.search(r"\b(k\d{2,3}|nganh|chuong trinh|ctdt|hoc ky|quy dinh)\b", q_folded)
        ):
            result = {
                "tier": "complex",
                "reason": "signals: folded_comparison",
                "confidence": "high",
                "complex_subtype": "comparison",
                "query_signals": query_signals_dict,
            }
            logger.info(
                "ComplexityRouter: %r -> %s/%s (%s)",
                q[:60], result["tier"], result["complex_subtype"], result["reason"],
            )
            return result

        if (
            " va " in q_folded
            and re.search(r"\b(cho biet|liet ke|so sanh|giai thich)\b", q_folded)
        ):
            result = {
                "tier": "complex",
                "reason": "signals: multi_step_connector",
                "confidence": "high",
                "complex_subtype": "general",
                "query_signals": query_signals_dict,
            }
            logger.info(
                "ComplexityRouter: %r -> %s/%s (%s)",
                q[:60], result["tier"], result["complex_subtype"], result["reason"],
            )
            return result

        for pattern, subtype in _COMPLEX_SPECS_RE:
            if pattern.search(q):
                result = {
                    "tier": "complex",
                    "reason": f"complex_pattern: {pattern.pattern[:50]}",
                    "confidence": "high",
                    "complex_subtype": subtype,
                    "query_signals": query_signals_dict,
                }
                logger.info(
                    "ComplexityRouter: %r -> %s/%s (%s)",
                    q[:60], result["tier"], subtype, result["reason"],
                )
                return result

        # 3. Structural heuristics — lower confidence, general subtype
        word_count = len(q.split())
        if word_count > 30:
            # Chỉ route complex nếu query dài VÀ có dấu hiệu nhiều chủ đề.
            # Query dài về 1 chủ đề duy nhất (ví dụ: mô tả chi tiết 1 quy trình)
            # không cần agent loop — simple RAG là đủ.
            has_multiple_topics = bool(_MULTI_TOPIC_RE.search(q_lower))
            if has_multiple_topics:
                result = {
                    "tier": "complex",
                    "reason": f"heuristic: word_count={word_count}>30 + multi_topic_connector",
                    "confidence": "medium",
                    "complex_subtype": "general",
                    "query_signals": query_signals_dict,
                }
                logger.info(
                    "ComplexityRouter: %r -> %s (%s)",
                    q[:60], result["tier"], result["reason"],
                )
                return result
            else:
                # Query dài nhưng single-topic → giữ simple (RAG đơn giản là đủ)
                logger.info(
                    "ComplexityRouter: %r -> simple (word_count=%d but single_topic)",
                    q[:60], word_count,
                )

        if q.count("?") > 1:
            result = {
                "tier": "complex",
                "reason": f"heuristic: multiple_questions={q.count('?')}",
                "confidence": "medium",
                "complex_subtype": "general",
                "query_signals": query_signals_dict,
            }
            logger.info(
                "ComplexityRouter: %r -> %s (%s)",
                q[:60], result["tier"], result["reason"],
            )
            return result

        # Three or more conjunctions suggest a compound multi-part question
        if q_lower.count(" và ") >= 3:
            result = {
                "tier": "complex",
                "reason": f"heuristic: conjunction_count={q_lower.count(' và ')}>=3",
                "confidence": "medium",
                "complex_subtype": "general",
                "query_signals": query_signals_dict,
            }
            logger.info(
                "ComplexityRouter: %r -> %s (%s)",
                q[:60], result["tier"], result["reason"],
            )
            return result

        # Fall-through: cheap Tier-0 patterns saw no decisive signal. Return
        # ``"unknown"`` (not ``"simple"``) so the pipeline escalates to the
        # ML multi-label classifier (Tier 1) and, only when ≥2 collections are
        # active, the LLM judge (Tier 2). Callers that want a hard tier (e.g.
        # ``route_tier``) treat ``"unknown"`` as ``"simple"``.
        result = {
            "tier": "unknown",
            "reason": "default: no decisive Tier-0 signal — defer to ML/LLM tiers",
            "confidence": "low",
            "query_signals": query_signals_dict,
        }
        logger.info(
            "ComplexityRouter: %r -> %s (%s)",
            q[:60], result["tier"], result["reason"],
        )
        return result

    def route_tier(self, query: str) -> str:
        """Return just the tier string (``'chitchat'``, ``'simple'``, ``'complex'``).

        Backwards-compatible convenience method. The internal ``"unknown"`` tier
        (Tier-0 saw no decisive signal) collapses to ``"simple"`` here, since
        this helper has no access to the ML/LLM tiers that resolve it.
        """
        tier = self.route(query)["tier"]
        return "simple" if tier == "unknown" else tier
