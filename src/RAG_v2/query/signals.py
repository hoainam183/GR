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
    schedule_intent: bool = False
    deadline_intent: bool = False
    announcement_intent: bool = False
    curriculum_semester_intent: bool = False

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
    r"\b(?:cua\s+toi|cua\s+minh|cua\s+em)\b",
    r"\b(?:nganh|chuong\s+trinh|hoc\s+phan|diem|cpa|gpa|khoa|truong)\s+(?:cua\s+)?(?:toi|minh|em)\b",
    r"\b(?:toi|minh|em)\s+(?:hoc\s+nganh|la\s+sinh\s+vien)\b",
    r"\bsinh\s+vien\s+nhu\s+(?:toi|minh|em)\b",
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
    r"\b(?:mon|hoc\s+phan|chuong\s+trinh|khung|bang|dao\s+tao).{0,30}\b(?:hoc\s+ky|ky)\s*\d+\b",
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

_SCHEDULE_PATTERNS = (
    r"\b(lich thi|lich hoc|lich dang ky|lich trinh|thoi khoa bieu|dot dang ky|dot mo lop|mo dang ky)\b",
    r"\b(lich|thoi gian|khi nao|bao gio|luc nao|ngay nao|dot)\b.{0,50}\b(thi|hoc|dang ky|mo lop|nop|bao ve|nhan bang|phuc khao|ktx|hoc phi)\b",
    r"\b(hoc ky|hoc ki|ky|ki)\s*(?:moi|toi|nay|he|sap toi|gan nhat|moi nhat)\b",
)

_DEADLINE_PATTERNS = (
    r"\b(deadline|han|het han|thoi han|ngay cuoi|chot|dong cong|mo cong)\b",
    r"\b(nop|dang ky|dong hoc phi|phuc khao).{0,40}\b(den khi nao|bao gio het han|het han|deadline|han)\b",
)

_ANNOUNCEMENT_PATTERNS = (
    r"\b(thong bao|tin tuc|bai viet|danh sach|cong bo|ket qua|trieu tap|nhac lich)\b",
    r"\bdanh sach.{0,30}\b(nhan|duoc nhan|sinh vien|hoc bong)\b",
)

_PROGRAM_PATTERNS = (
    r"\b(nganh|chuong trinh|ctdt|chuong trinh dao tao|khoa|k\d{2,3})\b",
    r"\b(?:it|mi|et|em|ep|ee|ev|hs|fl|ba|ph|me|ms)-[a-z0-9]+\b",
)

# ── Curriculum semester placement ("môn X học/đăng ký vào kỳ mấy?") ───────────
# Distinguishes WHICH-semester-in-curriculum (ctdt) from WHEN-registration-opens
# (kehoach). The question must reference a course AND ask which semester, while
# NOT carrying any "when does it open / schedule / deadline" time markers.
_COURSE_REFERENCE_PATTERNS = (
    r"\b(mon|hoc phan|mon hoc|hp)\b",
    r"\b(?:it|mi|ee|et|me|ch|ph|ma|tl|fl|pe|ed|jp|em|bf|tex)\s*-?\s*\d{4}[a-z]?\b",
)
_SEMESTER_PLACEMENT_PATTERNS = (
    r"\b(?:hoc\s*ky|hoc\s*ki|hki|hk|ky|ki)\s*(?:thu\s*)?(?:may|nao|bao nhieu)\b",
    r"\b(?:may|thu may)\s*(?:hoc\s*ky|hoc\s*ki|ky|ki)\b",
)
# Markers that make the question a WHEN-registration / schedule query (→ kehoach),
# which must SUPPRESS the curriculum-placement signal even if "kỳ mấy" appears.
_WHEN_OPENING_PATTERNS = (
    r"\b(khi nao|bao gio|luc nao|ngay nao|may gio|thoi gian|thoi diem)\b",
    r"\b(lich|deadline|han\s+(?:dang ky|nop|cuoi)|het han|chot|mo cong)\b",
    r"\b(mo|bat dau|ket thuc|dong)\s+(?:dang ky|dang ki|cong|lop)\b",
    r"\bdot\s+(?:dang ky|dang ki|\d|mo lop)\b",
    r"\b(con slot|con cho|con lop|con bao nhieu|con\s+\w+\s+lop)\b",
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
    schedule_intent = _matches_any(folded, _SCHEDULE_PATTERNS)
    deadline_intent = _matches_any(folded, _DEADLINE_PATTERNS)
    announcement_intent = _matches_any(folded, _ANNOUNCEMENT_PATTERNS)

    # Curriculum semester placement: "môn X học/đăng ký vào kỳ mấy?" asks WHICH
    # semester a course sits in the standard study plan (ctdt), not WHEN
    # registration opens (kehoach). Requires a course reference + a which-semester
    # question, and is suppressed by any WHEN-opening / schedule / deadline marker.
    curriculum_semester_intent = bool(
        _matches_any(folded, _COURSE_REFERENCE_PATTERNS)
        and _matches_any(folded, _SEMESTER_PLACEMENT_PATTERNS)
        and not _matches_any(folded, _WHEN_OPENING_PATTERNS)
    )

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
        schedule_intent=schedule_intent,
        deadline_intent=deadline_intent,
        announcement_intent=announcement_intent,
        curriculum_semester_intent=curriculum_semester_intent,
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
