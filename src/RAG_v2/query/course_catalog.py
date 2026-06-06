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

    folded_query = fold_vietnamese_text(query_text)
    # Entries are stored longest-name-first, so the first boundary match is the
    # most specific one (e.g. prefer "mạng máy tính nâng cao" over "mạng máy tính").
    for entry in courses:
        name_folded = entry.get("name_folded") or ""
        if not name_folded:
            continue
        pattern = r"(?<![0-9a-z])" + re.escape(name_folded) + r"(?![0-9a-z])"
        if re.search(pattern, folded_query):
            return entry
    return None
