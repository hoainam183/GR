from __future__ import annotations

import hashlib
import json
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


def _normalise_plan_steps_for_entities(
    steps: list[Any],
    source_query: str,
) -> tuple[list[Any], dict[str, Any]]:
    """Preserve explicit major/cohort scope when planner emits generic steps."""
    from retrieval.metadata_filters import (  # noqa: PLC0415
        extract_cohort_codes,
        extract_major_codes,
    )

    all_source_majors = extract_major_codes(source_query)
    all_source_cohorts = extract_cohort_codes(source_query)
    source_major = _single_extracted_entity(all_source_majors)
    source_cohort = _single_extracted_entity(all_source_cohorts)
    source_has_multiple_majors = len(all_source_majors) >= 2
    source_has_multiple_cohorts = len(all_source_cohorts) >= 2
    trace: dict[str, Any] = {
        "applied": False,
        "major_hint": source_major,
        "cohort_hint": source_cohort,
        "multi_major_mode": source_has_multiple_majors,
    }
    if (
        not source_major
        and not source_cohort
        and not source_has_multiple_majors
        and not source_has_multiple_cohorts
    ):
        return steps, trace

    normalised_steps: list[Any] = []
    changed = False
    for raw_step in steps:
        step, step_changed = _normalise_plan_step_for_entities(
            raw_step,
            source_major,
            source_cohort,
            source_has_multiple_majors,
            source_has_multiple_cohorts,
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
    changed = _inject_missing_hints(
        step,
        source_major,
        source_cohort,
        step_major_codes,
        step_cohort_codes,
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


def _inject_missing_hints(
    step: dict[str, Any],
    source_major: str | None,
    source_cohort: str | None,
    step_major_codes: list[str],
    step_cohort_codes: list[str],
) -> bool:
    changed = False
    if (
        source_major
        and not _clean_plan_hint(step.get("major_hint"))
        and (not step_major_codes or source_major in step_major_codes)
    ):
        step["major_hint"] = source_major
        changed = True

    if (
        source_cohort
        and not _clean_plan_hint(step.get("cohort_hint"))
        and (not step_cohort_codes or source_cohort in step_cohort_codes)
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
    step_major_to_inject = source_major
    if not step_major_to_inject and source_has_multiple_majors:
        step_major_to_inject = _clean_plan_hint(step.get("major_hint"))
    if step_major_to_inject and not step_major_codes:
        scoped_query = f"{scoped_query} ngành {step_major_to_inject}"

    step_cohort_to_inject = source_cohort
    if not step_cohort_to_inject and source_has_multiple_cohorts:
        step_cohort_to_inject = _clean_plan_hint(step.get("cohort_hint"))
    if step_cohort_to_inject and not step_cohort_codes:
        scoped_query = f"{scoped_query} {step_cohort_to_inject}"

    return " ".join(scoped_query.split())


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
