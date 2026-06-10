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
    - quydinh : applicable_cohort (cohort Kxx) OR missing (generic chunks)
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

    ``sort_by_date_desc``: when True and ``metadata_es_queries`` is empty,
    ``MultiCollectionSearch`` will fetch the most-recent chunk IDs from ES
    (by ``date_str`` field) and use them as a hard ``HasIdCondition`` in
    Qdrant instead of running a wildcard/term filter.  This implements the
    "mới nhất" (latest) freshness mode for collections that index ``date_str``.
    Explicit date/month filters (populated ``metadata_es_queries``) take
    priority and suppress this flag.
    """

    metadata_es_queries: List[Dict[str, Any]] = field(default_factory=list)
    sort_by_date_desc: bool = False

    @property
    def is_empty(self) -> bool:
        """True when no pre-filter queries are defined (search all)."""
        return not self.metadata_es_queries


def _fold_vietnamese_text(value: str) -> str:
    """Return a lowercase accent-insensitive form for lightweight intent matching."""
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    return without_marks.replace("đ", "d").replace("Đ", "D").casefold()


_FRESHNESS_INTENT_RE = re.compile(
    r"\b(?:moi\s+nhat|gan\s+day|hien\s+tai|"
    r"ky\s+nay|ki\s+nay|hoc\s+ky\s+moi|hoc\s+ki\s+moi|"
    r"hoc\s+ky\s+toi|hoc\s+ki\s+toi|thong\s+bao\s+moi|"
    r"latest|recent|newest|current\s+semester)\b",
    re.IGNORECASE,
)


def has_freshness_intent(query: str) -> bool:
    """Return True when a query asks for the latest/current information."""
    return bool(_FRESHNESS_INTENT_RE.search(_fold_vietnamese_text(query or "")))


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
    "BF-E12": "Kỹ thuật thực phẩm (Chương trình tiên tiến)",
    "BF-E19": "Kỹ thuật sinh học (Chương trình tiên tiến)",
    "BF1": "Kỹ thuật Sinh học",
    "BF2": "Kỹ thuật Thực phẩm",
    "CH-E11": "Kỹ thuật Hóa dược (Chương trình tiên tiến)",
    "CH-E20": "Hóa học Mỹ phẩm (Chương trình tiên tiến)",
    "CH1": "Kỹ thuật Hóa học",
    "CH2": "Hóa học",
    "ED2": "Công nghệ giáo dục",
    "ED3": "Quản lý giáo dục",
    "ED5": "Tâm lý học công nghiệp và tổ chức",
    "EE-E18": "Hệ thống điện và năng lượng tái tạo (Chương trình tiên tiến)",
    "EE-E8": "Kỹ thuật Điều khiển - Tự động hóa (Chương trình tiên tiến)",
    "EE-EP": "Tin học công nghiệp và Tự động hóa (Chương trình Việt-Pháp PFIEV)",
    "EE1": "Kỹ thuật điện",
    "EE2": "Kỹ thuật Điều khiển - Tự động hóa",
    "EM-E13": "Phân tích kinh doanh (Chương trình tiên tiến)",
    "EM-E14": "Logistics và Quản lý chuỗi cung ứng (Chương trình tiên tiến)",
    "EM-E17": "Kế toán (Chương trình tiên tiến)",
    "EM1": "Quản lý năng lượng",
    "EM2": "Quản lý công nghiệp",
    "EM3": "Quản trị kinh doanh",
    "EM5": "Tài chính - Ngân hàng",
    "ET-E16": "Truyền thông số và Kỹ thuật đa phương tiện (Chương trình tiên tiến)",
    "ET-E4": "Kỹ thuật Điện tử - Viễn thông (Chương trình tiên tiến)",
    "ET-E5": "Kỹ thuật Y sinh (Chương trình tiên tiến)",
    "ET-E9": "Hệ thống nhúng thông minh và IoT (Chương trình tiên tiến)",
    "ET-LUH": "Điện tử-Viễn thông - ĐH Leibniz Hannover (Đức)",
    "ET1": "Điện tử và Viễn thông",
    "ET2": "Kỹ thuật Y sinh",
    "EV1": "Kỹ thuật Môi trường",
    "EV2": "Quản lý Tài nguyên và Môi trường",
    "FL1": "Tiếng Anh Khoa học Kỹ thuật và Công nghệ",
    "FL2": "Tiếng Anh Chuyên nghiệp Quốc tế",
    "FL3": "Tiếng Trung Khoa học và Công nghệ",
    "FL4": "Tiếng Hàn Khoa học và Công nghệ",
    "HE1": "Kỹ thuật Nhiệt",
    "IT-E10": "Khoa học Dữ liệu và Trí tuệ Nhân tạo",
    "IT-E15": "An toàn không gian số (Chương trình tiên tiến)",
    "IT-E6": "Công nghệ thông tin (Việt-Nhật) (Chương trình tiên tiến)",
    "IT-E7": "Công nghệ thông tin (Global ICT)",
    "IT-EP": "Công nghệ thông tin (Việt-Pháp) (Chương trình tiên tiến)",
    "IT1": "CNTT: Khoa học Máy tính",
    "IT2": "CNTT: Kỹ thuật máy tính",
    "ME-E1": "Kỹ thuật Cơ điện tử (Chương trình tiên tiến)",
    "ME-GU": "Cơ khí - Chế tạo máy - ĐH Griffith (Úc)",
    "ME-LUH": "Cơ điện tử - ĐH Leibniz Hannover (Đức)",
    "ME-NUT": "Cơ điện tử - ĐH Nagaoka (Nhật Bản)",
    "ME1": "Kỹ thuật Cơ điện tử",
    "ME2": "Kỹ thuật Cơ khí",
    "MI-E22": "Khoa học tính toán cho các hệ thống thông minh (CTTT)",
    "MI1": "Toán - Tin",
    "MI2": "Hệ thống thông tin quản lý",
    "MS-E3": "Khoa học và Kỹ thuật Vật liệu (Chương trình tiên tiến)",
    "MS1": "Kỹ thuật Vật liệu",
    "MS2": "Chương trình Kỹ thuật vi điện tử và công nghệ Nano",
    "MS3": "Công nghệ vật liệu polyme và compozit",
    "MS5": "Kỹ thuật in",
    "PH1": "Vật lý kỹ thuật",
    "PH2": "Kỹ thuật hạt nhân",
    "PH3": "Vật lý Y khoa",
    "TE-E2": "Kỹ thuật Ô tô (Chương trình tiên tiến)",
    "TE-EP": "Cơ khí hàng không (Chương trình Việt - Pháp PFIEV)",
    "TE1": "Kỹ thuật Ô tô",
    "TE2": "Kỹ thuật Cơ khí động lực",
    "TE3": "Kỹ thuật Hàng không",
    "TROY-IT": "Khoa học máy tính - ĐH Troy (Hoa Kỳ)",
    "TX1": "Công nghệ Dệt May",
}

# Major-code patterns: list of (regex_pattern, major_code) tuples.
# Patterns are tried in order; the first match wins.
# Add new programmes here — no other code needs to change.
MAJOR_PATTERNS: List[Tuple[str, str]] = [
    # SoICT
    (r"\bIT[-\s]?E10\b|khoa học dữ liệu|trí tuệ nhân tạo|\bDATA\b|data\s+ai|artificial intelligence", "IT-E10"),
    (r"\bIT[-\s]?E15\b|an toàn không gian số|cyber|bảo mật số", "IT-E15"),
    (r"\bIT[-\s]?E6\b|việt.{0,4}nhật|ICTVJ", "IT-E6"),
    (r"\bIT[-\s]?E7\b|toàn cầu|global ICT|ICTG", "IT-E7"),
    (r"\bIT[-\s]?EP\b|việt.?pháp|ICTFR", "IT-EP"),
    (r"\bTROY[-\s]?IT\b|\bTROY\b", "TROY-IT"),
    (r"\bIT[-\s]?1\b|khoa học máy tính", "IT1"),
    (r"\bIT[-\s]?2\b|kỹ thuật máy tính", "IT2"),
    # Toán - Tin
    (r"\bMI[-\s]?1\b|\btoán.?tin\b|toán ứng dụng", "MI1"),
    (r"\bMI[-\s]?2\b|hệ thống thông tin quản lý|\bMIS\b", "MI2"),
    # Cơ khí
    (r"\bME[-\s]?GU\b|Griffith|mechanical machine engineering", "ME-GU"),
    (r"\bME[-\s]?LUH\b|Leibniz|Hannover", "ME-LUH"),
    (r"\bME[-\s]?NUT\b|Nagaoka", "ME-NUT"),
    (r"\bTE[-\s]?EP\b|cơ khí hàng không|hàng không", "TE-EP"),
    (r"\bHE[-\s]?1\b|kỹ thuật nhiệt\b", "HE1"),
    (r"\bTX[-\s]?1\b|công nghệ dệt may|công nghệ dệt\b", "TX1"),
    (r"\bME[-\s]?1\b|kỹ thuật cơ điện tử\b", "ME1"),
    (r"\bME[-\s]?2\b|kỹ thuật cơ khí\b", "ME2"),
    # Điện - Điện tử
    (r"\bEE[-\s]?E18\b|hệ thống điện.*năng lượng tái tạo", "EE-E18"),
    (r"\bEE[-\s]?E8\b|điều khiển.*tự động.*(?:KSCLC|chất lượng cao)", "EE-E8"),
    (r"\bEE[-\s]?EP\b|tin học công nghiệp|điều khiển.*PFIEV", "EE-EP"),
    (r"\bEE[-\s]?1\b|kỹ thuật điện\b", "EE1"),
    (r"\bEE[-\s]?2\b|kỹ thuật điều khiển.*tự động hóa\b", "EE2"),
    (r"\bEV[-\s]?1\b|kỹ thuật môi trường\b", "EV1"),
    (r"\bEV[-\s]?2\b|quản lý tài nguyên", "EV2"),
    # Hóa và Khoa học sự sống
    (r"\bCH[-\s]?E11\b|hóa dược", "CH-E11"),
    (r"\bBF[-\s]?E12\b|thực phẩm.*tiên tiến", "BF-E12"),
    (r"\bCH[-\s]?1\b|kỹ thuật hóa học\b", "CH1"),
    (r"\bCH[-\s]?2\b|hóa học\b", "CH2"),
    (r"\bBF[-\s]?1\b|kỹ thuật sinh học\b", "BF1"),
    (r"\bBF[-\s]?2\b|kỹ thuật thực phẩm\b", "BF2"),
    # Vật liệu
    (r"\bMS[-\s]?E3\b|khoa học.*kỹ thuật vật liệu", "MS-E3"),
    (r"\bMS[-\s]?2\b|vi điện tử.*nano|công nghệ nano", "MS2"),
    (r"\bMS[-\s]?3\b|polyme.*compozit", "MS3"),
    (r"\bMS[-\s]?5\b|kỹ thuật in\b", "MS5"),
    (r"\bMS[-\s]?1\b|kỹ thuật vật liệu\b", "MS1"),
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
    "Kỹ thuật Sinh học": [
        "Kỹ thuật Sinh học",
        "BF1",
    ],
    "Kỹ thuật Thực phẩm": [
        "Kỹ thuật Thực phẩm",
        "BF2",
    ],
    "Kỹ thuật thực phẩm": [
        # NOTE: the bare "Kỹ thuật thực phẩm" alias is intentionally omitted — it
        # case-folds identically to BF2's "Kỹ thuật Thực phẩm" (standard programme),
        # so it could never win the case-insensitive match here and only added
        # ambiguity. Advanced programme stays reachable via the qualified alias / code.
        "Kỹ thuật thực phẩm tiên tiến",
        "BF-E12",
    ],
    "Kỹ thuật Hóa học": [
        "Kỹ thuật Hóa học",
        "CH1",
    ],
    "Hóa học": [
        "Hóa học",
        "CH2",
    ],
    "Kỹ thuật Hóa dược": [
        "Kỹ thuật Hóa dược",
        "CH-E11",
    ],
    "Kỹ thuật điện": [
        "Kỹ thuật điện",
        "EE1",
    ],
    "Kỹ thuật Điều khiển - Tự động hóa": [
        "Kỹ thuật Điều khiển - Tự động hóa",
        "Kỹ thuật Điều khiển và Tự động hóa",
        "EE2",
        "EE-E8",
    ],
    "Hệ thống điện và năng lượng tái tạo": [
        "Hệ thống điện và năng lượng tái tạo",
        "EE-E18",
    ],
    "Tin học công nghiệp và Tự động hóa": [
        "Tin học công nghiệp và Tự động hóa",
        "EE-EP",
        "PFIEV",
    ],
    "Kỹ thuật Môi trường": [
        "Kỹ thuật Môi trường",
        "EV1",
    ],
    "Quản lý Tài nguyên và Môi trường": [
        "Quản lý Tài nguyên và Môi trường",
        "EV2",
    ],
    "Kỹ thuật Nhiệt": [
        "Kỹ thuật Nhiệt",
        "HE1",
    ],
    "Kỹ thuật Cơ điện tử": [
        "Kỹ thuật Cơ điện tử",
        "ME1",
    ],
    "Kỹ thuật Cơ khí": [
        "Kỹ thuật Cơ khí",
        "ME2",
    ],
    "Cơ khí - Chế tạo máy - ĐH Griffith (Úc)": [
        "Cơ khí - Chế tạo máy - ĐH Griffith (Úc)",
        "Cơ khí Griffith",
        "Mechanical Machine Engineering",
        "ME-GU",
    ],
    "Cơ điện tử - ĐH Leibniz Hannover (Đức)": [
        "Cơ điện tử - ĐH Leibniz Hannover (Đức)",
        "Cơ điện tử LUH",
        "Leibniz Hannover",
        "ME-LUH",
    ],
    "Cơ điện tử - ĐH Nagaoka (Nhật Bản)": [
        "Cơ điện tử - ĐH Nagaoka (Nhật Bản)",
        "Cơ điện tử Nagaoka",
        "ME-NUT",
    ],
    "Kỹ thuật Vật liệu": [
        "Kỹ thuật Vật liệu",
        "MS1",
    ],
    "Kỹ thuật vi điện tử và công nghệ Nano": [
        "Kỹ thuật vi điện tử và công nghệ Nano",
        "Vi điện tử và công nghệ Nano",
        "MS2",
    ],
    "Công nghệ vật liệu polyme và compozit": [
        "Công nghệ vật liệu polyme và compozit",
        "Polyme và compozit",
        "MS3",
    ],
    "Kỹ thuật in": [
        "Kỹ thuật in",
        "MS5",
    ],
    "Khoa học và Kỹ thuật Vật liệu": [
        "Khoa học và Kỹ thuật Vật liệu",
        "KHKTVL",
        "MS-E3",
    ],
    "Cơ khí hàng không": [
        "Cơ khí hàng không",
        "TE-EP",
    ],
    "Khoa học máy tính - ĐH Troy (Hoa Kỳ)": [
        "Khoa học máy tính - ĐH Troy (Hoa Kỳ)",
        "TROY-IT",
        "Troy",
    ],
    "Công nghệ Dệt May": [
        "Công nghệ Dệt May",
        "TX1",
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
_MAJOR_CODE_PREFIX_RE = r"IT|MI|ME|EE|EV|CH|BF|MS|HE|TE|TX|TROY|ED|EM|ET|FL|PH"
_MAJOR_CODE_SUFFIX_RE = r"E22|E20|E19|E18|E17|E16|E15|E14|E13|E12|E11|E10|E9|E8|E7|E6|E5|E4|E3|E2|E1|EP|GU|LUH|NUT|IT|1|2|3|4|5"
_MAJOR_CODE_SEPARATOR_RE = r"\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]?\s*"
_MAJOR_CODE_FUZZY_RE = re.compile(
    rf"\b({_MAJOR_CODE_PREFIX_RE}){_MAJOR_CODE_SEPARATOR_RE}({_MAJOR_CODE_SUFFIX_RE})\b",
    re.IGNORECASE,
)

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
    rf"\b({_MAJOR_CODE_PREFIX_RE}){_MAJOR_CODE_SEPARATOR_RE}({_MAJOR_CODE_SUFFIX_RE})\b",
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

_MAJOR_NAME_TO_CODE: Dict[str, str] = {}
for major_code, major_name in MAJOR_CODE_TO_NAME.items():
    _MAJOR_NAME_TO_CODE.setdefault(major_name, major_code)


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
    explicit_codes = extract_major_codes(normalised_text)
    if explicit_codes:
        return explicit_codes[0]
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
        direct_code = _normalise_major_text(resolved_major).upper()
        if direct_code in MAJOR_CODE_TO_NAME:
            return direct_code

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
    for alias_name, aliases in MAJOR_NAME_ALIAS_MAPPING.items():
        alias_values = [alias_name, *aliases]
        if any(_normalise_major_text(value).casefold() == major_code.casefold() for value in alias_values):
            labels.extend(alias_values)

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
    return f"{p}{s}" if s in {"1", "2", "3", "4", "5"} else f"{p}-{s}"


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


_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


def _major_name_query_variants(name: str) -> list[str]:
    """Return practical name variants for code enrichment."""
    variants = [name]
    without_parentheses = re.sub(r"[()]", "", name)
    if without_parentheses != name:
        variants.append(re.sub(r"\s{2,}", " ", without_parentheses).strip())
    without_program_note = re.sub(r"\s*\([^)]*chương trình[^)]*\)", "", name, flags=re.IGNORECASE)
    if without_program_note != name:
        variants.append(without_program_note.strip())
        variants.append(re.sub(r"[()]", "", without_program_note).strip())
    without_cttt_note = re.sub(r"\s*\(CTTT\)", "", name, flags=re.IGNORECASE)
    if without_cttt_note != name:
        variants.append(without_cttt_note.strip())
    if ":" in name:
        variants.append(name.split(":", 1)[1].strip())
    return [v for v in dict.fromkeys(variants) if len(v) >= 4]


def enrich_major_references_for_query(query: str) -> str:
    """Add code/name pairs for HUST major references in retrieval queries.

    Examples:
      - ``IT1`` -> ``IT1 (CNTT: Khoa học Máy tính)``
      - ``Khoa học máy tính`` -> ``Khoa học máy tính (IT1)``

    The function is deterministic and intentionally conservative: URLs are
    protected, already-expanded references are skipped, and short ambiguous
    fragments such as plain ``CNTT`` are not expanded.
    """
    if not query:
        return query

    saved_urls: list[str] = []

    def _stash_url(match: re.Match[str]) -> str:
        placeholder = f"\x00URL{len(saved_urls)}\x00"
        saved_urls.append(match.group(0))
        return placeholder

    result = _URL_RE.sub(_stash_url, query)
    normalized_for_codes = _normalise_major_text(result)

    for code in extract_major_codes(normalized_for_codes):
        name = MAJOR_CODE_TO_NAME.get(code)
        if not name:
            continue
        if re.search(rf"\b{re.escape(code)}\s*\(", result, re.IGNORECASE):
            continue
        if re.search(rf"\({re.escape(code)}\)", result, re.IGNORECASE):
            continue
        if name.casefold() in result.casefold():
            continue
        code_pattern = re.escape(code).replace(r"\-", r"\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]?\s*")
        result = re.sub(
            rf"\b{code_pattern}\b",
            f"{code} ({name})",
            result,
            flags=re.IGNORECASE,
        )

    existing_codes = set(extract_major_codes(_normalise_major_text(result)))
    for code, name in sorted(MAJOR_CODE_TO_NAME.items(), key=lambda item: len(item[1]), reverse=True):
        if code in existing_codes:
            continue
        for variant in sorted(_major_name_query_variants(name), key=len, reverse=True):
            if re.search(rf"{re.escape(variant)}\s*\(\s*{re.escape(code)}\s*\)", result, re.IGNORECASE):
                break
            pattern = rf"(?<![\w]){re.escape(variant)}(?![\w])"
            if not re.search(pattern, result, re.IGNORECASE):
                continue
            result = re.sub(
                pattern,
                lambda match, c=code: f"{match.group(0)} ({c})",
                result,
                count=1,
                flags=re.IGNORECASE,
            )
            existing_codes.add(code)
            break

    for i, url in enumerate(saved_urls):
        result = result.replace(f"\x00URL{i}\x00", url)
    return result


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
    """Filter *quydinh* by cohort-specific ``applicable_cohort`` first.

    ``applicable_cohort`` stores cohort codes as a list (e.g.
    ``["K63", "K64"]``). Elasticsearch ``term`` queries naturally match
    list-valued keyword fields when one element matches exactly.

    Fallback order:
          1. ``applicable_cohort`` exact (one or more cohorts) OR missing.
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
                _null_or_terms("applicable_cohort", cohort_codes),
            ]
        )


