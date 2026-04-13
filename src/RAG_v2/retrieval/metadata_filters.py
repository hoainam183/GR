"""Per-collection metadata filter extraction — pre-filtering step before hybrid search.

Architecture (pre-search flow):
  1. ``build_collection_filters()`` extracts an ordered ES-filter fallback chain
     for each active collection.
  2. ``MultiCollectionSearch`` runs ES metadata-only searches (filter, no text
     scoring) for each collection using those chains.
  3. Matching doc IDs are passed to Qdrant as ``HasIdCondition`` — restricting
     vector search to the pre-filtered subset.
  4. ES keyword (hybrid) search reuses the same term filter directly.
  5. If every ES metadata query in the chain returns zero results → fallback to
     no filter (search the entire collection).

Per-collection filter logic:
  - ctdt    : major_code (exact) → major_name (match) → no filter.
              Chunks with null major_code apply to all majors (always included).
  - quydinh : applicable_major array → no filter.
              Chunks with null applicable_major apply to all majors.
  - kehoach : date filter only when query contains specific year / month.
              After retrieval a recency score bonus rewards newer documents.
  - stsv    : no metadata filter.

To add a new collection filter:
  1. Subclass ``BaseFilterExtractor`` and implement ``extract()``.
  2. Register the instance in ``_COLLECTION_FILTER_REGISTRY``.
  No other files need to change.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ─── Data class ─────────────────────────────────────────────────────────────────


@dataclass
class CollectionFilter:
    """Filter spec for a single collection.

    ``metadata_es_queries`` is an ordered fallback chain of ES filter-only
    queries (no text scoring).  ``MultiCollectionSearch`` tries them in order
    until one returns doc IDs — those IDs become the Qdrant ``HasIdCondition``
    and are also reused as ES term filter in the hybrid keyword search.

    An empty list means no pre-filtering (search all documents).
    """

    metadata_es_queries: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True when no pre-filter queries are defined (search all)."""
        return not self.metadata_es_queries


# ─── Abstract base ───────────────────────────────────────────────────────────────


class BaseFilterExtractor(ABC):
    """Base class for per-collection metadata filter extraction.

    Subclass this to define filter logic for a new collection.

    The ``extract`` method receives:
      - ``query``: current (possibly reflected / enriched) query string.
      - ``resolved_major``: optional major string resolved from user profile /
        conversation history *before* this call (may be a code or a name).
        When provided it takes priority over regex-based extraction from
        ``query``.

    Returns a :class:`CollectionFilter` whose ``metadata_es_queries`` list is
    the fallback chain tried in order by the pre-search step.
    """

    @abstractmethod
    def extract(
        self,
        query: str,
        resolved_major: Optional[str] = None,
    ) -> CollectionFilter:
        """Extract the metadata filter fallback chain for this collection.

        Returns:
            :class:`CollectionFilter` — ``is_empty`` when no filter applies.
        """
        ...


# ─── Shared helpers ───────────────────────────────────────────────────────────────

# Map major_code → canonical major_name (used for name-based fallback queries).
# Add new programmes here together with an entry in MAJOR_PATTERNS.
MAJOR_CODE_TO_NAME: Dict[str, str] = {
    "IT-E10": "Khoa học Dữ liệu và Trí tuệ Nhân tạo",
    "IT-E15": "An toàn không gian số",
    "IT-E6": "Công nghệ thông tin Việt - Nhật",
    "IT-E7": "Công nghệ thông tin toàn cầu",
    "IT-EP": "Công nghệ thông tin Việt Pháp",
    "IT1": "Khoa học máy tính",
    "IT2": "Kỹ thuật máy tính",
    "MI1": "Toán - Tin",
    "MI2": "Hệ thống thông tin quản lý",
}

# Major-code patterns: list of (regex_pattern, major_code) tuples.
# Patterns are tried in order; the first match wins.
# Add new programmes here — no other code needs to change.
MAJOR_PATTERNS: List[Tuple[str, str]] = [
    (r"\bIT-E10\b|khoa học dữ liệu|trí tuệ nhân tạo|\bDATA\b|\bAI\b", "IT-E10"),
    (r"\bIT-E15\b|an toàn không gian số|cyber|bảo mật số", "IT-E15"),
    (r"\bIT-E6\b|việt.{0,4}nhật|ICTVJ", "IT-E6"),
    (r"\bIT-E7\b|toàn cầu|global ICT|ICTG", "IT-E7"),
    (r"\bIT-EP\b|việt.?pháp|ICTFR", "IT-EP"),
    (r"\bIT1\b|khoa học máy tính", "IT1"),
    (r"\bIT2\b|kỹ thuật máy tính", "IT2"),
    (r"\bMI1\b|\btoán.?tin\b|toán ứng dụng", "MI1"),
    (r"\bMI2\b|hệ thống thông tin quản lý|\bMIS\b", "MI2"),
]


