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
    - ctdt    : major_code (exact) → major_name (match) → major_code OR null
                            (generic chunks) → no filter.
    - quydinh : applicable_major (cohort Kxx) OR missing (generic chunks)
                → no filter.
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
import unicodedata
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
            - ``resolved_cohort``: optional cohort string resolved from user profile /
                conversation history (e.g. ``"70"`` or ``"K70"``).

    Returns a :class:`CollectionFilter` whose ``metadata_es_queries`` list is
    the fallback chain tried in order by the pre-search step.
    """

    @abstractmethod
    def extract(
        self,
        query: str,
        resolved_major: Optional[str] = None,
        resolved_cohort: Optional[str] = None,
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
    (r"\bIT[-\s]?E10\b|khoa học dữ liệu|trí tuệ nhân tạo|\bDATA\b|\bAI\b", "IT-E10"),
    (r"\bIT[-\s]?E15\b|an toàn không gian số|cyber|bảo mật số", "IT-E15"),
    (r"\bIT[-\s]?E6\b|việt.{0,4}nhật|ICTVJ", "IT-E6"),
    (r"\bIT[-\s]?E7\b|toàn cầu|global ICT|ICTG", "IT-E7"),
    (r"\bIT[-\s]?EP\b|việt.?pháp|ICTFR", "IT-EP"),
    (r"\bIT[-\s]?1\b|khoa học máy tính", "IT1"),
    (r"\bIT[-\s]?2\b|kỹ thuật máy tính", "IT2"),
    (r"\bMI[-\s]?1\b|\btoán.?tin\b|toán ứng dụng", "MI1"),
    (r"\bMI[-\s]?2\b|hệ thống thông tin quản lý|\bMIS\b", "MI2"),
]

# Map canonical major_name -> accepted aliases from profile/user context.
# Matching is case-insensitive and exact on alias entries.
MAJOR_NAME_ALIAS_MAPPING: Dict[str, List[str]] = {
    "Khoa học Dữ liệu và Trí tuệ Nhân tạo": [
        "Khoa học Dữ liệu và Trí tuệ Nhân tạo",
        "IT-E10",
        "Data AI",
    ],
    "An toàn không gian số": [
        "An toàn không gian số",
        "IT-E15",
        "An toàn thông tin",
    ],
    "Công nghệ thông tin Việt - Nhật": [
        "Công nghệ thông tin Việt - Nhật",
        "Công nghệ thông tin Việt Nhật",
        "CNTT Việt Nhật",
        "IT-E6",
        "ICTVJ",
    ],
    "Công nghệ thông tin toàn cầu": [
        "Công nghệ thông tin toàn cầu",
        "CNTT toàn cầu",
        "IT-E7",
        "ICTG",
    ],
    "Công nghệ thông tin Việt Pháp": [
        "Công nghệ thông tin Việt Pháp",
        "CNTT Việt Pháp",
        "IT-EP",
        "ICTFR",
    ],
    "Khoa học máy tính": [
        "Khoa học máy tính",
        "KHMT",
        "IT1",
    ],
    "Kỹ thuật máy tính": [
        "Kỹ thuật máy tính",
        "KTMT",
        "IT2",
    ],
    "Toán - Tin": [
        "Toán - Tin",
        "Toán tin",
        "MI1",
    ],
    "Hệ thống thông tin quản lý": [
        "Hệ thống thông tin quản lý",
        "HTTTQL",
        "MI2",
        "MIS",
    ],
}

_UNKNOWN_MAJOR_VALUES = {
    "",
    "none",
    "null",
    "unknown",
    "n/a",
    "na",
    "khong ro",
}

_DASH_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2212": "-",  # minus sign
    }
)
_MAJOR_CODE_FUZZY_RE = re.compile(
    r"\b(IT|MI)\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]?\s*(E10|E15|E6|E7|EP|1|2)\b",
    re.IGNORECASE,
)

def _canonicalise_major_code_parts(prefix: str, suffix: str) -> str:
    """Convert regex major parts to canonical major code (e.g. MI+1 -> MI1)."""
    p = prefix.upper()
    s = suffix.upper()
    return f"{p}{s}" if s in {"1", "2"} else f"{p}-{s}"
_COHORT_RE = re.compile(
    r"\bk\s*(\d{2,3})\b|kh[oó]a\s*k?\s*(\d{2,3})",
    re.IGNORECASE,
)
_COMPARE_HINT_RE = re.compile(
    r"\b(?:so\s*s[aá]nh|kh[aá]c\s+nhau|kh[aá]c\s+g[iì]|đ[oố]i\s*chi[eế]u|"
    r"doi\s*chieu|ph[aâ]n\s*bi[eệ]t|phan\s*biet)\b",
    re.IGNORECASE,
)
_COHORT_MENTION_RE = re.compile(
    r"\b(?:kh[oó]a\s*)?k\s*\d{2,3}\b",
    re.IGNORECASE,
)
_MAJOR_CODE_MENTION_RE = re.compile(
    r"\b(IT|MI)\s*-?\s*(E10|E15|E6|E7|EP|1|2)\b",
    re.IGNORECASE,
)
_COMPARE_CONNECTOR_RE = re.compile(
    r"\b(?:gi[uữ]a|v[aà]|v[oớ]i|voi)\b",
    re.IGNORECASE,
)
_COMPARE_FILLER_RE = re.compile(
    r"\bc[oó]\s*g[iì]\b",
    re.IGNORECASE,
)
_TRAILING_FUNCTION_WORD_RE = re.compile(
    r"\b(?:c[uủ]a|cho|trong|thu[oộ]c)\b$",
    re.IGNORECASE,
)

_MAJOR_NAME_TO_CODE: Dict[str, str] = {
    major_name: major_code
    for major_code, major_name in MAJOR_CODE_TO_NAME.items()
}


def _is_unknown_major(value: Optional[str]) -> bool:
    """Return True when *value* is empty or a common unknown placeholder."""
    if value is None:
        return True
    return value.strip().lower() in _UNKNOWN_MAJOR_VALUES


def _normalise_major_text(value: str) -> str:
    """Normalize major text so regex/alias matching is robust.

    Handles Unicode dash variants (e.g. ``IT–E6``), extra spaces around
    dashes, and compact forms like ``IT E6`` -> ``IT-E6``.
    """
    text = unicodedata.normalize("NFKC", value or "")
    text = text.translate(_DASH_TRANSLATION)
    text = re.sub(r"\s*-\s*", "-", text)
    text = _MAJOR_CODE_FUZZY_RE.sub(
        lambda m: _canonicalise_major_code_parts(m.group(1), m.group(2)),
        text,
    )
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def canonicalize_major_name(user_major: str) -> str:
    """Return canonical major name for *user_major* via alias mapping.

    Matching is case-insensitive and exact on values in
    ``MAJOR_NAME_ALIAS_MAPPING``. If no alias matches, return the original
    input unchanged.
    """
    if _is_unknown_major(user_major):
        return user_major

    normalised_input = _normalise_major_text(user_major)
    lowered_input = normalised_input.casefold()
    for canonical_name, aliases in MAJOR_NAME_ALIAS_MAPPING.items():
        for alias in aliases:
            if lowered_input == _normalise_major_text(alias).casefold():
                return canonical_name
    return normalised_input


def _extract_major_code(text: str) -> Optional[str]:
    """Return major_code matched from *text*, or ``None`` if no match."""
    normalised_text = _normalise_major_text(text)
    if _is_unknown_major(normalised_text):
        return None
    for pattern, code in MAJOR_PATTERNS:
        if re.search(pattern, normalised_text, re.IGNORECASE):
            return code
    return None


def _resolve_major_code(
    query: str,
    resolved_major: Optional[str],
) -> Optional[str]:
    """Determine the active major_code.

    Priority:
      1. ``resolved_major`` (from user profile / conversation history):
            try code -> canonical-name alias mapping -> regex.
      2. Regex detection on ``query`` itself.

    Unknown placeholders (e.g. ``null``, ``unknown``) are treated as missing,
    which naturally falls back to unfiltered global search.
    """
    if resolved_major and not _is_unknown_major(resolved_major):
        normalized_major = canonicalize_major_name(resolved_major)

        # If major is already a known code, use it directly.
        if normalized_major in MAJOR_CODE_TO_NAME:
            return normalized_major
        normalized_code = _normalise_major_text(normalized_major).upper()
        if normalized_code in MAJOR_CODE_TO_NAME:
            return normalized_code

        # If major is a known canonical name, resolve to major_code directly.
        code_by_name = _MAJOR_NAME_TO_CODE.get(normalized_major)
        if code_by_name:
            return code_by_name
        lowered_major = _normalise_major_text(normalized_major).casefold()
        for major_name, major_code in _MAJOR_NAME_TO_CODE.items():
            if _normalise_major_text(major_name).casefold() == lowered_major:
                return major_code

        # Otherwise treat it as a free-text name and run pattern matching.
        code = _extract_major_code(normalized_major)
        if code:
            return code
    # Fall back to current query regex detection.
    return _extract_major_code(query)


def _build_major_labels(major_code: str) -> List[str]:
    """Return all known labels/aliases for a major code (longest first)."""
    labels: List[str] = [major_code]
    major_name = MAJOR_CODE_TO_NAME.get(major_code)
    if major_name:
        labels.append(major_name)
        labels.extend(MAJOR_NAME_ALIAS_MAPPING.get(major_name, []))

    unique: List[str] = []
    seen: set[str] = set()
    for raw in labels:
        if _is_unknown_major(raw):
            continue
        value = _normalise_major_text(raw)
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)

    unique.sort(key=len, reverse=True)
    return unique


def _canonicalise_major_code_parts(prefix: str, suffix: str) -> str:
    """Convert regex major parts to canonical major code (e.g. MI+1 -> MI1)."""
    p = (prefix or "").upper()
    s = (suffix or "").upper()
    return f"{p}{s}" if s in {"1", "2"} else f"{p}-{s}"


def extract_major_codes(text: str) -> List[str]:
    """Extract unique explicit major codes in mention order from *text*."""
    normalized = _normalise_major_text(text or "")
    if not normalized:
        return []

    out: List[str] = []
    seen: set[str] = set()
    for match in _MAJOR_CODE_MENTION_RE.finditer(normalized):
        code = _canonicalise_major_code_parts(match.group(1), match.group(2))
        if code not in MAJOR_CODE_TO_NAME:
            continue
        key = code.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(code)
    return out


def _normalise_cohort_code(value: str) -> Optional[str]:
    """Normalize cohort text to canonical ``Kxx`` form, else ``None``."""
    normalized = _normalise_major_text(value or "")
    if not normalized:
        return None

    if re.fullmatch(r"\d{2,3}", normalized):
        return f"K{normalized}"

    match = re.fullmatch(r"K\s*(\d{2,3})", normalized, re.IGNORECASE)
    if match:
        return f"K{match.group(1)}"

    return None


def extract_cohort_codes(text: str) -> List[str]:
    """Extract unique cohort codes (``Kxx``) from *text* in mention order."""
    normalized = _normalise_major_text(text or "")
    if not normalized:
        return []

    out: List[str] = []
    seen: set[str] = set()
    for match in _COHORT_RE.finditer(normalized):
        num = match.group(1) or match.group(2)
        if not num:
            continue
        cohort = f"K{num}"
        key = cohort.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cohort)
    return out


def _extract_cohort_codes_from_hint(value: Optional[str]) -> List[str]:
    """Extract cohort codes from one hint value (profile/history/query signal)."""
    if value is None:
        return []

    raw = str(value).strip()
    if not raw or _is_unknown_major(raw):
        return []

    codes = extract_cohort_codes(raw)
    if codes:
        return codes

    maybe_cohort = _normalise_cohort_code(raw)
    return [maybe_cohort] if maybe_cohort else []


def strip_cohort_comparison_scaffold_for_retrieval(query: str) -> str:
    """Remove compare scaffolding/cohort mentions to keep topic-focused query."""
    raw_query = _normalise_major_text(query or "")
    if not raw_query:
        return raw_query

    cleaned = _COMPARE_HINT_RE.sub(" ", raw_query)
    cleaned = _COHORT_MENTION_RE.sub(" ", cleaned)
    cleaned = _COMPARE_CONNECTOR_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;:-()[]")
    cleaned = _TRAILING_FUNCTION_WORD_RE.sub("", cleaned).strip(" ,.;:-()[]")

    if len(cleaned.split()) < 2:
        return raw_query
    return cleaned


def build_cohort_comparison_subqueries_for_retrieval(
    query: str,
    *,
    max_subqueries: int = 3,
) -> List[str]:
    """Build per-cohort retrieval subqueries for cohort-comparison questions.

    Example:
        "so sánh quy định ngoại ngữ của K70 và K67"
        -> ["quy định ngoại ngữ cho K70", "quy định ngoại ngữ cho K67"]
    """
    raw_query = _normalise_major_text(query or "")
    if not raw_query:
        return []

    cohorts = extract_cohort_codes(raw_query)
    if len(cohorts) < 2 or not _COMPARE_HINT_RE.search(raw_query):
        return []

    topic_query = strip_cohort_comparison_scaffold_for_retrieval(raw_query)
    return [f"{topic_query} cho {cohort}" for cohort in cohorts[:max_subqueries]]


def strip_major_comparison_scaffold_for_retrieval(query: str) -> str:
    """Remove compare scaffolding/major mentions to keep topic-focused query."""
    raw_query = _normalise_major_text(query or "")
    if not raw_query:
        return raw_query

    cleaned = _COMPARE_HINT_RE.sub(" ", raw_query)
    cleaned = _COMPARE_FILLER_RE.sub(" ", cleaned)
    cleaned = _MAJOR_CODE_MENTION_RE.sub(" ", cleaned)
    cleaned = re.sub(
        r"\b(?:ngành|chuyên\s+ngành|chương\s+trình(?:\s+đào\s+tạo)?)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = _COMPARE_CONNECTOR_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;:-()[]")
    cleaned = _TRAILING_FUNCTION_WORD_RE.sub("", cleaned).strip(" ,.;:-()[]")

    if len(cleaned.split()) < 2:
        return raw_query
    return cleaned


def build_major_comparison_subqueries_for_retrieval(
    query: str,
    *,
    max_subqueries: int = 3,
) -> List[Tuple[str, str]]:
    """Build per-major retrieval subqueries for major-comparison questions.

    Example:
        "môn lập trình mạng của ngành IT-E7 và IT-E6 có gì khác nhau"
        -> [
             ("môn lập trình mạng của ngành IT-E7", "IT-E7"),
             ("môn lập trình mạng của ngành IT-E6", "IT-E6"),
           ]
    """
    raw_query = _normalise_major_text(query or "")
    if not raw_query:
        return []

    major_codes = extract_major_codes(raw_query)
    if len(major_codes) < 2 or not _COMPARE_HINT_RE.search(raw_query):
        return []

    topic_query = strip_major_comparison_scaffold_for_retrieval(raw_query)
    return [
        (f"{topic_query} của ngành {major_code}", major_code)
        for major_code in major_codes[:max_subqueries]
    ]


_GENERIC_WORDS = {
    "tôi", "mình", "em", "bạn", "chào", "xin",
    "muốn", "cần", "hỏi", "biết", "tìm", "hiểu", "xem",
    "thông", "tin", "chung", "chi", "tiết", "tổng", "quan", "giới", "thiệu",
    "về", "của", "cho", "trong", "thuộc",
    "là", "gì", "như", "thế", "nào", "ra", "sao", "ở", "đâu",
    "có", "những", "cái", "các",
    "vui", "lòng", "hãy",
    "ngành", "chuyên", "học", "chương", "trình", "đào", "tạo"
}

def strip_major_from_query_for_retrieval(
    query: str,
    resolved_major: Optional[str] = None,
) -> str:
    """Strip major-specific mentions once major filtering is already applied.

    Retrieval works better when semantic/keyword search focuses on the course
    intent (e.g. "môn mạng máy tính") while major constraints are handled by
    metadata filtering (e.g. ``major_code=IT-E6``).

    If stripping makes the query too short, the original query is returned.
    """
    raw_query = _normalise_major_text(query or "")
    if not raw_query:
        return raw_query

    major_code = _resolve_major_code(raw_query, resolved_major)
    if not major_code:
        return raw_query

    labels = _build_major_labels(major_code)
    if not labels:
        return raw_query

    label_group = "|".join(re.escape(label) for label in labels)
    cleaned = raw_query

    # Remove full phrases first to avoid leaving connector fragments.
    phrase_patterns = [
        rf"\b(?:trong|thuộc|cho|của)\s+ngành\s+(?:{label_group})\b",
        rf"\bngành\s+(?:{label_group})\b",
        rf"\bchuyên\s+ngành\s+(?:{label_group})\b",
        rf"\bchương\s+trình(?:\s+đào\s+tạo)?(?:\s+ngành)?\s+(?:{label_group})\b",
        rf"\((?:{label_group})\)",
        rf"\b(?:{label_group})\b",
    ]
    for pattern in phrase_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # Cleanup leftovers after label removal.
    cleaned = re.sub(
        r"\b(?:trong|thuộc|cho|của)\s+ngành\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:ngành|chuyên\s+ngành)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;:-()[]")

    # Keep the original query if stripping removed too much context.
    if len(cleaned.split()) < 2:
        return raw_query

    words = re.findall(r'\w+', cleaned.lower())
    non_generic = [w for w in words if w not in _GENERIC_WORDS]
    if len(non_generic) < 1:
        return raw_query

    return cleaned


def expand_major_in_query_for_reranking(
    query: str,
    resolved_major: Optional[str] = None,
) -> str:
    """Replace major codes with their full names to improve reranker scores.
    
    Cross-encoders (like BGE) are trained on general text and often assign
    very low relevance scores to pairs where the query uses an internal code
    (e.g., "IT1") but the document uses the full name ("Khoa học máy tính").
    """
    raw_query = _normalise_major_text(query or "")
    if not raw_query:
        return raw_query

    major_code = _resolve_major_code(raw_query, resolved_major)
    if not major_code:
        return raw_query

    major_name = MAJOR_CODE_TO_NAME.get(major_code)
    if not major_name:
        return raw_query

    if major_name.lower() in raw_query.lower():
        return raw_query

    labels = _build_major_labels(major_code)
    expanded = raw_query
    
    replaced = False
    for label in labels:
        if label.lower() in expanded.lower():
            # Use regex to avoid replacing inside words, though codes usually stand alone.
            pattern = re.compile(rf"\b{re.escape(label)}\b", re.IGNORECASE)
            # If the boundary regex doesn't match because of weird spacing, 
            # fall back to a direct replace
            if pattern.search(expanded):
                expanded = pattern.sub(major_name, expanded)
                replaced = True
                break
            else:
                # Direct string replace fallback (case-insensitive)
                pattern = re.compile(re.escape(label), re.IGNORECASE)
                expanded = pattern.sub(major_name, expanded)
                replaced = True
                break

    # Do not append the major name if it was successfully stripped, 
    # as appending it hurts reranking scores for specific syllabus chunks 
    # that only contain course names without mentioning the major.

    return expanded


def _term_any_mapping(field: str, value: str) -> Dict[str, Any]:
    """ES exact term query compatible with both field-mapping variants.

    Supports:
      - ``field`` is ``keyword``
      - ``field`` is ``text`` with ``field.keyword`` subfield
    """
    return {
        "bool": {
            "should": [
                {"term": {field: value}},
                {"term": {f"{field}.keyword": value}},
            ],
            "minimum_should_match": 1,
        }
    }


def _term_any_mapping_multi(field: str, values: List[str]) -> Dict[str, Any]:
    """ES exact-term query for one-of-many values, mapping-compatible."""
    clauses: List[Dict[str, Any]] = []
    for value in values:
        clauses.append({"term": {field: value}})
        clauses.append({"term": {f"{field}.keyword": value}})

    return {
        "bool": {
            "should": clauses,
            "minimum_should_match": 1,
        }
    }


def _wildcard_any_mapping(field: str, pattern: str) -> Dict[str, Any]:
    """ES wildcard query compatible with both field and field.keyword."""
    return {
        "bool": {
            "should": [
                {"wildcard": {field: pattern}},
                {"wildcard": {f"{field}.keyword": pattern}},
            ],
            "minimum_should_match": 1,
        }
    }


def _null_clause(field: str) -> Dict[str, Any]:
    """ES clause matching documents where *field* is absent."""
    return {"bool": {"must_not": {"exists": {"field": field}}}}


def _null_or_term(field: str, value: str) -> Dict[str, Any]:
    """ES query: exact term match OR field is absent."""
    return {
        "bool": {
            "should": [
                _term_any_mapping(field, value),
                _null_clause(field),
            ],
            "minimum_should_match": 1,
        }
    }


def _null_or_terms(field: str, values: List[str]) -> Dict[str, Any]:
    """ES query: any exact term in *values* OR field is absent."""
    return {
        "bool": {
            "should": [
                _term_any_mapping_multi(field, values),
                _null_clause(field),
            ],
            "minimum_should_match": 1,
        }
    }


def _match_only(field: str, value: str) -> Dict[str, Any]:
    """ES fuzzy match-only query (without null fallback)."""
    return {"match": {field: {"query": value, "fuzziness": "AUTO"}}}


def _null_or_match(field: str, value: str) -> Dict[str, Any]:
    """ES query: ``field`` contains *value* (fuzzy match) OR field is absent."""
    return {
        "bool": {
            "should": [
                _match_only(field, value),
                _null_clause(field),
            ],
            "minimum_should_match": 1,
        }
    }


# ─── Collection-specific extractors ─────────────────────────────────────────────


class CtdtFilterExtractor(BaseFilterExtractor):
    """Filter *ctdt* by major-specific queries first, then generic chunks.

    Fallback order:
      1. ``major_code`` exact.
      2. ``major_name`` fuzzy match.
      3. ``major_code`` exact OR ``major_code`` missing (generic chunks).
      4. No filter (all chunks) when all above return zero hits.
    """

    def extract(
        self,
        query: str,
        resolved_major: Optional[str] = None,
        resolved_cohort: Optional[str] = None,  # noqa: ARG002
    ) -> CollectionFilter:
        major_code = _resolve_major_code(query, resolved_major)
        if not major_code:
            return CollectionFilter()

        major_name = MAJOR_CODE_TO_NAME.get(major_code, "")
        queries: List[Dict[str, Any]] = [
            # First try: exact major_code match only (most precise)
            _term_any_mapping("major_code", major_code),
        ]
        if major_name:
            # Fallback: fuzzy match on major_name (without null-expansion)
            queries.append(_match_only("major_name", major_name))

        # Late fallback: include generic chunks with missing major_code.
        queries.append(_null_or_term("major_code", major_code))

        return CollectionFilter(metadata_es_queries=queries)


class QuyDinhFilterExtractor(BaseFilterExtractor):
    """Filter *quydinh* by cohort-specific ``applicable_major`` first.

    ``applicable_major`` stores cohort codes as a list (e.g.
    ``["K63", "K64"]``). Elasticsearch ``term`` queries naturally match
    list-valued keyword fields when one element matches exactly.

    Fallback order:
          1. ``applicable_major`` exact (one or more cohorts) OR missing.
          2. No filter (all chunks) when no cohort signal is available.
    """

    def extract(
        self,
        query: str,
        resolved_major: Optional[str] = None,
        resolved_cohort: Optional[str] = None,
    ) -> CollectionFilter:
        cohort_codes = extract_cohort_codes(query)
        if not cohort_codes:
            cohort_codes = _extract_cohort_codes_from_hint(resolved_cohort)
        if not cohort_codes:
            cohort_codes = _extract_cohort_codes_from_hint(resolved_major)

        if not cohort_codes:
            return CollectionFilter()

        return CollectionFilter(
            metadata_es_queries=[
                _null_or_terms("applicable_major", cohort_codes),
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
        resolved_cohort: Optional[str] = None,  # noqa: ARG002
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
            return _wildcard_any_mapping("date_str", f"*/{month}/{year}")

        # Year only: "năm 2025", "nam 2025", bare "2025"
        m2 = re.search(r"(?:n[aă]m\s*)?(20\d{2})\b", query, re.IGNORECASE)
        if m2:
            year = int(m2.group(1))
            # Matches any date_str ending with "/{year}"
            return _wildcard_any_mapping("date_str", f"*/{year}")

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
    resolved_cohort: Optional[str] = None,
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
        resolved_cohort: Cohort string resolved from user profile / conversation
            history (e.g. ``"70"`` or ``"K70"``).

    Returns:
        ``{collection_name: CollectionFilter}`` — ``is_empty`` values mean no
        pre-filter for that collection.
    """
    result: Dict[str, CollectionFilter] = {}
    for col in collections:
        extractor = _COLLECTION_FILTER_REGISTRY.get(col)
        result[col] = (
            extractor.extract(
                query=query,
                resolved_major=resolved_major,
                resolved_cohort=resolved_cohort,
            )
            if extractor is not None
            else CollectionFilter()
        )
    return result