class KeHoachFilterExtractor(BaseFilterExtractor):
    """Filter *kehoach* by date when query mentions a specific year / month.

    ``date_str`` format in the store: ``"D/M/YYYY"`` (e.g. ``"11/3/2026"``).

    Priority order:
      1. Explicit month/year in query → ES wildcard filter (``metadata_es_queries``).
      2. Freshness intent ("mới nhất", "gần đây", …) without explicit date →
         ``sort_by_date_desc=True``; ``MultiCollectionSearch`` fetches the most-
         recent chunk IDs from ES and uses them as a hard ``HasIdCondition``.
      3. No signal → empty filter; recency bonus (+0.05) still applies.
    """

    def extract(
        self,
        query: str,
        resolved_major: Optional[str] = None,  # noqa: ARG002
        resolved_cohort: Optional[str] = None,  # noqa: ARG002
    ) -> CollectionFilter:
        date_query = self._build_date_query(query)
        if date_query is not None:
            # Explicit date filter takes priority — no freshness sort needed
            return CollectionFilter(metadata_es_queries=[date_query])

        if has_freshness_intent(query):
            # No explicit date but user wants the latest docs
            return CollectionFilter(sort_by_date_desc=True)

        return CollectionFilter()

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
        # Strip school-year patterns (e.g., "2025-2026", "2025/2026", "năm học 2025-2026")
        # to avoid misinterpreting school years as specific calendar/posting years.
        clean_query = re.sub(
            r"n[aă]m\s*h[oọ]c\s*20\d{2}\s*[-\/]\s*(?:20)?\d{2}\b",
            " ",
            query,
            flags=re.IGNORECASE,
        )
        clean_query = re.sub(
            r"\b20\d{2}\s*[-\/]\s*(?:20)?\d{2}\b",
            " ",
            clean_query,
            flags=re.IGNORECASE,
        )
        clean_query = re.sub(
            r"\b20\d{2}\s*[\._\/-]\s*[123]\b|\b20\d{2}[123]\b",
            " ",
            clean_query,
            flags=re.IGNORECASE,
        )

        # Month + year: "tháng 3 2026", "thang 3 nam 2026", "3/2026", "03/2026"
        m = re.search(
            r"th[aá]ng\s*(\d{1,2})(?:\s+n[aă]m\s*|\s*/\s*)(\d{4})"
            r"|(\d{1,2})\s*/\s*(20\d{2})",
            clean_query,
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
        m2 = re.search(r"(?:n[aă]m\s*)?(20\d{2})\b", clean_query, re.IGNORECASE)
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

_DATE_STR_FRESHNESS_COLLECTIONS = {"kehoach", "quydinh"}


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
    freshness_intent = has_freshness_intent(query)
    for col in collections:
        extractor = _COLLECTION_FILTER_REGISTRY.get(col)
        cf = (
            extractor.extract(
                query=query,
                resolved_major=resolved_major,
                resolved_cohort=resolved_cohort,
            )
            if extractor is not None
            else CollectionFilter()
        )
        if (
            freshness_intent
            and col in _DATE_STR_FRESHNESS_COLLECTIONS
            and cf.is_empty
            and not cf.sort_by_date_desc
        ):
            cf = CollectionFilter(sort_by_date_desc=True)
        result[col] = cf
    return result
