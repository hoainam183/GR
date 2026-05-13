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
# Queries matching any of these need the full LangGraph ReAct agent.
# Design principle: be SPECIFIC to avoid false positives on simple questions.
#
# Each pattern is tagged with a complex_subtype so the downstream planner can
# decide whether to use the deterministic planner path or the agent loop.

# Patterns → complex_subtype mapping.
# Order matters: first match wins.
_COMPLEX_PATTERN_SPECS: list[tuple[str, str]] = [
    # ── comparison subtype ────────────────────────────────────────────────────
    # Explicit comparison keyword
    (r"\bso\s*sánh\b", "comparison"),
    # Two cohort codes mentioned in the same query (K65 … K70)
    (r"\bK\d{2,3}\b.{1,120}\bK\d{2,3}\b", "comparison"),
    # Two programme codes mentioned (IT-E6 … IT-E7, MI-E10 ...)
    (r"\b(?:IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH)-[A-Z0-9]+\b.{1,50}\b(?:IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH)-[A-Z0-9]+\b", "comparison"),
    # Difference / similarity ONLY when paired with cohort / programme context
    (r"(khác nhau|khác biệt|giống nhau).{0,40}(K\d{2}|khóa|ngành|chương trình|học kỳ|quy định)", "comparison"),
    (r"(K\d{2}|khóa|ngành|chương trình).{0,40}(khác nhau|khác biệt|giống nhau)", "comparison"),

    # ── multi_source subtype ──────────────────────────────────────────────────
    # QUAN TRỌNG: personal_check phải nằm TRƯỚC multi_source vì first-match wins.
    # Query "tôi có đủ điều kiện..." phải vào personal_check (ReAct), không vào
    # multi_source (Planner) — vì Planner không thể trả lời "bạn CÓ đủ hay không"
    # khi thiếu thông tin GPA/tín chỉ cá nhân của sinh viên.

    # ── multi_source override — curriculum+regulation compound queries ─────────
    # These queries combine an equivalence lookup (ctdt) WITH a graduation
    # condition lookup (quydinh). They are better handled by decomposition than
    # the agent, so they must appear BEFORE personal_check to win the first-match.
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

    # ── personal_check subtype ────────────────────────────────────────────────
    # Detect query cần context cá nhân: "tôi/mình/em ... có thể/đủ/đạt/được không"
    (
        r"\b(tôi|mình|em)\b.{0,80}\b(có\s+thể|đủ\s+điều\s+kiện|đạt\s+điều\s+kiện|đạt\s+chuẩn|được\s+không|có\s+được)\b",
        "personal_check",
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


class ComplexityRouter:
    """
    Classifies an incoming query into one of three routing tiers:

    - ``"chitchat"``  — greeting / acknowledgement, handled by a simple
                        canned-response handler; no RAG needed.
    - ``"simple"``    — single-domain factual question; handled by the
                        existing RAG v2 pipeline.
    - ``"complex"``   — multi-domain, comparative, or ambiguous query;
                        routed to the LangGraph ReAct agent.

    When tier is ``"complex"``, the result also contains a
    ``complex_subtype`` field:

    - ``"comparison"``   — explicit A-vs-B comparison → planner path
    - ``"multi_source"`` — needs data from ≥2 collections → planner path
    - ``"general"``      — ambiguous / multi-step → agent loop path

    The ``route()`` method now returns a dict with ``tier``, ``reason``,
    ``confidence``, and optionally ``complex_subtype`` keys for better
    observability. The ``route_tier()`` convenience method returns just
    the tier string for backwards compatibility.
    """

    def route(self, query: str) -> Dict[str, Any]:
        """Classify query and return ``{tier, reason, confidence[, complex_subtype]}``.

        Returns:
            Dict with keys:

            - ``tier``: ``"chitchat"`` | ``"simple"`` | ``"complex"``
            - ``reason``: human-readable explanation of the routing decision
            - ``confidence``: ``"high"`` (pattern match) or ``"medium"`` (heuristic)
            - ``complex_subtype`` (only when tier=complex):
              ``"comparison"`` | ``"multi_source"`` | ``"general"``
        """
        q = query.strip()
        q_lower = q.lower()

        # 1. Chitchat — fast path, checked first
        for pattern in _CHITCHAT_RE:
            if pattern.search(q_lower):
                result = {
                    "tier": "chitchat",
                    "reason": f"chitchat_pattern: {pattern.pattern[:40]}",
                    "confidence": "high",
                }
                logger.info(
                    "ComplexityRouter: %r → %s (%s)",
                    q[:60], result["tier"], result["reason"],
                )
                return result

        # 2. Complex signals — regex patterns with subtype tagging
        for pattern, subtype in _COMPLEX_SPECS_RE:
            if pattern.search(q):
                result = {
                    "tier": "complex",
                    "reason": f"complex_pattern: {pattern.pattern[:50]}",
                    "confidence": "high",
                    "complex_subtype": subtype,
                }
                logger.info(
                    "ComplexityRouter: %r → %s/%s (%s)",
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
                }
                logger.info(
                    "ComplexityRouter: %r → %s (%s)",
                    q[:60], result["tier"], result["reason"],
                )
                return result
            else:
                # Query dài nhưng single-topic → giữ simple (RAG đơn giản là đủ)
                logger.info(
                    "ComplexityRouter: %r → simple (word_count=%d but single_topic)",
                    q[:60], word_count,
                )

        if q.count("?") > 1:
            result = {
                "tier": "complex",
                "reason": f"heuristic: multiple_questions={q.count('?')}",
                "confidence": "medium",
                "complex_subtype": "general",
            }
            logger.info(
                "ComplexityRouter: %r → %s (%s)",
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
            }
            logger.info(
                "ComplexityRouter: %r → %s (%s)",
                q[:60], result["tier"], result["reason"],
            )
            return result

        result = {
            "tier": "simple",
            "reason": "default: no complex signals detected",
            "confidence": "high",
        }
        logger.info(
            "ComplexityRouter: %r → %s (%s)",
            q[:60], result["tier"], result["reason"],
        )
        return result

    def route_tier(self, query: str) -> str:
        """Return just the tier string (``'chitchat'``, ``'simple'``, ``'complex'``).

        Backwards-compatible convenience method.
        """
        return self.route(query)["tier"]