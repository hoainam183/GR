# Collection-Specific Keyword Boosting — Design Plan

## 1. Tổng quan kiến trúc

```
ElasticsearchStore.keyword_search(query, collection_name, ...)
        │
        ▼
CollectionQueryBuilder.build(collection_name, query)
        │   ├── CtdtQueryBuilder       → boost course_code, course_name
        │   ├── QuyDinhQueryBuilder    → boost article, regulation_type, cohort
        │   ├── KeHoachQueryBuilder    → boost event_type, date, semester
        │   └── StsvQueryBuilder       → boost form_type, procedure_name
        │
        ▼
ES Query DSL  →  Elasticsearch  →  BM25 results
```

Nguyên tắc thiết kế:
- **Module riêng** `collection_query_builder.py` — tách biệt logic boosting khỏi store
- **Registry pattern** — giống `metadata_filters.py`, thêm collection mới không cần sửa file khác
- **ElasticsearchStore** nhận thêm param `collection_name` trong `keyword_search()` và delegate sang builder
- Backward-compatible: nếu `collection_name=None` → fallback query hiện tại

---

## 2. ES Index Mapping mới cho từng collection

### 2.1 `ctdt` — Curriculum / Courses (thiết kế mới hoàn toàn)

```python
CTDT_EXTRA_FIELDS = {
    # Exact match fields — keyword type for filtering & boosting
    "course_code":   {"type": "keyword"},          # "IT3080", "IT4015E"
    "course_type":   {"type": "keyword"},           # "bat_buoc" | "tu_chon" | "co_so_nganh"

    # Full-text fields — dùng cho fuzzy search
    "course_name": {
        "type": "text",
        "analyzer": text_analyzer,
        "fields": {"keyword": {"type": "keyword"}}, # cho exact boost
    },
    "prerequisites":  {"type": "text", "analyzer": text_analyzer},  # "IT1003, IT2040"
    "corequisites":   {"type": "text", "analyzer": text_analyzer},
    "department":     {"type": "keyword"},          # "Khoa CNTT", "Khoa Toán"

    # Numeric
    "credits":        {"type": "integer"},          # 3, 4, ...
}
```

**Lý do:** Course code là identifier quan trọng nhất — query "IT3080" phải hit exact match với boost cực cao. Course name cần cả text (fuzzy) lẫn keyword subfield (exact phrase boost).

---

### 2.2 `quydinh` — Regulations (bổ sung thêm)

```python
QUYDINH_EXTRA_FIELDS = {
    # Đã có: applicable_major (keyword list)
    # Thêm mới:
    "regulation_type": {"type": "keyword"},
    # Values: "hoc_bong" | "ngoai_ngu" | "diem_ren_luyen" | "tot_nghiep" | "khac"

    "article_number": {"type": "keyword"},          # "48", "12" — số điều
    "chapter":        {"type": "keyword"},           # "III", "2"
}
```

---

### 2.3 `kehoach` — Plans / Schedules (bổ sung thêm)

```python
KEHOACH_EXTRA_FIELDS = {
    # Đã có: date_str (keyword)
    # Thêm mới:
    "event_type": {"type": "keyword"},
    # Values: "xet_hoc_bong" | "dang_ky_hoc_tap" | "thi_lai" | "nop_don" | "khac"

    "semester":       {"type": "keyword"},          # "HK1", "HK2", "HKhe"
    "academic_year":  {"type": "keyword"},          # "2024-2025"
}
```

---

### 2.4 `stsv` — Student Services / Forms (bổ sung thêm)

```python
STSV_EXTRA_FIELDS = {
    "form_type": {"type": "keyword"},
    # Values: "bieu_mau" | "huong_dan" | "thong_bao" | "quy_trinh"

    "procedure_name": {
        "type": "text",
        "analyzer": text_analyzer,
        "fields": {"keyword": {"type": "keyword"}},
    },
    # "Xin miễn giảm học phí", "Đăng ký học lại"
}
```

---

## 3. Module `collection_query_builder.py`

### 3.1 Cấu trúc file

```
retrieval/
├── collection_query_builder.py   ← NEW
├── elasticsearch_store.py        ← sửa keyword_search()
├── metadata_filters.py
└── ...
```

