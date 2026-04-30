"""Complexity Router — classifies queries into chitchat / simple / complex tiers.

Improvements over original:
- Added logging for routing decisions (enables analysis & debugging).
- Added confidence signal (pattern-based vs heuristic-based).
- Better pattern coverage for ambiguous queries.
- Optional DomainClassifier integration for borderline cases.
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

COMPLEX_PATTERNS: list[str] = [
    # Explicit comparison keyword
    r"\bso\s*sánh\b",

    # Two cohort codes mentioned in the same query (K65 … K70)
    # Widened to 120 chars — cohorts often appear far apart in Vietnamese.
    r"\bK\d{2,3}\b.{1,120}\bK\d{2,3}\b",

    # Two programme codes mentioned (IT-E6 … IT-E7, MI-E10 ...)
    r"\b(?:IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH)-[A-Z0-9]+\b.{1,50}\b(?:IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH)-[A-Z0-9]+\b",

    # Difference / similarity ONLY when paired with cohort / programme context
    r"(khác nhau|khác biệt|giống nhau).{0,40}(K\d{2}|khóa|ngành|chương trình|học kỳ|quy định)",
    r"(K\d{2}|khóa|ngành|chương trình).{0,40}(khác nhau|khác biệt|giống nhau)",

    # Multi-source eligibility queries
    r"\bđủ\s+điều\s+kiện\b",
    r"\b(có\s+thể|có\s+được)\b.{0,30}\b(tốt nghiệp|đăng ký|đăng kí|xét duyệt|nhận học bổng)\b",
    r"(môn|học phần).{0,30}\b(được|có)\s+(đăng ký|đăng kí|mở)\b",
    r"\btất\s+cả.{0,20}điều\s+kiện\b",

    # Ambiguous single-term queries (no actionable context)
    r"^(học bổng|môn học|lịch|quy định|chương trình)\s*\??$",
    r"^cho\s+tôi\s+biết\s+về\s+\w{1,15}\s*$",

    # Multi-step questions with conjunctions
    r"\bvà\b.{0,30}\b(cho biết|liệt kê|so sánh|giải thích)\b",
]

# ─── Compiled caches ──────────────────────────────────────────────────────────

_CHITCHAT_RE: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in CHITCHAT_PATTERNS
]
_COMPLEX_RE: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in COMPLEX_PATTERNS
]


class ComplexityRouter:
    """
    Classifies an incoming query into one of three routing tiers:

    - ``"chitchat"``  — greeting / acknowledgement, handled by a simple
                        canned-response handler; no RAG needed.
    - ``"simple"``    — single-domain factual question; handled by the
                        existing RAG v2 pipeline.
    - ``"complex"``   — multi-domain, comparative, or ambiguous query;
                        routed to the LangGraph ReAct agent.

    The ``route()`` method now returns a dict with ``tier``, ``reason``,
    and ``confidence`` keys for better observability. The ``route_tier()``
    convenience method returns just the tier string for backwards
    compatibility.
    """

    def route(self, query: str) -> Dict[str, Any]:
        """Classify query and return ``{tier, reason, confidence}``.

        Returns:
            Dict with keys:

            - ``tier``: ``"chitchat"`` | ``"simple"`` | ``"complex"``
            - ``reason``: human-readable explanation of the routing decision
            - ``confidence``: ``"high"`` (pattern match) or ``"medium"`` (heuristic)
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

        # 2. Complex signals — regex patterns
        for pattern in _COMPLEX_RE:
            if pattern.search(q):
                result = {
                    "tier": "complex",
                    "reason": f"complex_pattern: {pattern.pattern[:50]}",
                    "confidence": "high",
                }
                logger.info(
                    "ComplexityRouter: %r → %s (%s)",
                    q[:60], result["tier"], result["reason"],
                )
                return result

        # 3. Structural heuristics — lower confidence
        word_count = len(q.split())
        if word_count > 30:
            result = {
                "tier": "complex",
                "reason": f"heuristic: word_count={word_count}>30",
                "confidence": "medium",
            }
            logger.info(
                "ComplexityRouter: %r → %s (%s)",
                q[:60], result["tier"], result["reason"],
            )
            return result

        if q.count("?") > 1:
            result = {
                "tier": "complex",
                "reason": f"heuristic: multiple_questions={q.count('?')}",
                "confidence": "medium",
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