def _extract_major_code(text: str) -> Optional[str]:
    """Return major_code matched from *text*, or ``None`` if no match."""
    for pattern, code in MAJOR_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return code
    return None


def _resolve_major_code(
    query: str,
    resolved_major: Optional[str],
) -> Optional[str]:
    """Determine the active major_code.

    Priority:
      1. ``resolved_major`` (from user profile / conversation history):
         try to interpret as a code first, else run regex on it.
      2. Regex detection on ``query`` itself.
    """
    if resolved_major:
        # If resolved_major is already a known code, use it directly.
        if resolved_major in MAJOR_CODE_TO_NAME:
            return resolved_major
        # Otherwise treat it as a name/partial name and run pattern matching.
        code = _extract_major_code(resolved_major)
        if code:
            return code
    # Fall back to current query regex detection.
    return _extract_major_code(query)


def _null_or_term(field: str, value: str) -> Dict[str, Any]:
    """ES query: ``field == value`` OR field is absent (null → applies to all).

    Uses ``field.keyword`` sub-field for exact-match term queries so that
    values containing hyphens (e.g. ``IT-E6``) are not tokenised.
    """
    return {
        "bool": {
            "should": [
                {"term": {f"{field}.keyword": value}},
                {"bool": {"must_not": {"exists": {"field": field}}}},
            ],
            "minimum_should_match": 1,
        }
    }


def _null_or_match(field: str, value: str) -> Dict[str, Any]:
    """ES query: ``field`` contains *value* (fuzzy match) OR field is absent."""
    return {
        "bool": {
            "should": [
                {"match": {field: {"query": value, "fuzziness": "AUTO"}}},
                {"bool": {"must_not": {"exists": {"field": field}}}},
            ],
            "minimum_should_match": 1,
        }
    }


# ─── Collection-specific extractors ─────────────────────────────────────────────


class CtdtFilterExtractor(BaseFilterExtractor):
    """Filter *ctdt* by ``major_code`` (exact) → ``major_name`` (fuzzy) → all.

    Chunks with ``major_code = null`` apply to all majors and are always
    included regardless of the detected major (handled by ``_null_or_term``).
    """

    def extract(
        self,
        query: str,
        resolved_major: Optional[str] = None,
    ) -> CollectionFilter:
        major_code = _resolve_major_code(query, resolved_major)
        if not major_code:
            return CollectionFilter()

        major_name = MAJOR_CODE_TO_NAME.get(major_code, "")
        queries: List[Dict[str, Any]] = [
            # First try: exact major_code match (most precise)
            _null_or_term("major_code", major_code),
        ]
        if major_name:
            # Fallback: fuzzy match on major_name (if code filter is too strict)
            queries.append(_null_or_match("major_name", major_name))

        return CollectionFilter(metadata_es_queries=queries)


class QuyDinhFilterExtractor(BaseFilterExtractor):
    """Filter *quydinh* by ``applicable_major`` array → all.

    Chunks with ``applicable_major = null`` apply to all majors and are
    always included (handled by ``_null_or_term``).
    """

    def extract(
        self,
        query: str,
        resolved_major: Optional[str] = None,
    ) -> CollectionFilter:
        major_code = _resolve_major_code(query, resolved_major)
        if not major_code:
            return CollectionFilter()

        return CollectionFilter(
            metadata_es_queries=[
                _null_or_term("applicable_major", major_code),
            ]
        )


