"""Session profile extraction and generation profile notes."""

from __future__ import annotations

import logging
import re

from typing import Any, Dict, Generator, List, Optional, Set

from retrieval.metadata_filters import (
    MAJOR_CODE_TO_NAME,
)

from .common import _fold_vietnamese

logger = logging.getLogger(__name__)


_EXPLICIT_MAJOR_CODE_RE = re.compile(
    r"\b(?:IT|MI|ME|EE|EV|CH|BF|MS|HE|TE|TX|TROY)"
    r"\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]?\s*"
    r"(?:E18|E15|E12|E11|E10|E8|E7|E6|E3|E1|EP|GU|LUH|NUT|IT|1|2|3|5)\b",
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


def _extract_session_profile_dict(
    history: Optional[List[Dict[str, str]]],
) -> Dict[str, str]:
    """Scan full conversation history and return a raw dict of user-stated facts.

    Keys: ``"nganh"``, ``"nam"``, ``"khoa"``, ``"gpa"`` (all optional).
    Returns empty dict when nothing useful is found.
    """
    if not history:
        return {}

    profile: Dict[str, str] = {}
    user_messages = [
        m.get("content", "")
        for m in history
        if m.get("role") == "user" and m.get("content")
    ]

    for text in user_messages:
        t = text.lower()
        if not profile.get("nganh"):
            m = re.search(
                r"(?:h\u1ecdc ng\u00e0nh|ng\u00e0nh|chuy\u00ean ng\u00e0nh)\s+([^\.,\n]{2,30})",
                t,
            )
            if m:
                profile["nganh"] = m.group(1).strip()
        if not profile.get("nam"):
            m = re.search(
                r"sinh vi\u00ean n\u0103m\s*(\d)|n\u0103m\s*(\d)\b|n\u0103m th\u1ee9\s*(\d)",
                t,
            )
            if m:
                profile["nam"] = next(g for g in m.groups() if g)
        if not profile.get("khoa"):
            m = re.search(r"\bk(\d{2,3})\b|kh\u00f3a\s*(\d{2,3})", t)
            if m:
                profile["khoa"] = next(g for g in m.groups() if g)
        if not profile.get("gpa"):
            m = re.search(
                r"\b(?:cpa|gpa)\s*(?:l\u00e0|=|:)?\s*(\d+[\.,]\d+)\b", t
            )
            if m:
                profile["gpa"] = m.group(1).replace(",", ".")

    return profile


def _extract_session_profile(history: Optional[List[Dict[str, str]]]) -> str:
    """Scan full conversation history for user-stated facts (major, year, GPA).

    Returns a compact note like:
        "ThÃ´ng tin sinh viÃªn: ngÃ nh CNTT, nÄƒm 3, CPA=2.4."
    or empty string when nothing useful is found.

    This allows the LLM to answer personal questions (\"tÃ´i há»c ngÃ nh gÃ¬?\") even
    after the original turn has been trimmed from the context window.
    """
    profile = _extract_session_profile_dict(history)
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

    return "Th\u00f4ng tin sinh vi\u00ean: " + ", ".join(parts) + "."


def _should_prepend_profile_note(question: str) -> bool:
    """Return True only when the question explicitly depends on user profile."""
    if _EXPLICIT_MAJOR_CODE_RE.search(question or "") is not None:
        return False
    return bool(
        _PROFILE_DEPENDENT_QUERY_RE.search(_fold_vietnamese(question or ""))
    )


def _build_resolved_profile_note(
    major_for_note: Optional[str],
    resolved_cohort: Optional[str],
) -> str:
    """Build the generation profile note from facts the caller already gated.

    Caller (:func:`_profile_note_for_generation`) decides WHETHER the major may be
    surfaced (target named, curriculum auto-scope, or a self-referential question)
    and passes ``major_for_note=None`` otherwise. This deliberately does NOT read
    ``user_context`` directly: the old "blind dump" of the authenticated profile
    (name / student-id / major) leaked the asker's program into answers to general
    questions that merely mentioned a profile-dependent topic.
    """
    parts: List[str] = []
    if major_for_note:
        major_text = MAJOR_CODE_TO_NAME.get(major_for_note, major_for_note)
        if major_text and major_text != major_for_note:
            major_text = f"{major_text} [{major_for_note}]"
        parts.append(f"NgÃ nh: {major_text}")
    if resolved_cohort:
        parts.append(f"KhoÃ¡: {resolved_cohort}")
    if not parts:
        return ""
    return "ThÃ´ng tin sinh viÃªn: " + " | ".join(parts) + "."


def _profile_note_for_generation(
    question: str,
    search_query: Optional[str],
    routing_result: Optional[Dict[str, Any]],
    resolved_major: Optional[str],
    resolved_cohort: Optional[str],
    resolved_user_major: Optional[str],
    resolved_target_major: Optional[str],
    user_context: Optional[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]],
) -> str:
    """Decide and build the profile note prepended to the generation context.

    Topic-driven via ``query.profile_dependency``: inject the user's program/cohort
    only when the answer depends on a profile attribute that resolves to the
    authenticated profile (not a target named in the query). A legacy phrasing
    check is kept as a floor so self-referential identity questions
    ("ngÃ nh cá»§a tÃ´i lÃ  gÃ¬") still surface the profile.

    This is the consistency fix (BUG-1 / BUG-4): retrieval major-filtering and the
    generation note now share one gate, so a major reflection already resolved is
    never silently dropped â€” the model stops re-asking the program.
    """
    user_major = resolved_user_major or (
        (user_context or {}).get("major_code")
        or (user_context or {}).get("major")
    )

    # Simplified profile note injection: surface the program and cohort
    # if the question is self-referential ("tôi", "em", "mình") or directly involves personal profile.
    identity = _should_prepend_profile_note(question)
    include_major = identity and bool(user_major)
    include_cohort = identity and bool(resolved_cohort)

    major_for_note = resolved_major if include_major else None
    cohort_for_note = resolved_cohort if include_cohort else None
    return _build_resolved_profile_note(
        major_for_note, cohort_for_note
    ) or _extract_session_profile(history)
