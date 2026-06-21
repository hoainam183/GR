"""Query Reflection — rewrite, clarify, format, and add context from history."""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

if TYPE_CHECKING:
    from config.settings import Settings

from openai import OpenAI, InternalServerError, RateLimitError

from .prompts import (
    REWRITE_NO_HISTORY_TEMPLATE,
    REWRITE_SYSTEM_PROMPT,
    REWRITE_WITH_HISTORY_TEMPLATE,
)
from .structured_query import COURSE_CODE_PREFIXES as _COURSE_CODE_PREFIXES
from utils.terminology import expand_academic_abbreviations

logger = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────────────────────────
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
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

# Course code regex (e.g. IT4062E, MI1110, JP2111). The prefix list is shared
# with ``query.structured_query`` (imported above) so the two never drift apart —
# reflection used to define a narrower list (no JP|EM|BF|TEX, no separator) and
# silently fail to recognise those codes, leaving entity extraction / course-code
# preservation wrong for them.
_COURSE_CODE_RE = re.compile(
    rf"\b(?:{_COURSE_CODE_PREFIXES})\s*-?\s*\d{{4}}[A-Z]?\b",
    re.IGNORECASE,
)
_ADJACENT_COURSE_CODE_RE = re.compile(
    rf"\s*\(\s*((?:{_COURSE_CODE_PREFIXES})\s*-?\s*\d{{4}}[A-Z]?)\s*\)",
    re.IGNORECASE,
)
_PROFILE_DEPENDENT_QUERY_RE = re.compile(
    r"\b(?:"
    r"(?:nganh|chuong\s*trinh|khoa|nam\s*thu|cpa|gpa|"
    r"ma\s*(?:sv|sinh\s*vien)|mssv|thong\s*tin)"
    r"\s+(?:hoc\s+)?(?:cua\s+)?(?:toi|minh|em)|"
    r"(?:toi|minh|em)\s+(?:hoc|dang\s+hoc|thuoc|la\s+sinh\s+vien)|"
    r"(?:nganh|khoa)\s+(?:toi|minh|em)"
    r")\b",
    re.IGNORECASE,
)

_COMPARISON_FOLLOWUP_RE = re.compile(
    r"^\s*(?:so\s*(?:sánh)?\s*(?:với|về)?|khác\s+(?:gì|nhau)|vs)\b",
    re.IGNORECASE,
)

# Freshness-intent signals (unaccented / folded form) — used to detect generic
# freshness queries that should NOT inherit academic scope from history.
_REFLECTION_FRESHNESS_ONLY_RE = re.compile(
    r"\b(?:moi\s*nhat|gan\s*day|hien\s*tai|ky\s*nay|ki\s*nay|"
    r"hoc\s*ky\s*moi|hoc\s*ki\s*moi|latest|recent|newest)\b",
    re.IGNORECASE,
)

# Anaphora signals — references to something from prior context.
# Presence means history IS needed to resolve the reference.
_ANAPHORA_SIGNALS_RE = re.compile(
    r"\b(?:đó|này|kia|ấy|vậy|còn|thêm|nữa)\b",
    re.IGNORECASE,
)

_TOPIC_HINTS: tuple[tuple[str, str], ...] = (
    (r"\bhoc\s+phi\b", "học phí"),
    (r"\bmuc\s+hoc\s+phi\b", "học phí"),
    (r"\bngoai\s+ngu\b|\btieng\s+anh\b|\bforeign\s+language\b", "ngoại ngữ"),
    (r"\btin\s+chi\b|\bcredits?\b", "tín chỉ"),
    (r"\bhoc\s+bong\b", "học bổng"),
    (r"\btot\s+nghiep\b", "điều kiện tốt nghiệp"),
    (r"\bchuong\s+trinh\b", "chương trình đào tạo"),
)

