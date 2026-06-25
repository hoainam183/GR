from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

_ENTITY_SCOPED_COLLECTIONS = frozenset({"quy_dinh", "chuong_trinh"})


def _content_to_text(content: Any) -> str:
    if isinstance(content, list):
        return "".join(str(item) for item in content)
    return str(content or "")


def _preview_text(value: Any, limit: int = 2000) -> str:
    text = _content_to_text(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _hash_text(value: Any) -> str:
    return hashlib.sha256(_content_to_text(value).encode("utf-8")).hexdigest()


def _trace_plan_step(step: dict[str, Any], top_k: int | None) -> dict[str, Any]:
    traced = {
        key: step.get(key)
        for key in ("label", "query", "collection", "major_hint", "cohort_hint")
        if step.get(key) is not None
    }
    if top_k is not None:
        traced["top_k"] = top_k
    return traced


def _clean_plan_hint(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _single_extracted_entity(values: list[str]) -> str | None:
    unique_values = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return unique_values[0] if len(unique_values) == 1 else None


# Comparison wording that must SUPPRESS the profile fallback: a comparison
# question ("so sánh ngành của tôi với IT1") should not have the profile major
# forced onto every step. Kept folded/diacritic-insensitive to match mobile input.
_COMPARISON_KEYWORDS: tuple[str, ...] = (
    "so sánh",
    "khác gì",
    "khác nhau",
    "so sanh",
    "khac gi",
    "khac nhau",
)


@dataclass(frozen=True)
class ResolvedScope:
    """Authoritative entity scope for a planner run (query-first, profile-fallback)."""

    major: str | None = None
    cohort: str | None = None
    multi_major: bool = False
    multi_cohort: bool = False


def resolve_entity_scope(
    source_query: str,
    user_context: dict[str, Any] | None = None,
) -> ResolvedScope:
    """Resolve the authoritative major/cohort scope for a planner run.

    Resolution is deterministic and does NOT depend on the planner LLM:

    1. If the (reflected) query names exactly one major → use it.
    2. If it names ≥2 majors → comparison mode: no single major, steps keep
       their own scope (``multi_major=True``).
    3. Otherwise fall back to the user profile (``user_context["major_code"]``),
       but ONLY when the query carries a personal reference ("ngành của tôi",
       "tôi đang học…") — never for comparison wording. This mirrors the
       reflection layer's Rule 11 (``_has_profile_dependent_signal``): a bare
       question that does not reference the user must not be silently narrowed
       to the user's own major/cohort. Without this guard a follow-up like
       "với K63 thì sao" — which reflection deliberately leaves major-free —
       would have the profile major forced back onto every step.

    Cohort is resolved symmetrically against ``user_context["cohort"]``.
    """
    from query.signals import analyze_query_signals  # noqa: PLC0415
    from retrieval.metadata_filters import (  # noqa: PLC0415
        extract_cohort_codes,
        extract_major_codes,
    )

    query_majors = extract_major_codes(source_query)
    query_cohorts = extract_cohort_codes(source_query)
    multi_major = len(query_majors) >= 2
    multi_cohort = len(query_cohorts) >= 2

    folded = (source_query or "").casefold()
    is_comparison = any(keyword in folded for keyword in _COMPARISON_KEYWORDS)
    has_personal_ref = analyze_query_signals(source_query).personal_reference
    profile = user_context or {}

    major = _single_extracted_entity(query_majors)
    if major is None and not multi_major and not is_comparison and has_personal_ref:
        major = _clean_plan_hint(profile.get("major_code"))

    cohort = _single_extracted_entity(query_cohorts)
    if cohort is None and not multi_cohort and not is_comparison and has_personal_ref:
        cohort = _clean_plan_hint(profile.get("cohort"))

    return ResolvedScope(
        major=major,
        cohort=cohort,
        multi_major=multi_major,
        multi_cohort=multi_cohort,
    )


def _normalise_plan_steps_for_entities(
    steps: list[Any],
    source_query: str,
    user_context: dict[str, Any] | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Ground each step's major/cohort scope to the resolved entity scope.

    The scope is resolved once via :func:`resolve_entity_scope` (query-first,
    profile-fallback) so the steps are authoritative regardless of what the
    planner LLM emitted — passing ``user_context`` enables the profile fallback.
    """
    scope = resolve_entity_scope(source_query, user_context)
    trace: dict[str, Any] = {
        "applied": False,
        "major_hint": scope.major,
        "cohort_hint": scope.cohort,
        "multi_major_mode": scope.multi_major,
    }
    if (
        not scope.major
        and not scope.cohort
        and not scope.multi_major
        and not scope.multi_cohort
    ):
        return steps, trace

    normalised_steps: list[Any] = []
    changed = False
    for raw_step in steps:
        step, step_changed = _normalise_plan_step_for_entities(
            raw_step,
            scope.major,
            scope.cohort,
            scope.multi_major,
            scope.multi_cohort,
        )
        normalised_steps.append(step)
        changed = changed or step_changed

    trace["applied"] = changed
    return normalised_steps, trace


def _normalise_plan_step_for_entities(
    raw_step: Any,
    source_major: str | None,
    source_cohort: str | None,
    source_has_multiple_majors: bool,
    source_has_multiple_cohorts: bool,
) -> tuple[Any, bool]:
    from retrieval.metadata_filters import (  # noqa: PLC0415
        extract_cohort_codes,
        extract_major_codes,
    )

    if not isinstance(raw_step, dict):
        return raw_step, False

    step = dict(raw_step)
    query = str(step.get("query") or "").strip()
    collection = str(step.get("collection") or "").strip()
    step_major_codes = extract_major_codes(query)
    step_cohort_codes = extract_cohort_codes(query)
    changed = _ground_step_hints(
        step,
        source_major,
        source_cohort,
        source_has_multiple_majors,
        source_has_multiple_cohorts,
    )
    scoped_query = _scoped_query_for_entity_collection(
        query,
        collection,
        step,
        source_major,
        source_cohort,
        source_has_multiple_majors,
        source_has_multiple_cohorts,
        step_major_codes,
        step_cohort_codes,
    )
    if scoped_query != query:
        step["query"] = scoped_query
        changed = True
    return step, changed


def _ground_step_hints(
    step: dict[str, Any],
    source_major: str | None,
    source_cohort: str | None,
    source_has_multiple_majors: bool,
    source_has_multiple_cohorts: bool,
) -> bool:
    """Force a step's entity hints to match the source query's scope.

    The reflected source query is authoritative for entity scope. The planner
    LLM sometimes copies a major/cohort from its few-shot examples instead of
    the question (observed: ``major_hint="IT-E6"`` / ``cohort_hint="K67"`` for
    an "IT1" question). For each entity dimension the source names unambiguously
    we force that exact value — overriding a contradicting one; for a dimension
    the source does not name, a planner-invented hint is dropped. Multi-entity
    comparison queries (≥2 majors/cohorts) are left untouched so each step keeps
    its own scope.
    """
    changed = False
    if (
        not source_has_multiple_majors
        and _clean_plan_hint(step.get("major_hint")) != source_major
    ):
        step["major_hint"] = source_major
        changed = True
    if (
        not source_has_multiple_cohorts
        and _clean_plan_hint(step.get("cohort_hint")) != source_cohort
    ):
        step["cohort_hint"] = source_cohort
        changed = True
    return changed


def _scoped_query_for_entity_collection(
    query: str,
    collection: str,
    step: dict[str, Any],
    source_major: str | None,
    source_cohort: str | None,
    source_has_multiple_majors: bool,
    source_has_multiple_cohorts: bool,
    step_major_codes: list[str],
    step_cohort_codes: list[str],
) -> str:
    if not query or collection not in _ENTITY_SCOPED_COLLECTIONS:
        return query

    scoped_query = query

    # Major dimension. ``quy_dinh`` has no metadata filter, so the code in the
    # query text is the only routing signal — a contradicting major the planner
    # copied from an example must be rewritten, not just appended.
    if source_major and not source_has_multiple_majors:
        scoped_query = _reconcile_entity_code(
            scoped_query, step_major_codes, source_major, prefix="ngành "
        )
    elif source_has_multiple_majors:
        step_major = _clean_plan_hint(step.get("major_hint"))
        if step_major and not step_major_codes:
            scoped_query = f"{scoped_query} ngành {step_major}"

    # Cohort dimension (same reasoning).
    if source_cohort and not source_has_multiple_cohorts:
        scoped_query = _reconcile_entity_code(
            scoped_query, step_cohort_codes, source_cohort, prefix=""
        )
    elif source_has_multiple_cohorts:
        step_cohort = _clean_plan_hint(step.get("cohort_hint"))
        if step_cohort and not step_cohort_codes:
            scoped_query = f"{scoped_query} {step_cohort}"

    return " ".join(scoped_query.split())


def _reconcile_entity_code(
    text: str,
    found_codes: list[str],
    desired: str,
    prefix: str,
) -> str:
    """Make *text* reference exactly *desired* for one entity dimension.

    Replaces any code in *found_codes* that contradicts *desired* (a major the
    planner copied from a few-shot example), and appends *desired* when the text
    names no code for this dimension or the replacement missed a variant.
    """
    if not found_codes:
        return f"{text} {prefix}{desired}"
    result = text
    for code in found_codes:
        if code.casefold() == desired.casefold():
            continue
        result = re.sub(
            rf"(?<![0-9A-Za-z-]){re.escape(code)}(?![0-9A-Za-z-])",
            desired,
            result,
            flags=re.IGNORECASE,
        )
    if desired.casefold() not in result.casefold():
        result = f"{result} {prefix}{desired}"
    return result


def _parse_json_object(content: Any) -> dict[str, Any]:
    """Parse strict JSON object content, accepting optional markdown fences."""
    raw = _content_to_text(content).strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("planner response must be a JSON object")
    return parsed


def _is_empty_result_text(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    return (
        not normalized
        or normalized.startswith("[khong tim thay")
        or normalized.startswith("khong tim thay")
    )
