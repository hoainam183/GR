"""Query Reflection — rewrite, clarify, format, and add context from history."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from config.settings import Settings

from openai import OpenAI, InternalServerError, RateLimitError

from .prompts import (
    REWRITE_NO_HISTORY_TEMPLATE,
    REWRITE_SYSTEM_PROMPT,
    REWRITE_WITH_HISTORY_TEMPLATE,
)

logger = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────────────────────────
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_HISTORY_LIMIT = 5
_MAX_RETRIES = 3
_BASE_RETRY_DELAY = 2.0  # seconds

_UNKNOWN_PROFILE_VALUES = {
    "",
    "none",
    "null",
    "unknown",
    "n/a",
    "na",
    "khong ro",
}

# Personal pronouns/possessives that indicate the query needs profile enrichment
_PERSONAL_REFS = re.compile(
    r"\b(của tôi|ngành học của tôi|ngành của tôi|ngành tôi|ngành này|"
    r"chương trình của tôi|chương trình này|môn này|môn đó|môn học này)\b",
    re.IGNORECASE,
)

# Course code regex (e.g. IT4062E, MI1110)
_COURSE_CODE_RE = re.compile(
    r"\b(?:IT|MI|EE|ET|ME|CH|PH|MA|TL|FL|PE|ED)\d{4}[A-Z]?\b",
    re.IGNORECASE,
)



def _merge_user_major_into_context(
    user_context: Optional[Dict[str, Any]],
    user_major: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Return a copied context with ``user_major`` injected when missing."""
    major = _clean_profile_value(user_major)
    if not user_context and not major:
        return None

    merged = dict(user_context or {})
    if major and not _clean_profile_value(merged.get("major")):
        merged["major"] = major
    return merged


def _enforce_major_reference_rewrite(
    rewritten_query: str,
    profile: Optional[Dict[str, str]],
) -> str:
    """Resolve unresolved major references using trusted profile data.

    If the LLM still returns references such as "ngành học của tôi" while a
    concrete major exists in profile, this function replaces those fragments so
    the final query remains standalone for retrieval.
    """
    if not rewritten_query or not profile:
        return rewritten_query

    major = profile.get("major")
    if not major:
        return rewritten_query

    major_label = major
    major_code = profile.get("major_code")
    if major_code and major_code not in major_label:
        major_label = f"{major_label} ({major_code})"

    updated = rewritten_query
    replacements = [
        (r"\bngành học của tôi\b", f"ngành {major_label}"),
        (r"\bngành của tôi\b", f"ngành {major_label}"),
        (r"\bngành tôi\b", f"ngành {major_label}"),
        (r"\bngành này\b", f"ngành {major_label}"),
        (r"\bchương trình học của tôi\b", f"chương trình đào tạo ngành {major_label}"),
        (r"\bchương trình của tôi\b", f"chương trình đào tạo ngành {major_label}"),
        (r"\bchương trình này\b", f"chương trình đào tạo ngành {major_label}"),
    ]
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)

    if updated != rewritten_query:
        logger.debug("Reflection fallback rewrite applied: %r -> %r", rewritten_query, updated)
    return updated


def _clean_profile_value(value: Any) -> Optional[str]:
    """Normalize profile values and discard unknown placeholders."""
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if cleaned.lower() in _UNKNOWN_PROFILE_VALUES:
        return None
    return cleaned