# ── PII & conversational noise stripping ────────────────────────────────────────
# Student ID patterns: "mssv 20214987", "MSSV: 20214987", "mã sv 20214987"
_MSSV_RE = re.compile(
    r"\b(?:mssv|msv|mã\s+sinh\s+viên|ms\.?\s*sv|student\s*id)\s*[:\.\-]?\s*\d{6,12}\b",
    re.IGNORECASE,
)
# Personal introduction: "Em là Phạm Nhật Anh", "Tôi là X Y Z"
# Matches 1–5 capitalised Vietnamese name tokens after "là"
# The lead-in (pronoun + "là") is case-insensitive, but the name tokens must
# stay capital-initial: requiring an uppercase first letter is what distinguishes
# a real proper-noun introduction ("Tôi là Phạm Nhật Anh") from an ordinary
# question ("học phí của tôi là bao nhiêu"). A global re.IGNORECASE would make the
# uppercase classes match lowercase too and wrongly strip the latter to "học phí của".
_PERSONAL_INTRO_RE = re.compile(
    r"(?i:\b(?:em|tôi|mình)\s+là\s+)"
    r"(?:[A-ZÀÁẠẢÃĂẮẰẶẲẴÂẤẦẬẨẪĐÈÉẸẺẼÊẾỀỆỂỄÌÍỊỈĨÒÓỌỎÕÔỐỒỘỔỖƠỚỜỢỞỠÙÚỤỦŨƯỨỪỰỬỮỲÝỴỶỸ]"
    r"[a-zàáạảãăắằặẳẵâấầậẩẫđèéẹẻẽêếềệểễìíịỉĩòóọỏõôốồộổỗơớờợởỡùúụủũưứừựửữỳýỵỷỹ]{0,20}"
    r"(?:\s+[A-ZÀÁẠẢÃĂẮẰẶẲẴÂẤẦẬẨẪĐÈÉẸẺẼÊẾỀỆỂỄÌÍỊỈĨÒÓỌỎÕÔỐỒỘỔỖƠỚỜỢỞỠÙÚỤỦŨƯỨỪỰỬỮỲÝỴỶỸ]"
    r"[a-zàáạảãăắằặẳẵâấầậẩẫđèéẹẻẽêếềệểễìíịỉĩòóọỏõôốồộổỗơớờợởỡùúụủũưứừựửữỳýỵỷỹ]{0,20}){0,4})",
)
# Thanks / closing: "em xin cảm ơn", "Cảm ơn ban cố vấn a"
_THANKS_RE = re.compile(
    r"(?:em|tôi|mình)?\s*(?:xin\s+)?cảm\s+ơn[^.!?]{0,80}[.!]?",
    re.IGNORECASE,
)
# Addressee noise: "Ban cố vấn a.", "Kính gửi thầy cô"
_ADDRESSEE_RE = re.compile(
    r"\b(?:ban\s+cố\s+vấn|kính\s+gửi(?:\s+(?:thầy|cô|ban))?|ban\s+quản\s+lý)[^.!?]{0,30}[.!]?",
    re.IGNORECASE,
)


def _strip_pii_and_noise(query: str) -> str:
    """Remove PII and conversational noise from a query before reflection/retrieval.

    Strips student IDs, personal name introductions, closing/thanks phrases, and
    addressee fragments.  The core academic question is preserved.  If stripping
    reduces the result to fewer than 3 words the original query is returned
    unchanged to avoid destroying short queries.
    """
    cleaned = query
    cleaned = _MSSV_RE.sub("", cleaned)
    cleaned = _PERSONAL_INTRO_RE.sub("", cleaned)
    cleaned = _THANKS_RE.sub("", cleaned)
    cleaned = _ADDRESSEE_RE.sub("", cleaned)
    # Normalise whitespace and stray leading punctuation
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip(
        " \t\n\r\u2013\u2014\u002d.,–—"
    )
    # Guard: if too much was stripped, keep original
    if len(cleaned.split()) < 3:
        logger.debug(
            "PII strip produced too-short result; keeping original: %r",
            query[:80],
        )
        return query
    if cleaned != query:
        logger.info("PII strip: %r → %r", query[:80], cleaned[:80])
    return cleaned


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
        (
            r"\bchương trình học của tôi\b",
            f"chương trình đào tạo ngành {major_label}",
        ),
        (
            r"\bchương trình của tôi\b",
            f"chương trình đào tạo ngành {major_label}",
        ),
        (r"\bchương trình này\b", f"chương trình đào tạo ngành {major_label}"),
    ]
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)

    if updated != rewritten_query:
        logger.debug(
            "Reflection fallback rewrite applied: %r -> %r",
            rewritten_query,
            updated,
        )
    return updated


