# Đánh Giá Chi Tiết & Kế Hoạch Tối Ưu Module Retrieval

## Tổng Quan

Module [retrieval](file:///d:/GR/src/RAG_v2/retrieval) là thành phần trung tâm của hệ thống RAG, chịu trách nhiệm tìm kiếm hybrid (vector + BM25) trên nhiều collection (ctdt, quydinh, kehoach, stsv). Module gồm **20 files**, ~3,200 dòng code chính, và thực hiện:

- **Metadata pre-filtering** → **Dual-vector search (BGE-M3 + E5)** → **BM25 keyword search** → **Score fusion** → **Dedup** → **Reranking** → **Cross-reference resolution** → **Validity filtering**

---

## I. CÁC LỖI TIỀM ẨN — PHÂN LOẠI THEO MỨC ĐỘ

### 🔴 CRITICAL — Ảnh hưởng trực tiếp đến chất lượng retrieval

> [!CAUTION]
> 6 lỗi critical sau đây có thể gây sai sót nghiêm trọng trong kết quả retrieval thực tế.

---

#### C1. `applicable_cohort` vs `applicable_major` — Field Name Mismatch (QuyDinh filter BROKEN)

**File**: [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py#L1046) vs [elasticsearch_store.py](file:///d:/GR/src/RAG_v2/retrieval/elasticsearch_store.py#L175)

`QuyDinhFilterExtractor.extract()` tạo ES query với field `"applicable_cohort"`:
```python
_null_or_terms("applicable_cohort", cohort_codes)  # ← line 1046
```

Nhưng ES index mapping trong `elasticsearch_store.py` chỉ định nghĩa field `"applicable_major"`:
```python
"applicable_major": {"type": "keyword"},  # ← line 175
```

Docstring của class nói `applicable_major`, nhưng **code thực tế query `applicable_cohort`** — một field **không tồn tại** trong ES mapping!

**Hậu quả**: Filter cho collection `quydinh` **luôn trả về 0 results** vì field `applicable_cohort` không tồn tại → fallback chain kết thúc ở "no filter" → search toàn bộ collection mà không có cohort filtering. Sinh viên K70 hỏi "quy định ngoại ngữ" sẽ nhận quy định của tất cả khóa, bao gồm K63, K64... đã lỗi thời.

> [!CAUTION]
> Đây là lỗi nghiêm trọng nhất — cohort filtering cho quydinh hoàn toàn không hoạt động. Fix ngay bằng cách đổi `"applicable_cohort"` → `"applicable_major"` ở line 1046, hoặc thêm field `applicable_cohort` vào ES mapping.

**Fix**:
```diff
-_null_or_terms("applicable_cohort", cohort_codes),
+_null_or_terms("applicable_major", cohort_codes),
```

---

#### C2. Score Fusion Single-Item Pool Bug — `_score_fusion` trả về 0.0 cho item duy nhất

**File**: [multi_collection_search.py](file:///d:/GR/src/RAG_v2/retrieval/multi_collection_search.py#L680-L686)

Khi `vector_pool` hoặc `keyword_pool` chỉ có **1 item**, min-max normalization tạo ra `norm = 0.0`:

```python
# Khi chỉ có 1 item: v_max = v_min = score → v_range = 1.0 (fallback)
# norm_v = (score - v_min) / v_range = (score - score) / 1.0 = 0.0
```

**Hậu quả**: Một kết quả vector có cosine score rất cao (0.95) nhưng là item duy nhất trong pool sẽ bị normalized thành 0.0, khiến nó xếp hạng thấp hơn các keyword results. Điều này xảy ra thường xuyên khi metadata filter thu hẹp kết quả xuống 1-2 items.

**Fix**:
```diff
 if vector_pool:
     v_max = vector_pool[0]["score"]
     v_min = vector_pool[-1]["score"]
-    v_range = v_max - v_min if v_max != v_min else 1.0
+    v_range = v_max - v_min if v_max != v_min else v_max or 1.0
 else:
     v_min = v_range = 1.0
```
Khi chỉ có 1 item, dùng chính score đó làm range → `norm = score/score = 1.0`.

---

#### C2. Major Code Collision — "Kỹ thuật Thực phẩm" (BF2) vs "Kỹ thuật thực phẩm" (BF-E12)

**File**: [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py#L133-L170)

`MAJOR_CODE_TO_NAME` có 2 entries khác nhau chỉ bởi capitalization:
- `BF2 → "Kỹ thuật Thực phẩm"` (chữ T hoa)
- `BF-E12 → "Kỹ thuật thực phẩm"` (chữ t thường)

`_MAJOR_NAME_TO_CODE` dùng `setdefault` nên chỉ map cho entry đầu tiên. Khi `resolved_major = "Kỹ thuật thực phẩm"`:
1. `canonicalize_major_name` → trả về "Kỹ thuật thực phẩm" (BF-E12)
2. `_MAJOR_NAME_TO_CODE["Kỹ thuật thực phẩm"]` → không tìm thấy (vì "Kỹ thuật Thực phẩm" ≠ "Kỹ thuật thực phẩm")
3. Phải rơi vào `casefold` fallback loop → tìm BF2 trước BF-E12 (sai!)

**Hậu quả**: Sinh viên ngành BF-E12 hỏi về CTĐT của mình nhưng lọc theo BF2, nhận kết quả sai hoàn toàn.

**Fix**: Dùng case-insensitive lookup cho `_MAJOR_NAME_TO_CODE` hoặc chuẩn hóa key.

---

#### C3. Qdrant Score Fusion Không Normalize — BGE vs E5 Score Dominance

**File**: [qdrant_store.py](file:///d:/GR/src/RAG_v2/retrieval/qdrant_store.py#L190-L236)

`_fuse_results` tính `score = bge_weight * bge_score + e5_weight * e5_score` **mà không normalize** hai model trước. BGE-M3 và E5 có thể trả về score ranges rất khác nhau (ví dụ BGE: 0.3–0.9, E5: 0.5–0.95). Model nào có absolute scores cao hơn sẽ luôn dominate, bất kể weight setting.

**Hậu quả**: Weights 0.5/0.5 thực tế không cân bằng — model có range cao hơn luôn ảnh hưởng nhiều hơn, dẫn đến suboptimal ranking.

**Fix**: Áp dụng min-max normalization trước fusion, giống `_score_fusion` ở `MultiCollectionSearch`.

---

#### C4. BaseRetriever Là Interface "Mồ Côi" — Không Ai Implement

**File**: [base.py](file:///d:/GR/src/RAG_v2/retrieval/base.py#L9-L36)

`BaseRetriever.search()` yêu cầu `query_vector: Optional[List[float]]` (single vector), nhưng tất cả implementations thực tế (`QdrantStore`, `HybridSearch`, `MultiCollectionSearch`) đều dùng dual vectors (`bge_m3_query`, `e5_query`) và **không kế thừa** `BaseRetriever`.

**Hậu quả**: Type contracts bị phá vỡ — code client dùng `BaseRetriever` type sẽ không thể swap implementations. Interface trở thành dead code gây confusion.

---

#### C5. HybridSearch.search() Là Dead Code Trong Multi-Collection Flow

**File**: [hybrid_search.py](file:///d:/GR/src/RAG_v2/retrieval/hybrid_search.py#L53-L118) vs [multi_collection_search.py](file:///d:/GR/src/RAG_v2/retrieval/multi_collection_search.py#L357-L375)

`MultiCollectionSearch._fetch_one()` gọi trực tiếp `hybrid.qdrant.search()` và `hybrid.es.keyword_search()`, **bỏ qua hoàn toàn** `HybridSearch.search()`. Điều này có nghĩa:
- RRF fusion trong `HybridSearch._rrf_fuse()` **không bao giờ được gọi** trong multi-collection flow
- Exclude terms parsing trong `HybridSearch.search()` bị duplicate với `MultiCollectionSearch.search()`
- `HybridSearch` chỉ là "container" giữ references tới `qdrant` và `es`

---

### 🟠 HIGH — Có thể gây sai sót trong edge cases

> [!WARNING]
> 8 lỗi sau ảnh hưởng đến chất lượng trong các trường hợp biên nhưng không phải lỗi hệ thống.

---

#### H1. ThreadPoolExecutor Tạo Mới Mỗi Lần Search

**File**: [multi_collection_search.py](file:///d:/GR/src/RAG_v2/retrieval/multi_collection_search.py#L378)

```python
with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
```

Thread pool được tạo mới và destroy cho mỗi lần `search()`. Với 4 threads, overhead tạo/hủy ~2-5ms mỗi lần.

**Fix**: Tạo pool trong `__init__` và reuse. Dùng `atexit` hoặc context manager để cleanup.

---

#### H2. Qdrant Dual-Vector Search = 2 Network Round-Trips

**File**: [qdrant_store.py](file:///d:/GR/src/RAG_v2/retrieval/qdrant_store.py#L158-L180)

Mỗi lần search phải gọi 2 lần `query_points` (BGE + E5) tuần tự. Qdrant hỗ trợ `query_batch_points` để batch cả 2 query trong 1 round-trip.

**Impact**: Latency tăng gấp đôi cho Qdrant search phần (~20-50ms overhead mỗi query).

---

#### H3. `resolve_chunk_ids_for_qdrant` Có Thể Trả Về Empty Sai

**File**: [elasticsearch_store.py](file:///d:/GR/src/RAG_v2/retrieval/elasticsearch_store.py#L428-L546)

Method này cố map ES `_id` → Qdrant point IDs. Nếu ID format không khớp (ES dùng string, Qdrant dùng UUID), cả fast path và fallback path đều trả về `[]`. Khi đó metadata filter bị silent skip — search toàn bộ collection mà không có filter.

---

#### H4. `_ensure_index` Nuốt Exception Không Phải ICU

**File**: [elasticsearch_store.py](file:///d:/GR/src/RAG_v2/retrieval/elasticsearch_store.py#L108)

```python
except Exception:  # Catches ALL exceptions, not just ICU-missing
```

Nếu index creation fail vì network error hoặc auth failure (không phải ICU missing), code sẽ silently fallback sang standard analyzer thay vì raise error.

---

#### H5. `strip_major_from_query_for_retrieval` Over-Strip cho Comparison Queries

**File**: [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py#L765-L828)

Query "chương trình đào tạo ngành IT1 và IT2" sẽ bị strip cả 2 major codes, để lại "chương trình đào tạo" — quá generic cho retrieval.

---

#### H6. `kehoach_recency_bonus` Dùng `datetime.now()` Không Timezone

**File**: [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py#L1163)

`datetime.now()` trả về local time. Nếu server timezone thay đổi, recency calculations bị lệch.

---

#### H7. `ValidityFilter` Substring Matching Có False Positives

**File**: [validity_filter.py](file:///d:/GR/src/RAG_v2/retrieval/validity_filter.py#L106-L108)

`pattern in source_lower` nghĩa là "qd_2020" superseded sẽ cũng match "new_qd_2020_update" (chưa superseded).

---

#### H8. `ReferenceResolver._lookup_by_search` Trigger Full Search+Rerank

**File**: [reference_resolver.py](file:///d:/GR/src/RAG_v2/retrieval/reference_resolver.py#L458-L463)

Resolving 1 reference = 1 full search pipeline (embedding + Qdrant + ES + reranker). Với `max_total_refs=3`, worst case = 3 full searches thêm.

---

### 🟡 MEDIUM — Anti-patterns và Technical Debt

| # | Issue | File | Mô tả |
|---|-------|------|--------|
| M1 | Dead code `INDEX_SETTINGS` | [elasticsearch_store.py](file:///d:/GR/src/RAG_v2/retrieval/elasticsearch_store.py#L17-L58) | Module-level constant không bao giờ được dùng |
| M2 | Dead code `config.py` | [config.py](file:///d:/GR/src/RAG_v2/retrieval/config.py) | `VIETNAMESE_STOP_WORDS = []` — file rỗng, không ai import |
| M3 | Duplicated `_filter_excluded` logic | [hybrid_search.py](file:///d:/GR/src/RAG_v2/retrieval/hybrid_search.py#L121-L140) vs [multi_collection_search.py](file:///d:/GR/src/RAG_v2/retrieval/multi_collection_search.py#L637-L664) | Cùng haystack construction, copy-paste |
| M4 | `TYPE_CHECKING` import unused | [__init__.py](file:///d:/GR/src/RAG_v2/retrieval/__init__.py#L4) | Imported nhưng không dùng trong `if TYPE_CHECKING:` block |
| M5 | `update_metadata_batch` Qdrant = O(n) API calls | [qdrant_store.py](file:///d:/GR/src/RAG_v2/retrieval/qdrant_store.py#L387-L400) | Gọi `set_payload` từng point thay vì batch |
| M6 | Hardcoded major data | [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py#L133-L390) | 3+ data structures phải sync khi thêm ngành mới |
| M7 | `search()` không fallback khi 1 store down | [service.py](file:///d:/GR/src/RAG_v2/retrieval/service.py#L124-L180) | Nếu embedding fail → toàn bộ search fail |
| M8 | `_text_key` truncate 200 chars cho dedup | [reference_resolver.py](file:///d:/GR/src/RAG_v2/retrieval/reference_resolver.py#L165-L166) | 2 chunks khác nhau nhưng 200 chars đầu giống → false dedup |
| M9 | `_build_date_query` strip semester codes | [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py#L1108-L1113) | "lịch học kỳ 2025-1" → strip year, mất context |
| M10 | Search fallback to ALL collections | [multi_collection_search.py](file:///d:/GR/src/RAG_v2/retrieval/multi_collection_search.py#L286-L291) | Request `["nonexistent"]` → search all thay vì empty |
| M11 | No caching for identical queries | Module-wide | Cùng query gọi liên tiếp → embed + search lại từ đầu |
| M12 | `RetrievalService` không enforce singleton | [service.py](file:///d:/GR/src/RAG_v2/retrieval/service.py#L68) | Multiple `from_settings()` calls = multiple embedder instances |

---

## II. ĐÁNH GIÁ TEST COVERAGE

### Tổng Quan Coverage

| File | Tests | Đánh giá | Gaps nghiêm trọng |
|------|-------|----------|-------------------|
| [elasticsearch_store.py](file:///d:/GR/src/RAG_v2/retrieval/elasticsearch_store.py) | 3 tests | ⚠️ Yếu | `resolve_chunk_ids_for_qdrant`, `get_latest_chunk_ids_by_date` — 0 tests |
| [qdrant_store.py](file:///d:/GR/src/RAG_v2/retrieval/qdrant_store.py) | 3 tests | ⚠️ Yếu | `get_by_metadata`, `search with filters` — 0 tests |
| [hybrid_search.py](file:///d:/GR/src/RAG_v2/retrieval/hybrid_search.py) | 7 tests | ✅ Khá | Thiếu custom weight tests |
| [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py) | 38 tests | ✅ Tốt nhất | Thiếu `build_collection_filters`, `kehoach_recency_bonus` |
| [multi_collection_search.py](file:///d:/GR/src/RAG_v2/retrieval/multi_collection_search.py) | 0 tests | 🔴 Không có | Core pipeline hoàn toàn không test |
| [reference_resolver.py](file:///d:/GR/src/RAG_v2/retrieval/reference_resolver.py) | 0 tests | 🔴 Không có | Complex cross-ref logic không test |
| [validity_filter.py](file:///d:/GR/src/RAG_v2/retrieval/validity_filter.py) | 0 tests | 🔴 Không có | — |
| [collection_selector.py](file:///d:/GR/src/RAG_v2/retrieval/collection_selector.py) | 0 tests | 🔴 Không có | — |
| [service.py](file:///d:/GR/src/RAG_v2/retrieval/service.py) | 0 tests | 🔴 Không có | — |

> [!IMPORTANT]
> **5/9 files chính** hoàn toàn **không có test**. Đặc biệt nghiêm trọng là `multi_collection_search.py` (835 dòng, core pipeline) và `reference_resolver.py` (561 dòng, complex logic).

---

## III. CHIẾN LƯỢC TỐI ƯU THEO RAG BEST PRACTICES

### Phase 1: Fix Critical Bugs (Ưu tiên cao nhất — 1-2 ngày)

> [!CAUTION]
> Những fix này cần deploy ngay vì ảnh hưởng trực tiếp đến chất lượng câu trả lời.

#### [MODIFY] [multi_collection_search.py](file:///d:/GR/src/RAG_v2/retrieval/multi_collection_search.py)

1. **Fix C1**: `_score_fusion` — Sửa min-max normalization cho single-item pools
   - Khi pool chỉ có 1 item, dùng `v_range = v_max or 1.0` thay vì `v_range = 1.0`
   - Điều này đảm bảo single-item pool gets norm=1.0 (max confidence)

2. **Fix C5**: Refactor `_fetch_one` để gọi qua `HybridSearch.search()` hoặc remove `HybridSearch.search()` để tránh confusion

3. **Fix H1**: Chuyển `ThreadPoolExecutor` thành instance attribute, khởi tạo trong `__init__`

#### [MODIFY] [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py)

4. **Fix C2**: Sửa `_MAJOR_NAME_TO_CODE` dùng case-insensitive key hoặc normalize cả key lẫn value
   ```python
   _MAJOR_NAME_TO_CODE: Dict[str, str] = {}
   for major_code, major_name in MAJOR_CODE_TO_NAME.items():
       _MAJOR_NAME_TO_CODE.setdefault(major_name.lower(), major_code)  # lowercase key
   ```

#### [MODIFY] [qdrant_store.py](file:///d:/GR/src/RAG_v2/retrieval/qdrant_store.py)

5. **Fix C3**: Thêm min-max normalization trước weighted fusion trong `_fuse_results()`

---

### Phase 2: Performance Optimization (3-5 ngày)

#### [MODIFY] [qdrant_store.py](file:///d:/GR/src/RAG_v2/retrieval/qdrant_store.py)

1. **Fix H2**: Chuyển dual `query_points` → `query_batch_points` cho 1 round-trip
2. **Fix M5**: Batch `set_payload` operations thay vì loop

#### [MODIFY] [elasticsearch_store.py](file:///d:/GR/src/RAG_v2/retrieval/elasticsearch_store.py)

3. **Optimize `get_latest_chunk_ids_by_date`**: Chuyển `date_str` sang ES date type, dùng ES native sort thay vì Python sort trên 1000 items
4. **Fix H4**: Catch cụ thể `elasticsearch.RequestError` cho ICU fallback

#### [MODIFY] [reference_resolver.py](file:///d:/GR/src/RAG_v2/retrieval/reference_resolver.py)

5. **Fix H8**: Tách `_lookup_by_search` thành lightweight search (skip reranking) với `rerank=False`
6. Thêm LRU cache cho resolved references (cache by `(collection, document_id, article_num)`)

#### [NEW] `retrieval/cache.py`

7. Implement query-level caching: Cache embedding results + search results với TTL
   ```python
   @lru_cache(maxsize=128)
   def cached_embed(query: str) -> Tuple[List[float], List[float]]: ...
   ```

---

### Phase 3: Architecture Improvements (1-2 tuần)

#### [MODIFY] [base.py](file:///d:/GR/src/RAG_v2/retrieval/base.py)

1. **Fix C4**: Cập nhật `BaseRetriever` interface để match thực tế (dual vectors) hoặc xóa bỏ
   ```python
   class BaseRetriever(ABC):
       @abstractmethod
       def search(
           self,
           query: str,
           bge_m3_query: Optional[List[float]] = None,
           e5_query: Optional[List[float]] = None,
           top_k: int = 5,
           **kwargs: Any,
       ) -> List[Dict[str, Any]]: ...
   ```

#### [MODIFY] [hybrid_search.py](file:///d:/GR/src/RAG_v2/retrieval/hybrid_search.py)

2. **Clarify role**: Hoặc (a) integrate `HybridSearch.search()` vào multi-collection flow, hoặc (b) remove `search()` và chỉ giữ `HybridSearch` như container

#### [NEW] `retrieval/utils.py`

3. **Fix M3**: Extract shared utilities
   ```python
   def build_exclusion_haystack(item: Dict) -> str: ...
   def text_dedup_key(text: str) -> str: ...
   ```

#### [DELETE] `retrieval/config.py`

4. **Fix M2**: Remove dead config file

#### [MODIFY] [metadata_filters.py](file:///d:/GR/src/RAG_v2/retrieval/metadata_filters.py)

5. **Fix M6**: Externalize major data vào JSON/YAML file
   ```
   data/major_programs.json → MAJOR_CODE_TO_NAME, MAJOR_PATTERNS, MAJOR_NAME_ALIAS_MAPPING
   ```

#### [MODIFY] [validity_filter.py](file:///d:/GR/src/RAG_v2/retrieval/validity_filter.py)

6. **Fix H7**: Chuyển substring matching → exact stem matching hoặc regex with word boundaries

#### [MODIFY] [service.py](file:///d:/GR/src/RAG_v2/retrieval/service.py)

7. **Fix M12**: Enforce singleton pattern
8. **Fix M7**: Graceful degradation — fallback single embedder nếu 1 model fail

---

### Phase 4: Test Coverage & Quality (1-2 tuần)

> [!IMPORTANT]
> Ưu tiên viết tests cho 5 files không có test, đặc biệt `multi_collection_search.py`.

#### [NEW] `retrieval/test_multi_collection_search.py`

Tests cần cover:
- `_score_fusion` với: 0 items, 1 item, N items, mixed vector/keyword
- `_score_fusion_rrf` tương tự
- `_resolve_fusion_weights` với course queries và non-course queries
- `_resolve_filter_with_fallback` với: empty filter, successful filter, all-fail fallback
- `_dedup_pool` edge cases
- `_filter_excluded_results` với: no terms, matching terms, no match
- `search()` integration: multi-collection, single-collection, no-match fallback
- Thread safety

#### [NEW] `retrieval/test_reference_resolver.py`

Tests cần cover:
- `extract_references`: Điều X, khoản Y Điều X, multiple refs
- `_same_document` matching logic
- `_matches_article_heading`
- `resolve` full pipeline với mock service

#### [NEW] `retrieval/test_validity_filter.py`

Tests cần cover:
- Superseded document filtering
- `min_results` safety net
- False positive substring matching
- Missing registry file

#### [NEW] `retrieval/test_collection_selector.py`

Tests cần cover:
- Domain → collection mapping
- Confidence threshold behavior
- Multi-domain union
- Unknown domain handling

#### [MODIFY] Test files hiện tại

- Thêm tests cho `resolve_chunk_ids_for_qdrant` fallback paths
- Thêm tests cho `get_latest_chunk_ids_by_date` date parsing
- Thêm tests cho `build_collection_filters` integration
- Thêm tests cho `kehoach_recency_bonus`

---

## IV. ADVANCED RAG STRATEGIES — ROADMAP DÀI HẠN

### Strategy 1: Contextual Retrieval (Anthropic-style)

Thêm context vào mỗi chunk trước khi embed, cải thiện retrieval accuracy 20-67% (theo nghiên cứu Anthropic):

```python
# Trước khi embed chunk:
contextualized_text = f"""
Tài liệu: {document_title}
Phần: {section_heading}
Ngành: {major_name}
Nội dung chunk:
{chunk_text}
"""
```

### Strategy 2: Query Decomposition

Tách complex queries thành sub-queries trước khi search:
- "So sánh quy định ngoại ngữ K70 và K67" → 2 sub-queries riêng, mỗi query filter theo cohort
- Đã có `build_cohort_comparison_subqueries_for_retrieval()` nhưng chưa thấy được integrate

### Strategy 3: Adaptive Retrieval

Dựa vào confidence của retrieval results để quyết định:
- Nếu top result score < threshold → trigger query expansion / reformulation
- Nếu results từ nhiều collections → apply cross-collection reranking
- Nếu no results → fallback web search (Tavily)

### Strategy 4: Evaluation-Driven Improvement

- Implement automated evaluation pipeline (Recall@K, MRR, NDCG)
- Build golden test set từ `retrieval_evaluation_v2.md`
- CI/CD gate: block deploy nếu retrieval metrics regress

### Strategy 5: Semantic Caching

Cache không chỉ exact query match mà cả semantically similar queries:
```python
# Nếu embedding similarity > 0.95 với cached query → return cached results
```

---

## V. DOCUMENTATION GAPS

| Missing | Mức độ |
|---------|--------|
| `ReferenceResolver` không có trong MODULE.md | HIGH |
| `ValidityFilter` không có trong MODULE.md | HIGH |
| Operational runbook (how to debug retrieval issues) | MEDIUM |
| Performance benchmarks (expected latencies) | MEDIUM |
| Test coverage status trong MODULE.md | LOW |

---

## Open Questions

> [!IMPORTANT]
> Các câu hỏi cần feedback trước khi tiến hành:

1. **Về C5 (HybridSearch dead code)**: Bạn muốn (a) refactor `MultiCollectionSearch` để dùng `HybridSearch.search()` qua pipeline chuẩn, hay (b) remove `HybridSearch.search()` và chỉ giữ nó như container? Option (a) sạch hơn nhưng cần refactor nhiều. Option (b) ít effort hơn.

2. **Về Phase 3, M6 (externalize major data)**: Bạn có muốn chuyển hardcoded major patterns ra file JSON/YAML không? Ưu điểm: dễ maintain, không cần deploy code khi thêm ngành. Nhược điểm: thêm 1 file dependency.

3. **Về Phase 4 (tests)**: Bạn muốn ưu tiên viết tests cho files nào trước? Recommendation: `multi_collection_search.py` → `reference_resolver.py` → `validity_filter.py`.

4. **Về Advanced Strategies**: Bạn quan tâm đến strategy nào nhất? Contextual Retrieval (cải thiện chất lượng) hay Semantic Caching (cải thiện performance)?

---

## Verification Plan

### Automated Tests
```bash
# Chạy existing tests để đảm bảo không regression
python -m pytest src/RAG_v2/retrieval/ -v

# Chạy tests mới sau khi viết
python -m pytest src/RAG_v2/retrieval/test_multi_collection_search.py -v
python -m pytest src/RAG_v2/retrieval/test_reference_resolver.py -v
```

### Manual Verification
- Test C1 fix: Search với metadata filter thu hẹp chỉ 1 result, verify score ≠ 0.0
- Test C2 fix: Query "CTĐT ngành Kỹ thuật thực phẩm" → verify filter BF-E12 (not BF2)
- Test C3 fix: Compare ranking before/after normalize với queries có BGE vs E5 score ranges khác nhau
- Run [retrieval_evaluation_v2.md](file:///d:/GR/src/RAG_v2/retrieval/retrieval_evaluation_v2.md) test cases lại sau fixes
