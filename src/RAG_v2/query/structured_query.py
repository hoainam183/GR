"""Structured query extraction for retrieval-time controls.

This module intentionally stays deterministic.  It extracts only signals that
are cheap and safe to use before retrieval: course codes, major codes, cohorts,
and explicit exclusion terms such as "khong bao gom X".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

_DASH_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)

_COURSE_CODE_RE = re.compile(
    r"\b(?:IT|MI|EE|ET|ME|CH|PH|MA|TL|FL|PE|ED|JP|EM|BF|TEX)\s*-?\s*\d{4}[A-Z]?\b",
    re.IGNORECASE,
)
_MAJOR_CODE_RE = re.compile(
    r"\b(IT|MI|ET|EM|EP|EE|EV|HS|FL|BA|PH|ME|CH|BF|MS|HE|TE|TX|TROY)\s*-?\s*(E\d{1,2}|EP|GU|LUH|NUT|IT|\d{1,2})\b",
    re.IGNORECASE,
)
_COHORT_RE = re.compile(
    r"\bk\s*(\d{2,3})\b|kh[oó]a\s*k?\s*(\d{2,3})",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    r"\b(?:khong\s+(?:bao\s+gom|gom|tinh|lay|xet)|"
    r"ngoai\s+tru|loai\s+tru|tru)\s+(?P<term>[^,.;?!]+)",
    re.IGNORECASE,
)
_TERM_STOP_RE = re.compile(
    r"\b(?:nhung|thi|khi|neu|neu\s+nhu|vay|ve|trong|cho|ap\s+dung)\b",
    re.IGNORECASE,
)
_LEADING_TERM_NOISE_RE = re.compile(
    r"^(?:cac|nhung|mot)\s+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StructuredQuery:
    """Deterministic slots used by retrieval and evaluation tooling."""

    original_query: str
    normalized_query: str
    course_codes: List[str] = field(default_factory=list)
    major_codes: List[str] = field(default_factory=list)
    cohorts: List[str] = field(default_factory=list)
    exclude_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_query_text(value: str) -> str:
    """Normalize Unicode/dash/spacing variants without removing accents."""
    text = unicodedata.normalize("NFKC", value or "")
    text = text.translate(_DASH_TRANSLATION)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def strip_diacritics(value: str) -> str:
    """Return lowercase text without Vietnamese diacritics for robust matching."""
    decomposed = unicodedata.normalize("NFD", value or "")
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    stripped = stripped.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFC", stripped).lower()


def _dedup(values: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _canonical_course_code(raw: str) -> str:
    return re.sub(r"[\s-]+", "", raw or "").upper()


def _canonical_major_code(match: re.Match[str]) -> str:
    prefix = match.group(1).upper()
    suffix = match.group(2).upper()
    return f"{prefix}{suffix}" if suffix in {"1", "2"} else f"{prefix}-{suffix}"


def _clean_exclude_term(raw: str) -> str:
    text = strip_diacritics(raw)
    text = _TERM_STOP_RE.split(text, maxsplit=1)[0]
    text = re.sub(r"\s{2,}", " ", text).strip(" -:()[]{}'\"")
    text = _LEADING_TERM_NOISE_RE.sub("", text).strip()
    words = text.split()
    if len(words) > 8:
        text = " ".join(words[:8])
    return text


def parse_structured_query(query: str) -> StructuredQuery:
    """Extract stable retrieval slots from a natural-language query."""
    normalized = normalize_query_text(query)
    accentless = strip_diacritics(normalized)

    course_codes = _dedup(
        [_canonical_course_code(match.group(0)) for match in _COURSE_CODE_RE.finditer(normalized)]
    )
    major_codes = _dedup(
        [_canonical_major_code(match) for match in _MAJOR_CODE_RE.finditer(normalized)]
    )

    cohorts: List[str] = []
    for match in _COHORT_RE.finditer(normalized):
        value = match.group(1) or match.group(2)
        if value:
            cohorts.append(f"K{value}")

    exclude_terms = _dedup(
        [
            term
            for term in (
                _clean_exclude_term(match.group("term"))
                for match in _NEGATION_RE.finditer(accentless)
            )
            if len(term) >= 2
        ]
    )

    return StructuredQuery(
        original_query=query,
        normalized_query=normalized,
        course_codes=course_codes,
        major_codes=major_codes,
        cohorts=_dedup(cohorts),
        exclude_terms=exclude_terms,
    )


def text_contains_excluded_term(text: str, exclude_terms: List[str]) -> bool:
    """Accent-insensitive substring check for post-vector filtering."""
    if not exclude_terms:
        return False
    haystack = strip_diacritics(text)
    return any(
        (needle := strip_diacritics(term)) and needle in haystack
        for term in exclude_terms
    )


def build_es_must_not_clauses(exclude_terms: List[str]) -> List[Dict[str, Any]]:
    """Build Elasticsearch must_not clauses for explicit exclusion terms."""
    clauses: List[Dict[str, Any]] = []
    for term in exclude_terms:
        cleaned = _clean_exclude_term(term)
        if not cleaned:
            continue
        clauses.append(
            {
                "multi_match": {
                    "query": cleaned,
                    "fields": ["text^1.0", "title^1.5", "course_name^2.0"],
                    "type": "phrase",
                }
            }
        )
        if _COURSE_CODE_RE.fullmatch(cleaned):
            clauses.append({"term": {"course_code": _canonical_course_code(cleaned)}})
    return clauses