def _fold_vietnamese(text: str) -> str:
    """Return lowercase, accent-insensitive text for lightweight matching."""
    decomposed = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return without_marks.replace("đ", "d").replace("Đ", "D").casefold()


def _has_profile_dependent_signal(query: str) -> bool:
    """Return True when the current query explicitly asks for profile context."""
    if _PERSONAL_REFS.search(query or ""):
        return True
    return bool(
        _PROFILE_DEPENDENT_QUERY_RE.search(_fold_vietnamese(query or ""))
    )



def _is_comparison_followup(query: str) -> bool:
    """Detect short comparison follow-ups that need topic inheritance."""
    raw = (query or "").strip()
    if not raw or not _COMPARISON_FOLLOWUP_RE.search(raw):
        return False

    try:
        from retrieval.metadata_filters import (
            extract_major_codes,
        )  # noqa: PLC0415

        explicit_major_count = len(extract_major_codes(raw))
    except Exception:
        explicit_major_count = 0

    return (
        len(raw.split()) <= 8
        or explicit_major_count < 2
        or bool(_PERSONAL_REFS.search(raw))
    )


def _extract_topic_hint(text: str) -> Optional[str]:
    """Extract a compact academic topic from one query/history message."""
    folded = _fold_vietnamese(text)
    for pattern, label in _TOPIC_HINTS:
        if re.search(pattern, folded):
            return label
    return None


def _comparison_followup_topic(
    query: str,
    chat_history: Optional[List[Dict[str, str]]],
) -> Optional[str]:
    """Resolve the topic for a short comparison follow-up.

    Current-query topic wins (e.g. "so về học phí").  Otherwise use the most
    recent user message with a concrete academic topic, not assistant text, so a
    bad previous answer cannot steer the next retrieval topic.
    """
    topic = _extract_topic_hint(query)
    if topic:
        return topic

    for msg in reversed(chat_history or []):
        if msg.get("role") != "user":
            continue
        topic = _extract_topic_hint(msg.get("content", ""))
        if topic:
            return topic
    return None


def _add_unique_major_code(codes: List[str], value: Optional[str]) -> None:
    if not value:
        return
    code = str(value).strip().upper()
    if code and code not in codes:
        codes.append(code)


def _comparison_followup_major_codes(
    query: str,
    chat_history: Optional[List[Dict[str, str]]],
    profile: Optional[Dict[str, str]],
) -> List[str]:
    """Collect comparison sides from history/current query/profile."""
    from retrieval.metadata_filters import extract_major_codes  # noqa: PLC0415

    codes: List[str] = []
    current_codes = extract_major_codes(query)
    if len(current_codes) >= 2:
        for code in current_codes:
            _add_unique_major_code(codes, code)
        return codes[:2]

    # Previous concrete subject first: "ME-GU có học phí..." then "so với...".
    for msg in reversed(chat_history or []):
        if msg.get("role") != "user":
            continue
        for code in extract_major_codes(msg.get("content", "")):
            _add_unique_major_code(codes, code)
        if len(codes) >= 2:
            return codes[:2]

    # Current explicit comparison target: "so sánh với IT-E7".
    for code in current_codes:
        _add_unique_major_code(codes, code)
    if len(codes) >= 2:
        return codes[:2]

    # Authenticated profile resolves "ngành của tôi" and short comparison
    # follow-ups such as "so về học phí" after a previous comparison request.
    if profile:
        for profile_value in (profile.get("major_code"), profile.get("major")):
            for code in extract_major_codes(str(profile_value or "")):
                _add_unique_major_code(codes, code)
        _add_unique_major_code(codes, profile.get("major_code"))
    if len(codes) >= 2:
        return codes[:2]

    # Last resort: assistant text may contain the resolved pair from the prior
    # answer.  Use it only after user/history/profile signals are insufficient.
    for msg in reversed(chat_history or []):
        if msg.get("role") != "assistant":
            continue
        for code in extract_major_codes(msg.get("content", "")):
            _add_unique_major_code(codes, code)
        if len(codes) >= 2:
            return codes[:2]

    return codes