def _normalise_profile_context(
    profile: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Return a normalized profile dict with canonical keys.

    Canonical keys used by the reflector:
      - major
      - major_code
      - cohort
      - student_id
    """
    if not profile:
        return {}

    major = _clean_profile_value(
        profile.get("major")
        or profile.get("major_name")
        or profile.get("user_major")
    )
    major_code = _clean_profile_value(
        profile.get("major_code")
        or profile.get("user_major_code")
    )
    cohort = _clean_profile_value(
        profile.get("cohort")
        or profile.get("khoa")
    )
    student_id = _clean_profile_value(
        profile.get("student_id")
        or profile.get("user_id")
    )

    out: Dict[str, str] = {}
    if major:
        out["major"] = major
    if major_code:
        out["major_code"] = major_code
    if cohort:
        out["cohort"] = cohort
    if student_id:
        out["student_id"] = student_id
    return out


def _merge_profile_context(
    user_context: Optional[Dict[str, Any]],
    user_profile: Optional[Dict[str, Any] | str],
) -> tuple[Dict[str, str], Optional[str]]:
    """Merge profile inputs and return (profile_dict, profile_note_override).

    Priority:
      1. user_context
      2. user_profile (dict) overrides user_context per-key
      3. user_profile (str) is treated as explicit note for prompt injection
    """
    merged = _normalise_profile_context(user_context)

    if isinstance(user_profile, dict):
        merged.update(_normalise_profile_context(user_profile))

    note_override: Optional[str] = None
    if isinstance(user_profile, str):
        note_override = _clean_profile_value(user_profile)

    return merged, note_override


def _extract_profile_note_from_context(
    user_context: Optional[Dict[str, Any]],
) -> str:
    """Build a short profile note from an authenticated user_context dict.

    Returns a string like:
        "sinh viên ngành Công nghệ thông tin Việt-Nhật (IT-E6), Khóa K65"
    or empty string when user_context is None / empty.
    """
    profile = _normalise_profile_context(user_context)
    if not profile:
        return ""

    parts: List[str] = []
    if profile.get("major"):
        major_note = profile["major"]
        if profile.get("major_code"):
            major_note += f" ({profile['major_code']})"
        parts.append(f"ngành {major_note}")
    if profile.get("cohort"):
        parts.append(f"Khóa K{profile['cohort']}")
    if profile.get("student_id"):
        parts.append(f"Mã SV: {profile['student_id']}")

    return "sinh viên " + ", ".join(parts) if parts else ""


def _extract_profile_note(history: List[Dict[str, str]]) -> str:
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


def _extract_entities(
    query: str,
    user_context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Optional[str]]:
    """Extract structured entities from query + context (no LLM call).

    Priority for each entity:
            1. Explicit signals in current ``query`` — highest priority because the
                 latest turn can override profile defaults (e.g. "ngành IT-E7").
            2. ``user_context`` — authenticated login data.
            3. Conversation ``history`` — user-stated facts in the session.

    Returns a dict with keys (all values may be ``None``):
      - ``major_code``      — e.g. "IT-E6"
      - ``major_name``      — e.g. "Công nghệ thông tin Việt - Nhật"
      - ``cohort``          — e.g. "65"
      - ``year_of_study``   — e.g. "2"
      - ``course_code``     — e.g. "IT4062E"
      - ``semester``        — e.g. "1" or "2" or "he" (hè)
      - ``academic_year``   — e.g. "20241" (semester code) or "2024-2025"
    """
    # Late import to avoid circular dependency (retrieval → reflection).
    from retrieval.metadata_filters import (  # noqa: PLC0415
        MAJOR_CODE_TO_NAME,
        _extract_major_code,
    )

    entities: Dict[str, Optional[str]] = {
        "major_code": None,
        "major_name": None,
        "cohort": None,
        "year_of_study": None,
        "course_code": None,
        "semester": None,
        "academic_year": None,
    }

    profile = _normalise_profile_context(user_context)

    # ── major ─────────────────────────────────────────────────────────────────
    # Priority 1: explicit major in the current query should override profile.
    explicit_query_major = _extract_major_code(query)
    if explicit_query_major:
        entities["major_code"] = explicit_query_major
        entities["major_name"] = MAJOR_CODE_TO_NAME.get(explicit_query_major)
    elif profile:
        # Priority 2: authenticated profile.
        code = profile.get("major_code")
        name = profile.get("major")
        if code:
            entities["major_code"] = str(code)
            entities["major_name"] = MAJOR_CODE_TO_NAME.get(str(code), name)
        elif name:
            detected = _extract_major_code(str(name))
            entities["major_code"] = detected
            entities["major_name"] = str(name)

    if not entities["major_code"] and history:
        # Priority 3: user-stated session facts.
        for msg in reversed(history):        # most-recent first
            if msg.get("role") == "user":
                text = msg.get("content", "")
                code = _extract_major_code(text)
                if code:
                    entities["major_code"] = code
                    entities["major_name"] = MAJOR_CODE_TO_NAME.get(code)
                    break

    # ── cohort ────────────────────────────────────────────────────────────────
    _COHORT_RE = re.compile(r"\bk(\d{2,3})\b|kh\u00f3a\s*(\d{2,3})", re.IGNORECASE)
    if profile.get("cohort"):
        entities["cohort"] = profile["cohort"]
    else:
        sources = ([query] +
                   [m.get("content", "") for m in (history or [])
                    if m.get("role") == "user"])
        for text in sources:
            mo = _COHORT_RE.search(text)
            if mo:
                entities["cohort"] = next(g for g in mo.groups() if g)
                break

    # ── year_of_study ─────────────────────────────────────────────────────────
    _YEAR_RE = re.compile(
        r"(?:sinh\s*vi\u00ean\s*)?n\u0103m\s*th\u1ee9?\s*(\d)"
        r"|n\u0103m\s+(\d)\b",
        re.IGNORECASE,
    )
    sources = ([query] +
               [m.get("content", "") for m in (history or [])
                if m.get("role") == "user"])
    for text in sources:
        mo = _YEAR_RE.search(text)
        if mo:
            entities["year_of_study"] = next(g for g in mo.groups() if g)
            break

    # ── course_code ───────────────────────────────────────────────────────────
    # Priority: current query first, then history (most-recent user turn first).
    # This ensures follow-up queries like "Còn slot không?" resolve correctly
    # when the course was mentioned in a prior turn.
    course_sources = [query] + [
        m.get("content", "")
        for m in reversed(history or [])
        if m.get("role") == "user"
    ]
    for text in course_sources:
        mo = _COURSE_CODE_RE.search(text)
        if mo:
            entities["course_code"] = mo.group(0).upper()
            break

    # ── semester ──────────────────────────────────────────────────────────────
    # Captures:
    #   - Semester codes like "20241", "20242", "20243" (hè)
    #   - Vietnamese phrases: "học kỳ 1", "học kỳ 2", "học kỳ hè", "HK1", "HK2"
    #   - English: "semester 1", "semester 2"
    _SEMESTER_CODE_RE = re.compile(r"\b(20\d{2}[123])\b")
    _SEMESTER_NAME_RE = re.compile(
        r"(?:h\u1ecdc\s*k\u1ef3|hk|semester)\s*([12h\u00e8])",
        re.IGNORECASE,
    )
    _HE_RE = re.compile(r"k\u1ef3\s*h\u00e8|h\u1ecdc\s*k\u1ef3\s*h\u00e8", re.IGNORECASE)

    sem_sources = [query] + [
        m.get("content", "")
        for m in reversed(history or [])
        if m.get("role") in ("user", "assistant")
    ]
    for text in sem_sources:
        # Full semester code takes precedence (e.g. "20241")
        mo = _SEMESTER_CODE_RE.search(text)
        if mo:
            code = mo.group(1)
            entities["academic_year"] = code
            # Last digit: 1→HK1, 2→HK2, 3→HKhè
            sem_digit = code[-1]
            entities["semester"] = "he" if sem_digit == "3" else sem_digit
            break
        # hè keyword
        if _HE_RE.search(text):
            entities["semester"] = "he"
            break
        # "học kỳ 1 / HK2 / semester 2"
        mo = _SEMESTER_NAME_RE.search(text)
        if mo:
            val = mo.group(1).lower()
            entities["semester"] = "he" if val in ("h", "è") else val
            break

    # ── academic_year (YYYY-YYYY format) ──────────────────────────────────────
    # Only populate if not already set from semester code above.
    if not entities["academic_year"]:
        _AY_RE = re.compile(r"\b(20\d{2})\s*[-–]\s*(20\d{2})\b")
        ay_sources = [query] + [
            m.get("content", "")
            for m in reversed(history or [])
            if m.get("role") == "user"
        ]
        for text in ay_sources:
            mo = _AY_RE.search(text)
            if mo:
                entities["academic_year"] = f"{mo.group(1)}-{mo.group(2)}"
                break

    return entities


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
        self.max_tokens: int = getattr(settings, "reflection_max_tokens", 256)
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
        user_profile: Optional[Dict[str, Any] | str] = None,
        user_major: Optional[str] = None,
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
            user_profile: Optional profile payload for prompt injection.
                - dict: merged into ``user_context`` (overrides per-key)
                - str: used directly as profile note in the prompt
            user_major: Optional shorthand major name. Useful for callers that
                only have one field (e.g. ``"Công nghệ thông tin"``).

        Returns:
            Dict with ``{"original": str, "rewritten": str}``.
        """
        context_with_major = _merge_user_major_into_context(user_context, user_major)
        merged_profile, profile_note_override = _merge_profile_context(
            user_context=context_with_major,
            user_profile=user_profile,
        )

        user_prompt = self._build_user_prompt(
            query=query,
            chat_history=chat_history,
            user_context=merged_profile or None,
            profile_note_override=profile_note_override,
        )

        messages = [
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Retry with exponential backoff for rate-limit / 503 errors
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                break
            except (RateLimitError, InternalServerError) as exc:
                # Retry on 429 Rate-Limit and 503 Service Unavailable
                if isinstance(exc, InternalServerError) and exc.status_code != 503:
                    raise
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_RETRY_DELAY * (2**attempt)
                    logger.warning(
                        "Reflection transient error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
        else:
            raise last_exc  # type: ignore[misc]

        rewritten = response.choices[0].message.content.strip()

        # If the LLM returns empty or just whitespace, keep the original
        if not rewritten:
            rewritten = query

        # Guardrail 1: if user profile has a trusted major but references remain
        # unresolved, replace them deterministically.
        if _PERSONAL_REFS.search(rewritten):
            rewritten = _enforce_major_reference_rewrite(
                rewritten_query=rewritten,
                profile=merged_profile or None,
            )

        logger.info(
            "Reflection: %r → %r (history_len=%d)",
            query[:60],
            rewritten[:60],
            len(chat_history) if chat_history else 0,
        )

        entities = _extract_entities(
            query,
            user_context=merged_profile or None,
            history=chat_history,
        )
        logger.debug("Extracted entities: %s", entities)

        return {
            "original": query,
            "rewritten": rewritten,
            "prompt": user_prompt,
            "entities": entities,
        }

    def extract_entities(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        user_profile: Optional[Dict[str, Any] | str] = None,
        user_major: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """Public wrapper around :func:`_extract_entities` for external callers."""
        context_with_major = _merge_user_major_into_context(user_context, user_major)
        merged_profile, _ = _merge_profile_context(
            user_context=context_with_major,
            user_profile=user_profile,
        )
        return _extract_entities(
            query,
            user_context=merged_profile or None,
            history=chat_history,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        profile_note_override: Optional[str] = None,
    ) -> str:
        """Format the user prompt, optionally including chat history.

        Builds a compact profile note from authenticated user_context (priority)
        or falls back to extracting it from chat history.  The note is prepended
        so even a first-turn query like "ngành của tôi" can be resolved.
        """
        # Prefer explicit note > authenticated profile > history regex.
        profile_note = profile_note_override or _extract_profile_note_from_context(user_context)
        if not profile_note and chat_history:
            profile_note = _extract_profile_note(chat_history)
        profile_block = profile_note or "(khong co)"

        if chat_history:
            recent = chat_history[-self.history_limit :]
            history_text = "\n".join(
                f"{'Người dùng' if msg['role'] == 'user' else 'Trợ lý'}: {msg['content']}"
                for msg in recent
                if msg.get("content")
            )
            return REWRITE_WITH_HISTORY_TEMPLATE.format(
                user_profile=profile_block,
                chat_history=history_text or "(khong co)",
                query=query,
            )
        return REWRITE_NO_HISTORY_TEMPLATE.format(
            user_profile=profile_block,
            chat_history="(khong co)",
            query=query,
        )