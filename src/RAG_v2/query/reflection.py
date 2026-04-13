"""Query Reflection — rewrite, clarify, format, and add context from history."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from config.settings import Settings

from openai import OpenAI, RateLimitError

from .prompts import (
    REWRITE_NO_HISTORY_TEMPLATE,
    REWRITE_SYSTEM_PROMPT,
    REWRITE_WITH_HISTORY_TEMPLATE,
)

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_HISTORY_LIMIT = 5
_MAX_RETRIES = 3
_BASE_RETRY_DELAY = 2.0  # seconds

# Personal pronouns/possessives that indicate the query needs profile enrichment
_PERSONAL_REFS = re.compile(
    r"\b(c(?:ủa|ủa tôi|húng tôi)|ng(?:ành|ành tôi)|ch(?:ương trình|ương trình tôi)"
    r"|kh(?:óa|óa tôi)|t(?:ôi|ôi đang)|mình)\b",
    re.IGNORECASE,
)


def _extract_profile_note_from_context(
    user_context: Optional[Dict[str, Any]],
) -> str:
    """Build a short profile note from an authenticated user_context dict.

    Returns a string like:
        "sinh viên ngành Công nghệ thông tin Việt-Nhật (IT-E6), Khóa K65"
    or empty string when user_context is None / empty.
    """
    if not user_context:
        return ""

    parts: List[str] = []
    if user_context.get("major"):
        major_note = str(user_context["major"])
        if user_context.get("major_code"):
            major_note += f" ({user_context['major_code']})"
        parts.append(f"ngành {major_note}")
    if user_context.get("cohort"):
        parts.append(f"Khóa K{user_context['cohort']}")
    if user_context.get("student_id"):
        parts.append(f"Mã SV: {user_context['student_id']}")

    return "sinh viên " + ", ".join(parts) if parts else ""



    """Scan conversation history for user-stated facts (major, year, GPA/CPA).

    Returns a short Vietnamese note like:
        "sinh viên ngành Công nghệ thông tin Việt-Nhật, năm 2, CPA=3.1"
    or empty string when nothing is found.
    """
    if not history:
        return ""

    profile: Dict[str, str] = {}
    user_messages = [
        m.get("content", "") for m in history
        if m.get("role") == "user" and m.get("content")
    ]

    for text in user_messages:
        t = text.lower()

        # Major / programme name
        if not profile.get("nganh"):
            # Pattern: "học ngành X", "ngành X", "chuyên ngành X"
            m = re.search(
                r"(?:h\u1ecdc ng\u00e0nh|ng\u00e0nh|chuy\u00ean ng\u00e0nh)\s+"
                r"([^\.,\n\?!]{3,50})",
                text,
                re.IGNORECASE,
            )
            if m:
                profile["nganh"] = m.group(1).strip().rstrip(".,!?")

        # Year of study
        if not profile.get("nam"):
            m = re.search(
                r"(?:sinh vi\u00ean n\u0103m|n\u0103m\s+th\u1ee9|n\u0103m)\s*(\d)"
                r"|(\d)\s*n\u0103m",
                t,
            )
            if m:
                profile["nam"] = next(g for g in m.groups() if g)

        # Cohort / Khóa
        if not profile.get("khoa"):
            m = re.search(r"\bk(\d{2,3})\b|kh\u00f3a\s*(\d{2,3})", t)
            if m:
                profile["khoa"] = next(g for g in m.groups() if g)

        # GPA / CPA
        if not profile.get("gpa"):
            m = re.search(
                r"\b(?:cpa|gpa)\s*(?:l\u00e0|=|:)?\s*(\d+[.,]\d+)\b", t
            )
            if m:
                profile["gpa"] = m.group(1).replace(",", ".")

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

    return "sinh vi\u00ean " + ", ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
class QueryReflector:
    """Rewrites and enriches a user query before it enters the retrieval pipeline.

    Responsibilities:
        1. **Rewrite** — make the query clear and self-contained.
        2. **Clarify** — resolve vague references using chat history.
        3. **Format** — normalise the query for embedding search.
        4. **Add context** — incorporate relevant chat history.

    All four steps are collapsed into a single LLM call that receives
    the raw query (and optionally recent chat history) and returns an
    improved version.

    Parameters:
        api_key: Google API key for Gemini. If *None*, reads from
            ``GOOGLE_API_KEY`` env var.
        model: Gemini model identifier used for query rewriting.
        temperature: Sampling temperature.
        history_limit: Maximum number of recent history messages to include.
    """

    def __init__(
        self,
        settings: Optional["Settings"] = None,
        api_key: Optional[str] = None,  # For backwards compatibility if any
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        if settings is None:
            from config.settings import Settings
            settings = Settings()

        self.model = model or settings.reflection_model
        self.temperature = temperature if temperature is not None else settings.reflection_temperature
        self.history_limit = history_limit
        
        provider = settings.reflection_provider
        
        # Setup OpenAI client parameters based on provider
        if provider == "gemini":
            base_url = _GEMINI_BASE_URL
            resolved_key = api_key or settings.google_api_key or os.getenv("GOOGLE_API_KEY", "")
        elif provider == "lm_studio":
            base_url = settings.lm_studio_base_url
            resolved_key = api_key or "lm-studio"
        elif provider == "ollama":
            # For Ollama OpenAI compatibility we append /v1 if missing
            _base = settings.ollama_base_url
            base_url = _base if _base.endswith("/v1") else f"{_base}/v1"
            resolved_key = api_key or "ollama"
        elif provider == "openai":
            base_url = "https://api.openai.com/v1"
            resolved_key = api_key or settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        else:
            base_url = _GEMINI_BASE_URL
            resolved_key = api_key or settings.google_api_key or os.getenv("GOOGLE_API_KEY", "")
            
        self._client = OpenAI(api_key=resolved_key, base_url=base_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reflect(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Rewrite *query* into a retrieval-optimised form.

        Args:
            query: The raw user message.
            chat_history: Recent conversation messages, each a dict with
                ``"role"`` (``"user"``/``"assistant"``) and ``"content"`` keys.
            user_context: Authenticated user profile dict (major, major_code,
                cohort, student_id).  When provided it takes priority over
                profile facts extracted from history, ensuring that first-turn
                queries like "ôn thi ngành của tôi" resolve correctly.

        Returns:
            Dict with ``{"original": str, "rewritten": str}``.
        """
        user_prompt = self._build_user_prompt(query, chat_history, user_context)

        messages = [
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Retry with exponential backoff for rate-limit errors
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=256,
                )
                break
            except RateLimitError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_RETRY_DELAY * (2**attempt)
                    logger.warning(
                        "Reflection rate-limited (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
        else:
            raise last_exc  # type: ignore[misc]

        rewritten = response.choices[0].message.content.strip()

        # If the LLM returns empty or just whitespace, keep the original
        if not rewritten:
            rewritten = query

        logger.info(
            "Reflection: %r → %r (history_len=%d)",
            query[:60],
            rewritten[:60],
            len(chat_history) if chat_history else 0,
        )

        return {"original": query, "rewritten": rewritten, "prompt": user_prompt}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format the user prompt, optionally including chat history.

        Builds a compact profile note from authenticated user_context (priority)
        or falls back to extracting it from chat history.  The note is prepended
        so even a first-turn query like "ngành của tôi" can be resolved.
        """
        # Prefer authenticated profile (exact code+name) over history regex.
        profile_note = _extract_profile_note_from_context(user_context)
        if not profile_note and chat_history:
            profile_note = _extract_profile_note(chat_history)

        if chat_history:
            recent = chat_history[-self.history_limit :]
            history_text = "\n".join(
                f"{'Người dùng' if msg['role'] == 'user' else 'Trợ lý'}: {msg['content']}"
                for msg in recent
                if msg.get("content")
            )
            if profile_note:
                history_text = f"[Thông tin đã biết: {profile_note}]\n" + history_text
            return REWRITE_WITH_HISTORY_TEMPLATE.format(
                history=history_text, query=query
            )
        # No history — still inject profile so the model can resolve pronouns.
        if profile_note:
            return REWRITE_WITH_HISTORY_TEMPLATE.format(
                history=f"[Thông tin đã biết: {profile_note}]",
                query=query,
            )
        return REWRITE_NO_HISTORY_TEMPLATE.format(query=query)