def _rewrite_comparison_followup(
    query: str,
    chat_history: Optional[List[Dict[str, str]]],
    profile: Optional[Dict[str, str]],
) -> Optional[str]:
    """Build a deterministic standalone query for short comparison follow-ups."""
    if not _is_comparison_followup(query):
        return None

    topic = _comparison_followup_topic(query, chat_history)
    if not topic:
        return None

    try:
        major_codes = _comparison_followup_major_codes(
            query, chat_history, profile
        )
    except Exception:
        logger.debug(
            "Could not resolve comparison follow-up entities", exc_info=True
        )
        return None

    if len(major_codes) < 2:
        return None

    return f"So sánh {topic} giữa {major_codes[0]} và {major_codes[1]}"


_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


def _expand_major_codes_in_query(query: str) -> str:
    """Deterministically expand major codes/names to paired references.

    E.g. ``"So sánh học phí giữa IT-E6 và IT1"``
    →    ``"So sánh học phí giữa IT-E6 (Công nghệ thông tin Việt - Nhật) và IT1 (Khoa học máy tính)"``

    Expansion uses the authoritative major mapping — no LLM involved. It also
    handles the reverse direction, e.g. ``"Khoa học máy tính"`` -> ``"Khoa học
    máy tính (IT1)"``.
    """
    try:
        from retrieval.metadata_filters import enrich_major_references_for_query  # noqa: PLC0415
    except Exception:
        return query

    result = enrich_major_references_for_query(query)
    if result != query:
        logger.debug("Major reference expansion: %r → %r", query[:80], result[:80])
    return result


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
        profile.get("major_code") or profile.get("user_major_code")
    )
    cohort = _clean_profile_value(profile.get("cohort") or profile.get("khoa"))
    student_id = _clean_profile_value(
        profile.get("student_id") or profile.get("user_id")
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
        m.get("content", "")
        for m in history
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


def _apply_catalog_course_match(
    entities: Dict[str, Optional[str]],
    query_text: str,
) -> bool:
    """Populate course fields from the major-scoped catalog when unique."""
    major_code = entities.get("major_code")
    if not major_code:
        return False

    from query.course_catalog import lookup_course_code  # noqa: PLC0415

    match = lookup_course_code(query_text, major_code)
    if not match:
        return False

    entities["course_code"] = match.get("code")
    entities["course_name"] = match.get("name")
    entities["course_name_folded"] = match.get("name_folded")
    entities["course_alias_folded"] = match.get("matched_alias_folded")
    return bool(entities["course_code"])


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
        # WHO the user IS — authenticated profile only, never overridden by the
        # query/history (so a stray "em học Cơ điện tử" cannot rewrite it).
        "user_major_code": None,
        "user_major_name": None,
        # WHAT major the question is ABOUT — explicit major named in the current
        # query (e.g. "ngành IT-E7"). None when the query names no target major.
        "target_major_code": None,
        "target_major_name": None,
        "cohort": None,
        "year_of_study": None,
        "course_code": None,
        "course_name": None,        # display name of a catalog-matched course
        "course_name_folded": None, # accent-folded name, used to locate it in text
        "course_alias_folded": None, # matched shorthand alias, when different
        "semester": None,
        "academic_year": None,
    }

    profile = _normalise_profile_context(user_context)

    # ── major ─────────────────────────────────────────────────────────────────
    # Distinguish WHO the user is (``user_major_*`` — auth profile only, immutable)
    # from WHAT major the question is about (``target_major_*`` — current query).
    # ``major_code``/``major_name`` keep the historical resolved value and
    # precedence (query → profile → history) for backward compatibility.
    #
    # user_major_* — authenticated profile ONLY. Never sourced from query/history,
    # so a conversational "em học Cơ điện tử" cannot override the real major.
    if profile:
        code = profile.get("major_code")
        name = profile.get("major")
        if code:
            entities["user_major_code"] = str(code)
            entities["user_major_name"] = MAJOR_CODE_TO_NAME.get(str(code), name)
        elif name:
            entities["user_major_code"] = _extract_major_code(str(name))
            entities["user_major_name"] = str(name)

    # target_major_* — explicit major named in the CURRENT query (e.g. "ngành IT-E7").
    explicit_query_major = _extract_major_code(query)
    if explicit_query_major:
        entities["target_major_code"] = explicit_query_major
        entities["target_major_name"] = MAJOR_CODE_TO_NAME.get(explicit_query_major)

    # Priority 1: explicit major in the current query should override profile.
    if explicit_query_major:
        entities["major_code"] = explicit_query_major
        entities["major_name"] = MAJOR_CODE_TO_NAME.get(explicit_query_major)
    elif profile:
        # Priority 2: authenticated profile.
        entities["major_code"] = entities["user_major_code"]
        entities["major_name"] = entities["user_major_name"]

    if not entities["major_code"] and history:
        # Priority 3: user-stated session facts.
        for msg in reversed(history):  # most-recent first
            if msg.get("role") == "user":
                text = msg.get("content", "")
                code = _extract_major_code(text)
                if code:
                    entities["major_code"] = code
                    entities["major_name"] = MAJOR_CODE_TO_NAME.get(code)
                    break

    # ── cohort ────────────────────────────────────────────────────────────────
    _COHORT_RE = re.compile(
        r"\bk(\d{2,3})\b|kh\u00f3a\s*(\d{2,3})", re.IGNORECASE
    )
    if profile.get("cohort"):
        entities["cohort"] = profile["cohort"]
    else:
        sources = [query] + [
            m.get("content", "")
            for m in (history or [])
            if m.get("role") == "user"
        ]
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
    sources = [query] + [
        m.get("content", "") for m in (history or []) if m.get("role") == "user"
    ]
    for text in sources:
        mo = _YEAR_RE.search(text)
        if mo:
            entities["year_of_study"] = next(g for g in mo.groups() if g)
            break

    # ── course_code ───────────────────────────────────────────────────────────
    # Priority:
    #   1. Explicit code in the current query.
    #   2. Course name/alias in the current query, scoped by major.
    #   3. History code fallback for short follow-ups such as "Còn slot không?".
    mo = _COURSE_CODE_RE.search(query)
    if mo:
        entities["course_code"] = mo.group(0).upper()
    elif not _apply_catalog_course_match(entities, query):
        for msg in reversed(history or []):
            if msg.get("role") != "user":
                continue
            mo = _COURSE_CODE_RE.search(msg.get("content", ""))
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
    _HE_RE = re.compile(
        r"k\u1ef3\s*h\u00e8|h\u1ecdc\s*k\u1ef3\s*h\u00e8", re.IGNORECASE
    )

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