### 3.2 Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BaseQueryBuilder(ABC):
    """Build collection-specific ES query DSL with field boosting."""

    @abstractmethod
    def build(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a complete ES search body dict."""
        ...
```

### 3.3 CtdtQueryBuilder — chi tiết boost

| Tín hiệu trong query | Field boost | Boost value | Ghi chú |
|---|---|---|---|
| Mã môn exact (`IT3080`) | `course_code` term | **200.0** | Highest — identifier |
| Mã môn trong text | `text` match_phrase | 50.0 | Đã có trong query |
| Tên môn exact phrase | `course_name.keyword` | 100.0 | "mạng máy tính" quoted |
| Tên môn fuzzy | `course_name` | 10.0 | multi_match |
| Title | `title` | 5.0 | hiện tại 1.5 |
| Text BM25 | `text` | 1.0 | baseline |
| `tín chỉ`, `credits` hint | `credits` exists filter | +30.0 constant | boost chunk có số tín |
| `tiên quyết` hint | `prerequisites` match | +20.0 | |
| `song hành` hint | `corequisites` match | +20.0 | |

**Regex detect course code:**
```python
_COURSE_CODE_RE = re.compile(
    r"\b(?:IT|MI|EE|ET|ME|CH|PH|MA|FL|PE)\s*\d{3,4}[A-Z]?\b",
    re.IGNORECASE
)
```

**Logic build query cho ctdt:**
```python
def build(self, query, top_k=20, filters=None):
    must = [self._base_multi_match(query)]
    should = [self._phrase_boost(query)]

    # 1. Detect course codes → exact term boost
    codes = self._extract_course_codes(query)
    for code in codes:
        should.append({
            "term": {"course_code": {"value": code.upper(), "boost": 200.0}}
        })
        should.append({
            "match_phrase": {"text": {"query": code, "boost": 50.0}}
        })

    # 2. Quoted phrase → boost course_name.keyword
    for phrase in self._extract_quoted(query):
        should.append({
            "match_phrase": {
                "course_name": {"query": phrase, "boost": 100.0}
            }
        })

    # 3. Keyword hints → boost specific fields
    lowered = query.lower()
    if any(w in lowered for w in ["tiên quyết", "tien quyet", "điều kiện tiên"]):
        should.append({
            "exists": {"field": "prerequisites"},  # prefer chunks có field này
        })
        should.append({
            "match": {"prerequisites": {"query": query, "boost": 20.0}}
        })
    if any(w in lowered for w in ["song hành", "song hanh"]):
        should.append({
            "match": {"corequisites": {"query": query, "boost": 20.0}}
        })
    if any(w in lowered for w in ["tín chỉ", "tin chi", "số tín"]):
        should.append({
            "constant_score": {
                "filter": {"exists": {"field": "credits"}},
                "boost": 30.0
            }
        })

    return self._wrap(must, should, filters, top_k)
```

---

### 3.4 QuyDinhQueryBuilder — chi tiết boost

| Tín hiệu | Field | Boost | Ghi chú |
|---|---|---|---|
| "Điều X" / "Khoản Y" | `article_number` term | 150.0 | Exact article ref |
| "học bổng" | `regulation_type=hoc_bong` | 80.0 | constant_score |
| "ngoại ngữ", "tiếng anh" | `regulation_type=ngoai_ngu` | 80.0 | |
| "điểm rèn luyện" | `regulation_type=diem_ren_luyen` | 80.0 | |
| "K70", "K67" (cohort) | `applicable_major` term | 60.0 | |
| Title phrase | `title` match_phrase | 5.0 | |
| Text BM25 | `text` | 1.0 | |

**Logic:**
```python
# Detect "Điều X" → boost article_number
article_match = re.search(r"Điều\s+(\d+)", query, re.IGNORECASE)
if article_match:
    should.append({
        "term": {
            "article_number": {
                "value": article_match.group(1),
                "boost": 150.0
            }
        }
    })

# Detect regulation type keywords
REGULATION_TYPE_HINTS = {
    "hoc_bong":        ["học bổng", "hoc bong", "xét học bổng"],
    "ngoai_ngu":       ["ngoại ngữ", "tiếng anh", "ielts", "toeic", "b1", "b2"],
    "diem_ren_luyen":  ["rèn luyện", "ren luyen", "điểm rl"],
    "tot_nghiep":      ["tốt nghiệp", "tot nghiep", "xét tốt nghiệp"],
}
for reg_type, hints in REGULATION_TYPE_HINTS.items():
    if any(h in lowered for h in hints):
        should.append({
            "constant_score": {
                "filter": {"term": {"regulation_type": reg_type}},
                "boost": 80.0
            }
        })

# Detect cohort Kxx → boost applicable_major
cohort_codes = extract_cohort_codes(query)  # reuse từ metadata_filters
for cohort in cohort_codes:
    should.append({
        "term": {"applicable_major": {"value": cohort, "boost": 60.0}}
    })
```

---

### 3.5 KeHoachQueryBuilder — chi tiết boost

| Tín hiệu | Field | Boost | Ghi chú |
|---|---|---|---|
| "học bổng", "xét học bổng" | `event_type=xet_hoc_bong` | 100.0 | |
| "đăng ký học tập", "đkht" | `event_type=dang_ky_hoc_tap` | 100.0 | |
| "HK1", "kỳ 1", "học kỳ 1" | `semester=HK1` term | 80.0 | |
| "2025", "2026" (năm) | `academic_year` wildcard | 60.0 | |
| "tháng 3", "3/2026" | `date_str` wildcard | 80.0 | Đã có, giữ nguyên |
| Recency bonus | post-retrieval | +0.05 max | Đã có trong score fusion |

**Logic:**
```python
EVENT_TYPE_HINTS = {
    "xet_hoc_bong":     ["học bổng", "xét học bổng", "hoc bong"],
    "dang_ky_hoc_tap":  ["đăng ký học tập", "đkht", "dang ky"],
    "thi_lai":          ["thi lại", "thi lai", "học lại"],
    "nop_don":          ["nộp đơn", "nop don", "nộp hồ sơ"],
}
# Detect semester
SEMESTER_HINTS = {
    "HK1": ["hk1", "học kỳ 1", "kỳ 1", "ki 1", "semester 1"],
    "HK2": ["hk2", "học kỳ 2", "kỳ 2", "ki 2", "semester 2"],
    "HKhe": ["hè", "he", "hk hè", "summer"],
}
```

---

### 3.6 StsvQueryBuilder — chi tiết boost

| Tín hiệu | Field | Boost | Ghi chú |
|---|---|---|---|
| "biểu mẫu", "mẫu đơn", "form" | `form_type=bieu_mau` | 80.0 | |
| "hướng dẫn", "quy trình" | `form_type=huong_dan` | 60.0 | |
| Tên thủ tục exact phrase | `procedure_name` match_phrase | 40.0 | |
| Title | `title` | 5.0 | |

---

## 4. Thay đổi trong `ElasticsearchStore`

### 4.1 Signature mới của `keyword_search`

```python
def keyword_search(
    self,
    query: str,
    top_k: int = 20,
    filters: Optional[Dict[str, Any]] = None,
    collection_name: Optional[str] = None,   # ← THÊM MỚI
) -> List[Dict[str, Any]]:
    """
    collection_name: nếu có → dùng CollectionQueryBuilder để build query
                     nếu None → fallback về generic query hiện tại
    """
    from .collection_query_builder import get_query_builder

    builder = get_query_builder(collection_name)  # None-safe
    if builder:
        search_body = builder.build(query, top_k, filters)
    else:
        search_body = self._build_generic_query(query, top_k, filters)

    resp = self.client.search(
        index=self.index_name,
        size=search_body["size"],
        query=search_body["query"],
    )
    # ... parse hits (giữ nguyên)
```

### 4.2 Refactor generic query thành `_build_generic_query()`

Tách code query hiện tại trong `keyword_search()` ra thành private method để tái sử dụng làm fallback.

---

## 5. Thay đổi trong `MultiCollectionSearch`

### 5.1 Pass `collection_name` xuống `keyword_search`

Trong `_fetch_one()`:
```python
def _fetch_one(name, hybrid):
    qdrant_filter, es_filter = resolved_filters.get(name, (None, None))
    vecs = hybrid.qdrant.search(...)
    kws = hybrid.es.keyword_search(
        query=query,
        top_k=keyword_top_k,
        filters=es_filter,
        collection_name=name,    # ← THÊM
    )
    return name, vecs, kws
```

---

## 6. Checklist triển khai

### Phase 1 — ES Mapping (không cần code mới)
- [ ] Thêm `CTDT_EXTRA_FIELDS` vào `ElasticsearchStore._make_settings()` cho index `ctdt`
- [ ] Thêm `QUYDINH_EXTRA_FIELDS`, `KEHOACH_EXTRA_FIELDS`, `STSV_EXTRA_FIELDS` tương tự
- [ ] Xây dựng script re-index để populate các field mới từ raw data

### Phase 2 — Module `collection_query_builder.py`
- [ ] Implement `BaseQueryBuilder` abstract class
- [ ] Implement `CtdtQueryBuilder` (priority: course_code exact boost)
- [ ] Implement `QuyDinhQueryBuilder`
- [ ] Implement `KeHoachQueryBuilder`
- [ ] Implement `StsvQueryBuilder`
- [ ] Registry function `get_query_builder(collection_name) -> Optional[BaseQueryBuilder]`

### Phase 3 — Integration
- [ ] Refactor `ElasticsearchStore.keyword_search()` — tách generic query ra `_build_generic_query()`
- [ ] Thêm param `collection_name` vào `keyword_search()`
- [ ] Pass `collection_name` từ `MultiCollectionSearch._fetch_one()`
- [ ] Pass `collection_name` từ `HybridSearch.search()` nếu cần

### Phase 4 — Testing
- [ ] Unit test per builder: assert boost fields xuất hiện đúng trong query DSL
- [ ] Integration test: query "IT3080" → chunk có `course_code=IT3080` phải rank #1
- [ ] Integration test: query "học bổng K70" → `regulation_type=hoc_bong` + `applicable_major=K70`
- [ ] A/B compare: top-5 kết quả trước/sau boosting với test queries

---

## 7. Câu hỏi còn mở — cần xác nhận

| # | Câu hỏi | Ảnh hưởng |
|---|---|---|
| 1 | Dữ liệu `course_code` (IT3080) hiện nằm ở đâu trong chunked text? Cần parser để extract khi re-index | Mapping + ingest pipeline |
| 2 | `regulation_type` được gán thủ công khi ingest hay cần classifier? | Ingest pipeline |
| 3 | `applicable_major` trong `quydinh` là list strings hay JSON array string trong ES? | Query DSL (term vs terms) |
| 4 | Boost values (200.0, 150.0...) là đề xuất — cần calibrate bằng evaluation set thực | Tuning |
| 5 | `stsv` có cần course-level boosting không (ví dụ: form liên quan môn học)? | Scope StsvQueryBuilder |
