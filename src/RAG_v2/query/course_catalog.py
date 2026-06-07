"""Major-aware course-name → course-code lookup.

Loads the prebuilt artifact ``query/models/course_catalog.json`` (produced by
``scripts/build_course_catalog.py``) and resolves a course code for a query that
mentions a course *by name*, scoped to the user's major/program.

The same course name can map to different codes across programs
(e.g. "Mạng máy tính" → ``IT3080`` in IT2/IT-E6/IT1 but ``IT3080E`` in IT-E7),
so lookup is ALWAYS keyed by ``major_code``. When the major is unknown the
lookup returns ``None`` (the caller then leaves the query untouched and lets the
answer layer ask which program the user is in).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from query.signals import fold_vietnamese_text

logger = logging.getLogger(__name__)

_CATALOG_PATH = Path(__file__).resolve().parent / "models" / "course_catalog.json"

# Lazy module-level cache: {major_code: [{code, name, name_folded, semester, credits}]}
_CATALOG: Optional[Dict[str, List[Dict[str, Optional[str]]]]] = None

_COURSE_ALIAS_PREFIXES = (
    "lap trinh ",
)


def _load_catalog() -> Dict[str, List[Dict[str, Optional[str]]]]:
    global _CATALOG
    if _CATALOG is None:
        try:
            _CATALOG = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
            logger.info(
                "Loaded course catalog: %d majors from %s",
                len(_CATALOG),
                _CATALOG_PATH.name,
            )
        except (OSError, ValueError):
            logger.warning(
                "Course catalog not available at %s — course-code injection disabled. "
                "Run `python -m scripts.build_course_catalog` to build it.",
                _CATALOG_PATH,
            )
            _CATALOG = {}
    return _CATALOG


def _normalize_major(major_code: Optional[str]) -> str:
    return (major_code or "").strip().upper()


def _normalise_course_phrase(value: str) -> str:
    """Return a searchable folded course phrase without bullet punctuation."""
    text = (value or "").strip().casefold()
    text = re.sub(r"^[^0-9a-z]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _phrase_matches(folded_query: str, phrase: str) -> bool:
    if not phrase:
        return False
    pattern = r"(?<![0-9a-z])" + re.escape(phrase) + r"(?![0-9a-z])"
    return bool(re.search(pattern, folded_query))


def _course_aliases(name_folded: str) -> List[str]:
    """Return exact name first, followed by safe shorthand aliases."""
    name = _normalise_course_phrase(name_folded)
    if not name:
        return []

    aliases = [name]
    for prefix in _COURSE_ALIAS_PREFIXES:
        if not name.startswith(prefix):
            continue
        alias = name[len(prefix) :].strip()
        if len(alias.split()) >= 2:
            aliases.append(alias)

    unique: List[str] = []
    seen: set[str] = set()
    for alias in aliases:
        if alias in seen:
            continue
        seen.add(alias)
        unique.append(alias)
    return unique


def _unique_code_match(
    matches: List[tuple[str, Dict[str, Optional[str]]]],
) -> Optional[Dict[str, Optional[str]]]:
    """Return the best match only when all candidates share one code."""
    if not matches:
        return None

    max_alias_len = max(len(alias) for alias, _ in matches)
    best_matches = [
        (alias, entry) for alias, entry in matches if len(alias) == max_alias_len
    ]
    codes = {entry.get("code") for _, entry in best_matches if entry.get("code")}
    if len(codes) != 1:
        return None

    alias, entry = next(
        (
            (candidate_alias, candidate_entry)
            for candidate_alias, candidate_entry in best_matches
            if candidate_entry.get("semester")
        ),
        best_matches[0],
    )
    result = dict(entry)
    result["matched_alias_folded"] = alias
    return result


def lookup_course_code(
    query_text: str,
    major_code: Optional[str],
) -> Optional[Dict[str, Optional[str]]]:
    """Return the course matched by name in ``query_text`` for ``major_code``.

    Returns a dict ``{code, name, name_folded, semester, credits}`` for the
    longest course name that appears (on token boundaries) in the query, or
    ``None`` when the major is unknown/uncovered or no course name matches.
    """
    if not query_text:
        return None
    catalog = _load_catalog()
    courses = catalog.get(_normalize_major(major_code))
    if not courses:
        return None

    folded_query = re.sub(r"\s+", " ", fold_vietnamese_text(query_text))
    # Entries are stored longest-name-first, so the first boundary match is the
    # most specific one (e.g. prefer "mạng máy tính nâng cao" over "mạng máy tính").
    for entry in courses:
        aliases = _course_aliases(entry.get("name_folded") or "")
        if not aliases:
            continue
        exact_name = aliases[0]
        if _phrase_matches(folded_query, exact_name):
            result = dict(entry)
            result["matched_alias_folded"] = exact_name
            return result

    alias_matches: List[tuple[str, Dict[str, Optional[str]]]] = []
    for entry in courses:
        for alias in _course_aliases(entry.get("name_folded") or "")[1:]:
            if _phrase_matches(folded_query, alias):
                alias_matches.append((alias, entry))

    unique_match = _unique_code_match(alias_matches)
    if unique_match:
        return unique_match
    return None