_REGISTER_VERB_RE = re.compile(r"đăng\s*k[ýyíi]", re.IGNORECASE)
_FOLDED_REGISTER_RE = re.compile(r"\bdang\s*k[yi]\b")


def _preserve_curriculum_placement_verb(original: str, rewritten: str) -> str:
    """Revert reflection that flips a curriculum-placement question into a
    registration-timing one.

    Observed failure: ``"môn X được HỌC vào kỳ mấy"`` + history containing a
    course code → the reflector rewrote it to ``"…được ĐĂNG KÝ vào học kỳ mấy"``,
    silently changing WHICH-semester-in-curriculum (ctdt) intent into
    WHEN-registration (kehoach). That drift violates the "keep original meaning"
    rule and steers retrieval/rerank toward schedule docs.

    Rule (deterministic, narrow): only when the ORIGINAL query asks which
    semester a course sits in (``curriculum_semester_intent``) AND the user did
    NOT themselves write "đăng ký", strip any reflection-introduced "đăng ký"
    verb back to "học". If the user genuinely wrote "đăng ký", leave it alone.
    """
    from .signals import analyze_query_signals, fold_vietnamese_text  # local import

    if not analyze_query_signals(original).curriculum_semester_intent:
        return rewritten
    if _FOLDED_REGISTER_RE.search(fold_vietnamese_text(original)):
        return rewritten  # user said "đăng ký" themselves → honour it
    if not _REGISTER_VERB_RE.search(rewritten):
        return rewritten
    return _REGISTER_VERB_RE.sub("học", rewritten)


def _fold_char(ch: str) -> str:
    """Accent-fold a single char consistently with ``fold_vietnamese_text``."""
    decomposed = unicodedata.normalize("NFD", ch)
    base = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    base = base.replace("đ", "d").replace("Đ", "D")
    return base.casefold()


