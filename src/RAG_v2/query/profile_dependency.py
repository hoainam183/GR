"""Topic-driven DEPENDENCY vs SOURCE resolution for user-profile attributes.

The old pipeline decided whether to inject the user's major/cohort by scanning the
query for the pronoun "tôi"/"em". That conflated two independent questions and was
both leaky (missed "em ...", pronoun-less questions) and wrong (filtered universal
topics like scholarships by major). This module splits the decision in two:

* **DEPENDENCY** — *Does the answer depend on a profile attribute?* This is a
  property of the TOPIC (intent / sub-topic), derived from the router domain and a
  small sub-topic keyword map — NOT from whether a pronoun is present.
  See :func:`required_attributes`.

* **SOURCE** — *For each required attribute, where does the value come from?*
  Priority: an explicit target named in the query (e.g. "ngành IT-E7") → the
  authenticated user profile → otherwise unresolved (ask the user).
  See :func:`resolve_sources`.

A profile note / metadata filter is applied for an attribute only when the topic
requires it AND its value resolves to the authenticated user profile. The same
helpers are consumed by reflection, retrieval-filter gating and generation so the
three layers always agree.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Mapping, Optional, Set

__all__ = [
    "required_attributes",
    "references_self",
    "resolve_sources",
    "should_inject_profile_note",
    "effective_major_for_retrieval",
]


def _fold(text: str) -> str:
    """Lower-case and strip Vietnamese diacritics (đ→d) for robust matching."""
    if not text:
        return ""
    text = text.replace("Đ", "d").replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return stripped.lower()


# ── Sub-topic signals (folded form) ──────────────────────────────────────────
# Scholarship / financial-aid procedures are the same for every student → no
# profile attribute required (acceptance #4 — must NOT filter by major).
_SCHOLARSHIP_RE = re.compile(r"\bhoc\s*bong\b|\btro\s*cap\b|\bmien\s*giam\s*hoc\s*phi\b")
# Tuition (học phí) is program-specific — IT-E6 (Việt-Nhật) and IT1 (Khoa học
# máy tính) charge different amounts — so "học phí của tôi" must resolve to the
# user's major. The scholarship/fee-waiver check runs first so "miễn giảm học
# phí" stays a universal procedure (set()).
_TUITION_RE = re.compile(r"\bhoc\s*phi\b|\bmuc\s*hoc\s*phi\b|\bchi\s*phi\b.*\bhoc\b")
# Foreign-language graduation requirement depends on the program/major
# (English programs use TOEIC, Japanese programs use JLPT N3/N4, etc.).
_FOREIGN_LANG_RE = re.compile(
    r"\bngoai\s*ngu\b|\btieng\s*anh\b|\btieng\s*nhat\b|\btieng\s*phap\b"
    r"|\bforeign\s*language\b|\btoeic\b|\bielts\b|\bjlpt\b|\bdelf\b"
)
# Graduation conditions depend on both program (major) and cohort (regulation year).
_GRADUATION_RE = re.compile(r"\btot\s*nghiep\b|\bxet\s*tot\s*nghiep\b|\bra\s*truong\b")
# Course/curriculum placement depends on the program/major.
_COURSE_CURRICULUM_RE = re.compile(
    r"\bmon(?:\s*hoc)?\b|\bhoc\s*phan\b|\bchuong\s*trinh\s*dao\s*tao\b"
)
# Registration/procedure questions about courses are schedule/support topics.
_COURSE_REGISTRATION_RE = re.compile(
    r"\bthu\s*tuc\b.*\bdang\s*ky\b|\bdang\s*ky\s*hoc\s*phan\b"
)
# Training regulations vary by cohort (K64 vs K65 follow different quy chế).
_TRAINING_REG_RE = re.compile(r"\bquy\s*che\s*dao\s*tao\b|\bquy\s*che\b")


def _domains(routing_result: Optional[Mapping[str, Any]]) -> Set[str]:
    if not routing_result:
        return set()
    domain = routing_result.get("domain")
    domains = routing_result.get("domains") or ([domain] if domain else [])
    return {str(d) for d in domains if d}


# ── Self-reference signal (folded form) ──────────────────────────────────────
# True only when the query OWNS the topic to the student via a possessive /
# subject-of-study construction ("X của tôi", "ngành tôi", "tôi học ..."). A bare
# politeness pronoun ("cho em hỏi ...") must NOT count, or every student question
# would re-trigger profile injection (the original leak). See references_self.
_SELF_REF_RE = re.compile(
    r"\bcua\s+(?:toi|minh|em)\b"
    r"|\b(?:nganh|khoa|chuong\s*trinh)\s+(?:toi|minh|em)\b"
    r"|\b(?:toi|minh|em)\s+(?:hoc|dang\s*hoc|thuoc|la\s*sinh\s*vien)\b"
)


def references_self(question: Optional[str]) -> bool:
    """True when the question explicitly scopes a topic to the asker.

    Distinguishes a self-referential, program-personal question ("học phí của
    tôi", "ngành tôi") from a general-policy question that merely contains a
    topic keyword ("tiếng Anh cơ bản ảnh hưởng thế nào"). Possessive-based so a
    bare politeness "em" ("cho em hỏi ...") is not a false positive.
    """
    return _SELF_REF_RE.search(_fold(question or "")) is not None


def _classify(
    question: str,
    search_query: Optional[str],
    routing_result: Optional[Mapping[str, Any]],
) -> tuple[Set[str], bool]:
    """Return ``(required_attrs, major_is_structural)``.

    ``major_is_structural`` is True only when the major requirement comes from a
    curriculum/course topic (the answer is meaningless without a program, so it
    auto-scopes to the student even with no self-reference). Policy topics
    (tuition / foreign-language / graduation-regulation) are structural=False:
    they scope to the student's major only on an explicit self-reference or a
    target major named in the query.

    Decision order — most specific sub-topic first, then router-domain defaults.
    """
    text = _fold(f"{question or ''} {search_query or ''}")

    if _SCHOLARSHIP_RE.search(text):
        return set(), False
    if _TUITION_RE.search(text):
        return {"major"}, False
    if _FOREIGN_LANG_RE.search(text):
        return {"major"}, False
    if _GRADUATION_RE.search(text):
        return {"major", "cohort"}, False
    if _COURSE_REGISTRATION_RE.search(text):
        return set(), False
    if _COURSE_CURRICULUM_RE.search(text):
        return {"major"}, True
    if _TRAINING_REG_RE.search(text):
        return {"cohort"}, False

    domains = _domains(routing_result)
    if "ctdt" in domains:
        return {"major"}, True
    # kehoach (schedules), stsv (student services) and generic quydinh regulations
    # are program-independent by default.
    return set(), False


def required_attributes(
    question: str,
    search_query: Optional[str],
    routing_result: Optional[Mapping[str, Any]],
) -> Set[str]:
    """Return the set of profile attributes the answer depends on.

    Values are a subset of ``{"major", "cohort"}``. Empty set means the answer is
    universal (do not inject a profile note, do not filter by major/cohort).
    Thin wrapper over :func:`_classify` (kept for the public/topic-only callers).
    """
    return _classify(question, search_query, routing_result)[0]


def resolve_sources(
    required: Set[str],
    *,
    user_major: Optional[str] = None,
    target_major: Optional[str] = None,
    cohort: Optional[str] = None,
    user_referenced: bool = False,
    major_structural: bool = False,
) -> Dict[str, str]:
    """Map each required attribute to its SOURCE: ``target`` / ``user_profile`` / ``ask``.

    * ``target``       — the query named the value explicitly (e.g. "ngành IT-E7");
                         answer about that target, do not inject the user's profile.
    * ``user_profile`` — value comes from the authenticated profile; inject + filter.
    * ``ask``          — value is required but unknown; the model should ask.

    For ``major``, the authenticated profile is used only when the requirement is
    ``major_structural`` (curriculum — auto-scope) OR the query is
    ``user_referenced`` (self-referential, e.g. "của tôi"). A program-personal
    policy topic asked impersonally ("tiếng Anh cơ bản ảnh hưởng thế nào") stays
    ``ask`` so it is answered universally, not silently scoped to one major.
    """
    sources: Dict[str, str] = {}
    for attr in required:
        if attr == "major":
            if target_major:
                sources["major"] = "target"
            elif user_major and (major_structural or user_referenced):
                sources["major"] = "user_profile"
            else:
                sources["major"] = "ask"
        elif attr == "cohort":
            # Cohort has no in-query "target" notion distinct from the resolved
            # value; a present cohort is profile/query-sourced, treat as profile.
            sources["cohort"] = "user_profile" if cohort else "ask"
    return sources


def should_inject_profile_note(
    question: str,
    search_query: Optional[str],
    routing_result: Optional[Mapping[str, Any]],
    *,
    user_major: Optional[str] = None,
    target_major: Optional[str] = None,
    cohort: Optional[str] = None,
) -> bool:
    """True when at least one required attribute resolves to the user's profile.

    This is the single gate shared by generation (whether to prepend the profile
    note) — replacing the brittle pronoun regexes that disagreed across layers.
    """
    required, major_structural = _classify(question, search_query, routing_result)
    if not required:
        return False
    sources = resolve_sources(
        required,
        user_major=user_major,
        target_major=target_major,
        cohort=cohort,
        user_referenced=references_self(question),
        major_structural=major_structural,
    )
    return any(src == "user_profile" for src in sources.values())


def effective_major_for_retrieval(
    question: str,
    search_query: Optional[str],
    routing_result: Optional[Mapping[str, Any]],
    resolved_major: Optional[str],
    *,
    target_major: Optional[str] = None,
    user_major: Optional[str] = None,
) -> Optional[str]:
    """Return the major to pass to retrieval, or ``None`` to skip major filtering.

    Mirrors the generation gate so the two layers always agree: the filter is
    applied only when the major's SOURCE is ``target`` or ``user_profile``.
    Universal topics (scholarships) and program-personal POLICY topics asked
    impersonally ("tiếng Anh cơ bản ảnh hưởng thế nào") drop the filter, so the
    answer is not silently narrowed to one program. When ``target_major`` /
    ``user_major`` are not supplied, falls back to ``resolved_major`` as the
    user-profile candidate (legacy positional callers / topic-only tests).
    """
    if not resolved_major:
        return None
    required, major_structural = _classify(question, search_query, routing_result)
    if "major" not in required:
        return None
    sources = resolve_sources(
        required,
        user_major=user_major or resolved_major,
        target_major=target_major,
        user_referenced=references_self(question),
        major_structural=major_structural,
    )
    return resolved_major if sources.get("major") in {"target", "user_profile"} else None