class KeHoachFilterExtractor(BaseFilterExtractor):
    """Filter *kehoach* by date when query mentions a specific year / month.

    ``date_str`` format in the store: ``"D/M/YYYY"`` (e.g. ``"11/3/2026"``).

    Default (no date in query): no filter applied — all kehoach documents
    are searched.  After retrieval, ``MultiCollectionSearch`` applies a
    recency score bonus to reward newer documents.

    When a specific year and / or month is detected in the query the extractor
    builds an ES wildcard filter for that time period only.
    """

    def extract(
        self,
        query: str,
        resolved_major: Optional[str] = None,  # noqa: ARG002
    ) -> CollectionFilter:
        date_query = self._build_date_query(query)
        if date_query is None:
            return CollectionFilter()
        return CollectionFilter(metadata_es_queries=[date_query])

    # ------------------------------------------------------------------
    # Date parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_date_query(query: str) -> Optional[Dict[str, Any]]:
        """Return an ES wildcard / term query for the date hinted in *query*.

        Tries month+year first (e.g. "tháng 3 2026" → "*/3/2026"),
        then year-only (e.g. "năm 2025" → "*/*/*/2025" → actually "*/2025").
        Returns ``None`` when no date signals found.
        Handles both accented (tháng/năm) and unaccented (thang/nam) forms.
        """
        # Month + year: "tháng 3 2026", "thang 3 nam 2026", "3/2026", "03/2026"
        m = re.search(
            r"th[aá]ng\s*(\d{1,2})(?:\s+n[aă]m\s*|\s*/\s*)(\d{4})"
            r"|(\d{1,2})\s*/\s*(20\d{2})",
            query,
            re.IGNORECASE,
        )
        if m:
            if m.group(1):
                month, year = int(m.group(1)), int(m.group(2))
            else:
                month, year = int(m.group(3)), int(m.group(4))
            # date_str = "D/M/YYYY" → wildcard "*/M/YYYY"
            return {"wildcard": {"date_str": f"*/{month}/{year}"}}

        # Year only: "năm 2025", "nam 2025", bare "2025"
        m2 = re.search(r"(?:n[aă]m\s*)?(20\d{2})\b", query, re.IGNORECASE)
        if m2:
            year = int(m2.group(1))
            # Matches any date_str ending with "/{year}"
            return {"wildcard": {"date_str": f"*/{year}"}}

        return None


# ─── Recency scoring helper (used by MultiCollectionSearch) ─────────────────────

# Maximum bonus added to a kehoach document's fused score.
KEHOACH_RECENCY_BONUS_MAX: float = 0.05
# Documents older than this are capped at zero recency bonus.
KEHOACH_RECENCY_DECAY_DAYS: int = 365


def kehoach_recency_bonus(doc: Dict[str, Any]) -> float:
    """Compute recency score bonus for a single retrieved document.

    Returns a value in [0.0, ``KEHOACH_RECENCY_BONUS_MAX``] — higher for
    newer ``kehoach`` documents.  All other collections return 0.0.
    """
    if doc.get("collection") != "kehoach":
        return 0.0
    date_str: str = (doc.get("metadata") or {}).get("date_str", "")
    if not date_str:
        return 0.0
    try:
        parts = date_str.split("/")
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        doc_date = datetime(year, month, day)
        age_days = max(0, (datetime.now() - doc_date).days)
        ratio = max(0.0, 1.0 - age_days / KEHOACH_RECENCY_DECAY_DAYS)
        return ratio * KEHOACH_RECENCY_BONUS_MAX
    except Exception:
        return 0.0


# ─── Registry & public API ───────────────────────────────────────────────────────

# Map collection name → extractor instance.
# Register new extractors here; no other files need to change.
_COLLECTION_FILTER_REGISTRY: Dict[str, BaseFilterExtractor] = {
    "ctdt": CtdtFilterExtractor(),
    "quydinh": QuyDinhFilterExtractor(),
    "kehoach": KeHoachFilterExtractor(),
    # "stsv" intentionally omitted — no metadata filter defined
}


def build_collection_filters(
    query: str,
    collections: List[str],
    resolved_major: Optional[str] = None,
) -> Dict[str, CollectionFilter]:
    """Build per-collection metadata filter chains (pre-search step).

    Call this *before* hybrid search.  The returned ``CollectionFilter`` objects
    are consumed by ``MultiCollectionSearch`` to run ES metadata pre-searches
    whose results narrow Qdrant vector search via ``HasIdCondition``.

    Args:
        query: User query string (possibly reflected / enriched).
        collections: Active collection names to search.
        resolved_major: Major string resolved from user profile / conversation
            history.  When provided it takes priority over regex extraction from
            ``query``.

    Returns:
        ``{collection_name: CollectionFilter}`` — ``is_empty`` values mean no
        pre-filter for that collection.
    """
    result: Dict[str, CollectionFilter] = {}
    for col in collections:
        extractor = _COLLECTION_FILTER_REGISTRY.get(col)
        result[col] = (
            extractor.extract(query=query, resolved_major=resolved_major)
            if extractor is not None
            else CollectionFilter()
        )
    return result