def _fold_with_index_map(text: str) -> tuple[str, List[int]]:
    """Return (folded_text, src_index) where src_index[k] is the original index
    of the original character that produced folded char k.

    Lets us locate a folded course name inside ``text`` and map the match back to
    original-string offsets for an in-place insertion.
    """
    folded_parts: List[str] = []
    src_index: List[int] = []
    for i, ch in enumerate(text):
        folded = _fold_char(ch)
        for fc in folded:
            folded_parts.append(fc)
            src_index.append(i)
    return "".join(folded_parts), src_index


def _find_folded_phrase_span(
    text: str,
    phrase_folded: str,
) -> Optional[tuple[int, int]]:
    """Return original-string span for a folded phrase match."""
    if not text or not phrase_folded:
        return None

    folded, src_index = _fold_with_index_map(text)
    pattern = r"(?<![0-9a-z])" + re.escape(phrase_folded) + r"(?![0-9a-z])"
    mo = re.search(pattern, folded)
    if not mo:
        return None

    start = src_index[mo.start()]
    end = src_index[mo.end() - 1] + 1
    return start, end


def _inject_course_code(
    rewritten: str,
    entities: Dict[str, Optional[str]],
    *,
    preserve_existing_codes: bool = False,
) -> str:
    """Insert the catalog-resolved course code after the course name in-place.

    E.g. "...Mạng máy tính được học..." → "...Mạng máy tính (IT3080) được học...".
    Only runs when a catalog-matched course (``course_name_folded`` + a derived
    ``course_code``) is present and the code is not already in the text.
    """
    code = (entities.get("course_code") or "").upper()
    name_folded = entities.get("course_name_folded")
    if not code or not name_folded:
        return rewritten
    if re.search(
        r"(?<![A-Za-z0-9])" + re.escape(code) + r"(?![A-Za-z0-9])",
        rewritten,
        re.IGNORECASE,
    ):
        return rewritten  # code already present (e.g. user typed it)

    course_name = entities.get("course_name") or ""
    alias_folded = entities.get("course_alias_folded")
    phrases: List[tuple[str, bool]] = []
    seen_phrases: set[str] = set()
    for phrase, is_alias in (
        (name_folded, False),
        (alias_folded, bool(alias_folded and alias_folded != name_folded)),
    ):
        if not phrase or phrase in seen_phrases:
            continue
        seen_phrases.add(phrase)
        phrases.append((phrase, is_alias))

    for phrase, is_alias in phrases:
        span = _find_folded_phrase_span(rewritten, phrase)
        if not span:
            continue

        start, end = span
        adjacent = _ADJACENT_COURSE_CODE_RE.match(rewritten[end:])
        if adjacent:
            existing_code = adjacent.group(1).upper()
            if existing_code == code:
                return rewritten
            if preserve_existing_codes:
                return rewritten
            if is_alias and course_name:
                close_at = end + adjacent.end()
                return f"{rewritten[:start]}{course_name} ({code}){rewritten[close_at:]}"
            code_start = end + adjacent.start(1)
            code_end = end + adjacent.end(1)
            return f"{rewritten[:code_start]}{code}{rewritten[code_end:]}"

        if preserve_existing_codes and _COURSE_CODE_RE.search(rewritten):
            return rewritten
        if is_alias and course_name:
            return f"{rewritten[:start]}{course_name} ({code}){rewritten[end:]}"
        return f"{rewritten[:end]} ({code}){rewritten[end:]}"

    return rewritten


