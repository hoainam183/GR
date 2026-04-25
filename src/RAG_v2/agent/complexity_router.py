from __future__ import annotations

import re

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
    r"\bK\d{2,3}\b.{1,50}\bK\d{2,3}\b",

    # Two programme codes mentioned (IT-E6 … IT-E7, MI-E10 ...)
    r"\b(?:IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH)-[A-Z0-9]+\b.{1,50}\b(?:IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH)-[A-Z0-9]+\b",

    # Difference / similarity ONLY when paired with cohort / programme context
    r"(khác nhau|khác biệt|giống nhau).{0,40}(K\d{2}|khóa|ngành|chương trình|học kỳ|quy định)",
    r"(K\d{2}|khóa|ngành|chương trình).{0,40}(khác nhau|khác biệt|giống nhau)",

    # Multi-source eligibility queries
    r"\bđủ\s+điều\s+kiện\b",
    r"\bcó\s+thể\b.{0,20}\b(tốt nghiệp|đăng ký|xét duyệt|nhận học bổng)\b",
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
    """

    def route(self, query: str) -> str:
        """Return ``'chitchat'``, ``'simple'``, or ``'complex'``."""
        q = query.strip()
        q_lower = q.lower()

        # 1. Chitchat — fast path, checked first
        for pattern in _CHITCHAT_RE:
            if pattern.search(q_lower):
                return "chitchat"

        # 2. Complex signals
        for pattern in _COMPLEX_RE:
            if pattern.search(q):
                return "complex"

        # 3. Structural heuristics — applied after pattern checks to reduce
        #    false positives from the broad word-count rule
        word_count = len(q.split())
        if word_count > 30:
            return "complex"
        if q.count("?") > 1:
            return "complex"
        # Three or more conjunctions suggest a compound multi-part question
        if q_lower.count(" và ") >= 3:
            return "complex"

        return "simple"