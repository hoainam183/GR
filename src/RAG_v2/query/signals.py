"""Query-level traits used by routing and adaptive retrieval.

The helpers in this module are intentionally lightweight and deterministic.
They do not decide the final answer; they expose reusable signals such as
"this asks for a point/credit value" or "this needs personal eligibility data".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class QuerySignals:
    """Reusable query traits shared by router, selector, and retriever."""

    personal_reference: bool = False
    eligibility_check: bool = False
    exact_policy_lookup: bool = False
    table_lookup: bool = False
    procedural_support: bool = False
    multi_domain: bool = False
    freshness: bool = False

    def to_dict(self) -> Dict[str, bool]:
        """Return a plain dict suitable for route/search traces."""
        return asdict(self)


def fold_vietnamese_text(text: str) -> str:
    """Lowercase and remove Vietnamese accents for robust pattern matching."""
    value = unicodedata.normalize("NFD", text or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return value.replace("đ", "d").replace("Đ", "D").casefold()


def coerce_query_signals(value: QuerySignals | Mapping[str, Any] | None) -> QuerySignals:
    """Convert a dict-like signal payload back to ``QuerySignals``."""
    if isinstance(value, QuerySignals):
        return value
    if not value:
        return QuerySignals()
    allowed = QuerySignals.__dataclass_fields__.keys()
    return QuerySignals(**{key: bool(value.get(key)) for key in allowed})


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


_PERSONAL_PATTERNS = (
    r"\b(toi|minh|em|cua toi|nganh cua toi|chuong trinh cua toi|sinh vien nhu toi)\b",
    r"\b(hoc phan cua toi|diem cua toi|cpa cua toi|gpa cua toi)\b",
)

_ELIGIBILITY_PATTERNS = (
    r"\b(du dieu kien|dat dieu kien|co du dieu kien)\b",
    r"\bdieu kien\s+(?:xet|duoc xet|tot nghiep|nhan|cap|tham gia|dang ky)\b",
    r"\b(tot nghiep|xet tot nghiep|dang ky tot nghiep|cong nhan tot nghiep)\b",
    r"\b(chuan dau ra|ngoai ngu dau ra|gdtc|gdqp|giao duc the chat|quoc phong)\b",
    r"\b(?:duoc xet|xet)\s+(?:hoc bong|mien giam|tot nghiep)\b",
    r"\b(?:hoc bong|mien giam).{0,30}\b(?:du dieu kien|dat dieu kien|duoc xet)\b",
)

_EXACT_LOOKUP_PATTERNS = (
    r"\b(bao nhieu|may|muc nao|muc diem|thang diem|can bao nhieu)\b",
    r"\b(duoc bao nhieu|duoc may|cong bao nhieu|tinh bao nhieu)\b",
    r"\b(diem ren luyen|diem cong|tin chi|hoc phi|muc thu|xep loai|quy doi)\b",
)

_TABLE_LOOKUP_PATTERNS = (
    r"\b(bang|khung|phu luc|muc|thang diem|quy doi|xep loai)\b",
    r"\b(diem ren luyen|diem cong|tin chi|hoc phi|muc thu|chuan)\b",
    r"\b(thoi luong|ma hoc phan|co ma|ma\s+la gi|danh cho ai|xep hoc)\b",
    r"\b(hoc ky|ky)\s*\d+\b",
    r"\b(thuoc nhom|nhom\s*(?:may|\d+)|bac\s*\d+(?:\.\d+)?)\b",
    r"\bfl\d{4}\b",
)

_PROCEDURAL_PATTERNS = (
    r"\b(chua nhan|chua duoc|khong nhan|khong duoc|bi thieu|sai diem)\b",
    r"\b(minh chung|xac nhan|cap nhat|bo sung|nop|gui|lien he|bieu mau|form)\b",
    r"\b(khieu nai|phuc khao|kiem tra lai|hoi ai|lam sao|can lam gi)\b",
)

_FRESHNESS_PATTERNS = (
    r"\b(moi nhat|gan day|hom nay|sap toi|hien nay|nam nay|ky moi|hoc ky moi)\b",
    r"\b(vua ban hanh|cap nhat|thong bao moi)\b",
)

_PROGRAM_PATTERNS = (
    r"\b(nganh|chuong trinh|ctdt|chuong trinh dao tao|khoa|k\d{2,3})\b",
    r"\b(?:it|mi|et|em|ep|ee|ev|hs|fl|ba|ph|me|ms)-[a-z0-9]+\b",
)


def analyze_query_signals(query: str) -> QuerySignals:
    """Analyze a user query into stable retrieval/routing traits."""
    folded = fold_vietnamese_text(query)

    personal_reference = _matches_any(folded, _PERSONAL_PATTERNS)
    eligibility_check = _matches_any(folded, _ELIGIBILITY_PATTERNS)
    exact_policy_lookup = _matches_any(folded, _EXACT_LOOKUP_PATTERNS)
    table_lookup = _matches_any(folded, _TABLE_LOOKUP_PATTERNS)
    procedural_support = _matches_any(folded, _PROCEDURAL_PATTERNS)
    freshness = _matches_any(folded, _FRESHNESS_PATTERNS)

    has_program_context = _matches_any(folded, _PROGRAM_PATTERNS)
    graduation_rule = bool(
        re.search(r"\b(tot nghiep|xet tot nghiep|dieu kien)\b", folded)
        and re.search(r"\b(quy dinh|chuong trinh|nganh|ctdt|tin chi|mon|hoc phan)\b", folded)
    )
    multi_domain = bool(
        (eligibility_check and has_program_context)
        or (procedural_support and (exact_policy_lookup or table_lookup))
        or graduation_rule
    )

    return QuerySignals(
        personal_reference=personal_reference,
        eligibility_check=eligibility_check,
        exact_policy_lookup=exact_policy_lookup,
        table_lookup=table_lookup,
        procedural_support=procedural_support,
        multi_domain=multi_domain,
        freshness=freshness,
    )


_TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ỹĐđ]+(?:[-_][0-9A-Za-zÀ-ỹĐđ]+)*")
_STOPWORDS = {
    "a",
    "ai",
    "anh",
    "bao",
    "ban",
    "bi",
    "cai",
    "can",
    "cho",
    "chua",
    "co",
    "cua",
    "da",
    "de",
    "duoc",
    "em",
    "gi",
    "gom",
    "hay",
    "khong",
    "la",
    "lam",
    "minh",
    "nao",
    "neu",
    "nhung",
    "nhu",
    "nhung",
    "nhiu",
    "nhieu",
    "phai",
    "thi",
    "toi",
    "trong",
    "va",
    "ve",
}


def _content_spans(query: str) -> List[List[str]]:
    spans: List[List[str]] = []
    current: List[str] = []
    for token in _TOKEN_RE.findall(query or ""):
        folded = fold_vietnamese_text(token)
        if folded in _STOPWORDS or len(folded) <= 1:
            if current:
                spans.append(current)
                current = []
            continue
        current.append(token)
    if current:
        spans.append(current)
    return spans


def extract_key_phrases(query: str, max_phrases: int = 8) -> List[str]:
    """Extract phrase candidates for phrase-aware BM25 boosting.

    Phrases are derived from content-token spans split at stopwords. This keeps
    exact phrases such as "hiến máu" and "điểm rèn luyện" without hardcoding
    any specific answer case.
    """
    phrases: List[str] = []
    seen: set[str] = set()
    for span in _content_spans(query):
        upper_n = min(4, len(span))
        for n in range(upper_n, 1, -1):
            for start in range(0, len(span) - n + 1):
                phrase = " ".join(span[start : start + n]).strip()
                key = fold_vietnamese_text(phrase)
                if key and key not in seen:
                    seen.add(key)
                    phrases.append(phrase)

    phrases.sort(key=lambda value: (len(value.split()), len(value)), reverse=True)
    return phrases[:max_phrases]