def _preserve_explicit_course_code(rewritten: str, explicit_code: Optional[str]) -> str:
    """Keep the course code typed by the user if the LLM rewrote it."""
    if not explicit_code:
        return rewritten
    explicit_code = explicit_code.upper()
    if re.search(
        r"(?<![A-Za-z0-9])" + re.escape(explicit_code) + r"(?![A-Za-z0-9])",
        rewritten,
        re.IGNORECASE,
    ):
        return rewritten
    return _COURSE_CODE_RE.sub(explicit_code, rewritten, count=1)


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
        self.temperature = (
            temperature
            if temperature is not None
            else settings.reflection_temperature
        )
        self.max_tokens: int = getattr(settings, "reflection_max_tokens", 256)
        self.history_limit = history_limit

        provider = settings.reflection_provider

        # Setup OpenAI client parameters based on provider
        if provider == "gemini":
            base_url = _GEMINI_BASE_URL
            resolved_key = (
                api_key
                or settings.google_api_key
                or os.getenv("GOOGLE_API_KEY", "")
            )
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
            resolved_key = (
                api_key
                or settings.openai_api_key
                or os.getenv("OPENAI_API_KEY", "")
            )
        else:
            base_url = _GEMINI_BASE_URL
            resolved_key = (
                api_key
                or settings.google_api_key
                or os.getenv("GOOGLE_API_KEY", "")
            )

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
        # Strip PII and conversational noise before any processing so that
        # names, student IDs, and greetings never pollute the reflector LLM
        # call or the retrieval query.
        raw_query = query  # preserve for return value
        query = _strip_pii_and_noise(query)
        explicit_course_code_match = _COURSE_CODE_RE.search(query)
        user_typed_course_code = (
            explicit_course_code_match.group(0).upper()
            if explicit_course_code_match
            else None
        )

        context_with_major = _merge_user_major_into_context(
            user_context, user_major
        )
        merged_profile, profile_note_override = _merge_profile_context(
            user_context=context_with_major,
            user_profile=user_profile,
        )

        # For generic freshness queries, skip history to prevent academic-scope
        # bleeding (e.g. prior assistant response mentioning "2025.2" should not
        # cause the LLM to inject that term into "lịch đăng kí kì học mới nhất").
        effective_history = (
            chat_history
            if self._should_use_history_for_reflection(query, chat_history)
            else None
        )
        if chat_history and effective_history is None:
            logger.info(
                "Reflection: history suppressed for standalone query %r",
                query[:60],
            )

        # Passthrough mode: skip LLM call when there is nothing to resolve.
        # Without history, profile, personal references, anaphora, or comparison
        # follow-up signals the LLM call has no information to add and only
        # risks introducing spurious qualifiers or scope narrowing.
        # The deterministic guardrails (major-code expansion, abbreviation
        # expansion) are always applied regardless of this flag.
        _needs_llm_rewrite = bool(
            effective_history
            or _has_profile_dependent_signal(query)
            or _is_comparison_followup(query)
            or _ANAPHORA_SIGNALS_RE.search(query)
        )

        if not _needs_llm_rewrite:
            rewritten = query
            user_prompt = ""
            logger.info(
                "Reflection passthrough (no context to resolve): %r", query[:60]
            )
        else:
            user_prompt = self._build_user_prompt(
                query=query,
                chat_history=effective_history,
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
                        messages=cast(Any, messages),
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                    )
                    break
                except (RateLimitError, InternalServerError) as exc:
                    # Retry on 429 Rate-Limit and 503 Service Unavailable
                    if (
                        isinstance(exc, InternalServerError)
                        and exc.status_code != 503
                    ):
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

            rewritten = (response.choices[0].message.content or "").strip()

            # If the LLM returns empty or just whitespace, keep the original
            if not rewritten:
                rewritten = query

        # Save the raw LLM candidate before any guardrails modify it.
        # Exposed as trace-only field so callers can see what was rejected.
        reflection_candidate: str = rewritten
        reflection_guardrail_reverted: bool = False
        reflection_rejected_scope: Optional[str] = None

        deterministic_followup_applied = False
        deterministic_followup = _rewrite_comparison_followup(
            query=query,
            chat_history=chat_history,
            profile=merged_profile or None,
        )
        if deterministic_followup:
            deterministic_followup_applied = True
            if deterministic_followup != rewritten:
                logger.info(
                    "Deterministic comparison follow-up rewrite: %r -> %r",
                    rewritten[:80],
                    deterministic_followup[:80],
                )
                rewritten = deterministic_followup

        # Resolve entities once (major precedence: explicit query major >
        # login profile > history) so guardrails below can reuse them. This is
        # also where the catalog-derived course_code is populated.
        entities = _extract_entities(
            query,
            user_context=merged_profile or None,
            history=chat_history,
        )

        # Guardrail 1: if user profile has a trusted major but references remain
        # unresolved, replace them deterministically.
        if _PERSONAL_REFS.search(rewritten):
            rewritten = _enforce_major_reference_rewrite(
                rewritten_query=rewritten,
                profile=merged_profile or None,
            )

        # Guardrail 2 — Preserve curriculum-placement intent: don't let the
        # reflector silently turn "môn X được học vào kỳ mấy" into "…đăng ký…".
        placement_candidate = rewritten
        rewritten = _preserve_curriculum_placement_verb(query, rewritten)
        if rewritten != placement_candidate:
            logger.info(
                "Reflection guardrail: reverted placement verb drift %r -> %r",
                placement_candidate[:80],
                rewritten[:80],
            )

        # Guardrail 3 — Expand bare major codes to include full names.
        # E.g. "IT1" → "IT1 (Khoa học máy tính)" so that vector/keyword
        # retrieval matches documents that only contain the full name.
        # Deterministic — uses MAJOR_CODE_TO_NAME dict, no LLM involved.
        if not deterministic_followup_applied:
            rewritten = _expand_major_codes_in_query(rewritten)

        terminology_candidate = rewritten
        rewritten = expand_academic_abbreviations(rewritten)
        terminology_expanded = rewritten != terminology_candidate

        if user_typed_course_code:
            rewritten = _preserve_explicit_course_code(
                rewritten,
                user_typed_course_code,
            )
        else:
            _apply_catalog_course_match(entities, rewritten)

        # Guardrail 4 — Inject the major-scoped course code for a course named in
        # the query. E.g. for an IT-E6 student: "Mạng máy tính" → "Mạng máy tính
        # (IT3080)"; for IT-E7 the same name resolves to IT3080E. Only fires when
        # the major is known and the code is not already present (so user-typed
        # codes are never duplicated). Deterministic; runs even in passthrough.
        course_injected = _inject_course_code(
            rewritten=rewritten,
            entities=entities,
            preserve_existing_codes=bool(user_typed_course_code),
        )
        if course_injected != rewritten:
            logger.info(
                "Reflection guardrail: injected course code %r -> %r",
                rewritten[:80],
                course_injected[:80],
            )
            rewritten = course_injected

        logger.info(
            "Reflection: %r → %r (history_len=%d)",
            query[:60],
            rewritten[:60],
            len(chat_history) if chat_history else 0,
        )
        logger.debug("Extracted entities: %s", entities)

        return {
            "original": raw_query,
            "stripped": query,  # after PII removal, before LLM rewrite
            "rewritten": rewritten,
            "prompt": user_prompt if _needs_llm_rewrite else "",
            "entities": entities,
            # Trace-only fields — expose LLM candidate and guardrail outcome
            # for debugging without affecting retrieval behavior.
            "reflection_candidate": reflection_candidate,
            "reflection_guardrail_reverted": reflection_guardrail_reverted,
            "reflection_rejected_scope": reflection_rejected_scope,
            "terminology_expanded": terminology_expanded,
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
        context_with_major = _merge_user_major_into_context(
            user_context, user_major
        )
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

    @staticmethod
    def _should_use_history_for_reflection(
        query: str,
        chat_history: Optional[List[Dict[str, str]]],
    ) -> bool:
        """Return True when history context should be sent to the reflection LLM.

        History is opt-in, not a default. It is used for:
          - Queries with personal-profile references ("ngành của tôi", …)
          - Short comparison follow-ups ("so sánh với", "khác gì", …)
          - Queries with anaphoric references to prior context ("còn", "đó", …)

        Examples that skip history:
          "Lịch trình học kỳ mới nhất?"
          "lịch đăng kí kì học mới nhất"
          "môn hướng đối tượng được học vào kì mấy"
        """
        if not chat_history:
            return False

        if _has_profile_dependent_signal(query):
            return True

        if _is_comparison_followup(query):
            return True

        if _ANAPHORA_SIGNALS_RE.search(query):
            return True

        # Generic freshness query with no personal/anaphora/comparison signal:
        # skip history to prevent scope bleeding from prior assistant context.
        if _REFLECTION_FRESHNESS_ONLY_RE.search(_fold_vietnamese(query)):
            return False

        return False

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
        # Prefer explicit note > authenticated profile > history regex, but
        # only when the current query actually asks for personal context.
        profile_note = ""
        if _has_profile_dependent_signal(query):
            profile_note = (
                profile_note_override
                or _extract_profile_note_from_context(user_context)
            )
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
