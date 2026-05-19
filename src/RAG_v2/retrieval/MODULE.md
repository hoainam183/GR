# Module: `retrieval` — Document Retrieval Layer

## Tổng quan

Module `retrieval` chịu trách nhiệm **tìm kiếm và lọc tài liệu** từ kho dữ liệu (Qdrant + Elasticsearch). Đây là module phức tạp nhất về mặt kỹ thuật, thực hiện **hybrid search** (vector + BM25) song song trên nhiều collection, kết hợp metadata pre-filtering, score fusion nhiều tầng, deduplication, validity filtering, và cross-reference resolution.

---

## Cấu trúc file

```
retrieval/
├── __init__.py                  # Public API + factory create_retriever()
├── base.py                      # BaseRetriever — abstract interface
├── service.py                   # RetrievalService — singleton orchestrator
├── multi_collection_search.py   # MultiCollectionSearch — parallel multi-collection search
├── hybrid_search.py             # HybridSearch — RRF fusion cho 1 collection
├── qdrant_store.py              # QdrantStore — dual-vector (BGE-M3 + E5) Qdrant store
├── elasticsearch_store.py       # ElasticsearchStore — BM25 keyword search + metadata filter
├── metadata_filters.py          # Pre-filter extraction: major/cohort/date per collection
├── collection_selector.py       # CollectionSelector — chọn collections từ domain
├── validity_filter.py           # ValidityFilter — loại chunk từ tài liệu superseded
├── reference_resolver.py        # ReferenceResolver — resolve cross-references
├── config.py                    # (trống / placeholder)
├── search_stsv.py               # Script tìm kiếm riêng cho STSV
├── index_stsv_to_es.py          # Script index STSV vào ES
├── retrieval_evaluation_v2.md   # Báo cáo đánh giá retrieval
├── test_hybrid_search.py        # Unit tests HybridSearch
├── test_metadata_filters.py     # Unit tests metadata filters
├── test_qdrant_store.py         # Unit tests QdrantStore
└── test_elasticsearch_store.py  # Unit tests ElasticsearchStore
```

---

## Public API (`__init__.py`)

```python
from retrieval import (
    BaseRetriever,
    QdrantStore,
    ElasticsearchStore,
    HybridSearch,
    BaseFilterExtractor,
    CollectionFilter,
    build_collection_filters,
    MultiCollectionSearch,
    create_retriever,          # factory chính
)
```

### `create_retriever(settings) -> MultiCollectionSearch`

Factory function: tạo `MultiCollectionSearch` từ `settings`, sử dụng `settings.collections`, `settings.qdrant_host/port`, `settings.elasticsearch_host/port`, `settings.vector_weight`, `settings.keyword_weight`.

---

## Chi tiết từng component

### `base.py` — `BaseRetriever`

Abstract base class cho tất cả retriever backends.

```python
class BaseRetriever(ABC):
    @abstractmethod
    def search(
        self,
        query: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = 5,
        **kwargs,
    ) -> List[Dict[str, Any]]: ...
```

---

### `service.py` — `RetrievalService`

**Nhiệm vụ:** Singleton service tập trung tất cả retrieval infrastructure.

Được tạo một lần lúc startup, inject vào cả `RAGPipeline` và `agent/tool_adapters`.

**Thành phần:**
| Attribute | Type | Mô tả |
|---|---|---|
| `bge_embedder` | `BGEm3Embedder` | Load BGE-M3 model |
| `e5_embedder` | `E5MultilingualEmbedder` | Load E5-multilingual model |
| `searcher` | `MultiCollectionSearch` | Hybrid searcher |
| `reranker` | reranker instance or None | Optional reranker |
| `tavily_tool` | `TavilySearchTool` or None | Optional web search |

**Factory:**
```python
service = RetrievalService.from_settings(settings)
```
Loads embedders, connects Qdrant/ES, khởi tạo reranker, và nếu `TAVILY_API_KEY` hợp lệ thì tạo `TavilySearchTool`.

**Methods:**

#### `embed_query(query) -> (bge_vec, e5_vec)`
Embed query với cả hai models, trả về tuple `(List[float], List[float])`.

#### `search(query, *, collections, top_k, resolved_major, resolved_cohort, rerank=True) -> List[Dict]`
Pipeline đầy đủ:
1. `embed_query()` → `bge_vec, e5_vec`
2. `searcher.search(...)` với `raw_candidate_k = max(top_k * 4, 20)`
3. Nếu `rerank=True` và reranker tồn tại → `reranker.rerank(query, documents, top_k)`
4. Trả về top-k results

#### `web_search(query, max_results=3) -> Any`
Delegate đến `TavilySearchTool`. Raise `RuntimeError` nếu Tavily chưa được config.

---

### `multi_collection_search.py` — `MultiCollectionSearch`

**Nhiệm vụ:** Orchestrate hybrid search trên nhiều collection song song.

**Constructor params:**
- `searchers`: `List[Tuple[str, HybridSearch]]`
- `rrf_k`: RRF constant (default 60, backward-compat)
- `max_workers`: ThreadPoolExecutor size (default 4)
- `vector_weight`: weight cho normalized vector score (default 0.7)
- `keyword_weight`: weight cho normalized keyword score (default 0.3)

**Factory:**
```python
MultiCollectionSearch.from_collection_names(
    collection_names=["ctdt", "quydinh", "stsv", "kehoach"],
    qdrant_host=..., qdrant_port=...,
    es_host=..., es_port=...,
    vector_weight=0.7, keyword_weight=0.3,
)
```

#### `search()` — Pipeline 6 bước

```
Inputs: query, bge_m3_query, e5_query, top_k, vector_top_k,
        keyword_top_k, vector_pool_k, keyword_pool_k,
        active_collections, resolved_major, resolved_cohort,
        disable_metadata_filter_collections, trace_out

Step 0: Metadata pre-search
        build_collection_filters() → CollectionFilter per collection
        _resolve_filter_with_fallback():
          - Thử từng ES metadata query trong fallback chain
          - Nếu có IDs → resolve_chunk_ids_for_qdrant() → HasIdCondition
          - Nếu mọi query trả về 0 → None filter (search toàn bộ)

Step 1+2: Parallel fetch (ThreadPoolExecutor)
        Per collection:
          - QdrantStore.search(bge_m3_query, e5_query, filter=HasIdCondition)
          - ElasticsearchStore.keyword_search(query, filter=es_filter)
        Gắn "collection" field và prefix ID: "{collection}/{id}"

Step 3: Global vector pool
        Sort all_vector by score desc → dedup by ID → top vector_pool_k

Step 4: Global keyword pool
        Sort all_keyword by score desc → dedup by ID → top keyword_pool_k

Step 5: Score fusion (min-max normalize + weighted sum)
        norm_v = (score - v_min) / v_range
        norm_k = (score - k_min) / k_range
        fused_score = vector_weight * norm_v
                    + keyword_weight * norm_k
                    + kehoach_recency_bonus(doc)  # chỉ cho collection kehoach

Step 6: Text-level dedup → sort desc → return top_k
```

**Adaptive fusion weights (`_resolve_fusion_weights`):**
- Mặc định: `vector=0.7, keyword=0.3`
- Nếu query chứa course code (`IT4210`, `MA1001`…) hoặc hints (`"môn "`, `"học phần"`, `"tiên quyết"`, `"tín chỉ"`…) → `vector=0.4, keyword=0.6` (bias về exact match BM25)
- `trace_out` dict (nếu truyền vào) sẽ được populate: `filters`, `collection_counts`, `fusion_weights`

**Helpers:**
- `collection_names` property → list tên collections
- `qdrant_stores` property → `{name: QdrantStore}`
- `collection_counts()` → `{name: {"qdrant": n, "es": n}}`

---

### `hybrid_search.py` — `HybridSearch`

**Nhiệm vụ:** Kết hợp Qdrant vector search + ES BM25 cho **một** collection bằng **RRF (Reciprocal Rank Fusion)**.

> **Lưu ý quan trọng:** `HybridSearch` dùng RRF fusion tại per-collection level. Còn `MultiCollectionSearch` dùng **min-max normalize + weighted sum** tại global level. Hai tầng fusion khác nhau.

**RRF score:** `rrf_score(rank, k=60) = 1.0 / (k + rank)`

**`search()` method:**
1. `QdrantStore.search()` → vector results (vector_top_k candidates)
2. `ElasticsearchStore.keyword_search()` → keyword results (keyword_top_k candidates)
3. `_rrf_fuse()` → RRF merge với weighted scores
4. Optional `filter_by_score(hybrid_score_threshold)` → filter low-quality
5. Return top-k

**Output dict per result:**
```python
{
    "id": str,
    "text": str,
    "metadata": dict,
    "score": float,          # fused RRF score
    "vector_score": float,   # raw cosine (Qdrant)
    "keyword_score": float,  # raw BM25 (ES)
    "vector_rank": int,      # rank trong Qdrant results (0 = not found)
    "keyword_rank": int,     # rank trong ES results (0 = not found)
    "bge_score": float,      # BGE-M3 cosine (diagnostic)
    "e5_score": float,       # E5 cosine (diagnostic)
}
```

---

### `qdrant_store.py` — `QdrantStore`

**Nhiệm vụ:** Quản lý một Qdrant collection với **hai named vectors**: `bge_m3` (1024-dim) và `e5` (1024-dim), COSINE distance.

**`search(bge_m3_query, e5_query, top_k, score_threshold, filters, bge_weight=0.5, e5_weight=0.5)`:**
- Gọi `query_points` hai lần (per vector), `hnsw_ef=128`, `per_vector_k = min(top_k*2, 100)`
- `_fuse_results()`: weighted score fusion `score = bge_weight * bge_score + e5_weight * e5_score`
- Return `[{"id", "text", "metadata", "score", "bge_score", "e5_score"}]`

**Indexing:**
```python
store.index_documents(texts, bge_m3_vectors, e5_vectors, metadatas, ids, batch_size=64)
```
Upsert theo batch. Payload = `{**metadata, "text": text}`.

**Metadata management:**
- `update_metadata_by_ids(ids, metadata, overwrite=False)` — set/overwrite payload fields
- `update_metadata_batch(id_metadata_pairs, overwrite=False, batch_size=100)` — bulk update
- `update_metadata_by_filter(filter_key, filter_value, metadata, overwrite=False)` — filter-based update

**Utility:**
- `get_by_ids(ids)` → fetch points by ID list
- `delete_by_metadata(key, value)` → delete by payload filter
- `count()` → số points trong collection
- `delete_collection()` → drop toàn bộ collection

---

### `elasticsearch_store.py` — `ElasticsearchStore`

**Nhiệm vụ:** BM25 keyword search + metadata pre-filtering.

**`keyword_search(query, top_k, filters, collection_name)`:**
- Build ES `bool` query với `should` boosting clauses
- Boosting cao hơn cho: course names, course codes, curriculum keywords
- Apply `filters` nếu có
- Return `[{"id", "text", "metadata", "score"}]`

**`metadata_filter_search(es_query) -> List[str]`:**
- Filter-only search (không có text scoring)
- Dùng trong Step 0 của `MultiCollectionSearch`
- Return list of document IDs

**`resolve_chunk_ids_for_qdrant(raw_ids) -> List[str]`:**
- Map ES document IDs → Qdrant point IDs (UUID format)
- Dùng sau `metadata_filter_search` để tạo `HasIdCondition`

---

### `metadata_filters.py` — Pre-filtering Infrastructure

**Nhiệm vụ:** Xây dựng ES metadata filter fallback chain cho từng collection.

#### Data class `CollectionFilter`
```python
@dataclass
class CollectionFilter:
    metadata_es_queries: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool: ...
```
`metadata_es_queries` là fallback chain — thử từng query theo thứ tự cho đến khi có kết quả.

#### Abstract class `BaseFilterExtractor`
```python
class BaseFilterExtractor(ABC):
    @abstractmethod
    def extract(
        self, query, resolved_major=None, resolved_cohort=None
    ) -> CollectionFilter: ...
```

#### Per-collection extractors

| Extractor | Collection | Filter logic |
|---|---|---|
| `CtdtFilterExtractor` | `ctdt` | 1. `major_code` exact → 2. `major_name` fuzzy → 3. `major_code` OR null (generic) → 4. no filter |
| `QuyDinhFilterExtractor` | `quydinh` | 1. `applicable_cohort` exact (Kxx) OR null → 2. no filter |
| `KeHoachFilterExtractor` | `kehoach` | 1. date wildcard (month+year hoặc year-only) → 2. no filter |
| _(omitted)_ | `stsv` | Không có extractor — luôn search toàn bộ |

#### Major code system

**`MAJOR_CODE_TO_NAME`** covers all CTĐT major codes currently indexed in `data/ctdt`:
`BF1`, `BF2`, `BF-E12`, `CH1`, `CH2`, `CH-E11`, `EE1`, `EE2`, `EE-E18`,
`EE-E8`, `EE-EP`, `EV1`, `EV2`, `HE1`, `IT1`, `IT2`, `IT-E10`, `IT-E15`,
`IT-E6`, `IT-E7`, `IT-EP`, `ME1`, `ME2`, `ME-GU`, `ME-LUH`, `ME-NUT`,
`MI1`, `MI2`, `MS1`, `MS2`, `MS3`, `MS5`, `MS-E3`, `TE-EP`, `TROY-IT`, `TX1`.

**`MAJOR_PATTERNS`** and the major-code regexes recognize dash, Unicode-dash,
spaced, and compact forms such as `ME-GU`, `ME GU`, `ME–GU`, `MSE3`, `BFE12`,
and `TROY IT`. Patterns are first-match-wins, so specific international or
advanced programme codes must stay before generic Vietnamese names.

**Hàm quan trọng:**
- `_resolve_major_code(query, resolved_major)` — priority: direct `resolved_major` code → resolved name/alias → regex trên query; duplicate canonical names keep the first code in `MAJOR_CODE_TO_NAME`
- `_build_major_labels(major_code)` — trả về tất cả aliases (sort longest first)
- `extract_major_codes(text)` — extract tất cả explicit major codes
- `extract_cohort_codes(text)` — extract cohort codes dạng `Kxx`
- `canonicalize_major_name(user_major)` — map alias → canonical name
- `_normalise_major_text(value)` — normalize Unicode dash variants, compact forms

**Query manipulation:**
- `strip_major_from_query_for_retrieval(query, resolved_major)` — loại major mentions khỏi query (sau khi đã có metadata filter)
- `expand_major_in_query_for_reranking(query, resolved_major)` — expand major code → full name để improve reranker cross-encoder scores
- `strip_cohort_comparison_scaffold_for_retrieval(query)` — loại cohort comparison scaffold
- `build_cohort_comparison_subqueries_for_retrieval(query)` — tách so-sánh thành per-cohort subqueries
- `strip_major_comparison_scaffold_for_retrieval(query)` — loại major comparison scaffold
- `build_major_comparison_subqueries_for_retrieval(query)` — tách so-sánh thành `[(subquery, major_code)]`

**Date filtering (`KeHoachFilterExtractor`):**
- Strip school-year patterns (`2025-2026`, `năm học 2025-2026`) trước khi parse
- Match `tháng 3 2026` / `3/2026` → wildcard `*/3/2026`
- Match `năm 2025` / `2025` → wildcard `*/2025`

**Recency bonus (`kehoach_recency_bonus`):**
- Chỉ áp dụng với collection `kehoach`
- Parse `date_str` format `"D/M/YYYY"`
- `bonus = (1 - age_days / 365) * 0.05` trong range `[0.0, 0.05]`

**Registry:**
```python
_COLLECTION_FILTER_REGISTRY = {
    "ctdt":    CtdtFilterExtractor(),
    "quydinh": QuyDinhFilterExtractor(),
    "kehoach": KeHoachFilterExtractor(),
    # "stsv" omitted — no filter
}
```

**Public entry point:**
```python
build_collection_filters(
    query, collections, resolved_major=None, resolved_cohort=None
) -> Dict[str, CollectionFilter]
```

---

### `collection_selector.py` — `CollectionSelector`

**Nhiệm vụ:** Map domain classification → target Qdrant/ES collections.

**Constants:**
```python
DOMAIN_TO_COLLECTIONS = {
    "ctdt":    ["ctdt"],
    "quydinh": ["quydinh", "stsv"],  # overlap: regulations ↔ student support
    "kehoach": ["kehoach"],
    "stsv":    ["stsv", "quydinh"],  # overlap: student support ↔ regulations
}
ALL_COLLECTIONS       = ["stsv", "quydinh", "kehoach", "ctdt"]
MULTI_DOMAIN_FALLBACK = ["quydinh", "stsv", "ctdt"]   # low-confidence fallback
CONFIDENCE_THRESHOLD  = 0.55
```

**`select(domain, confidence, domains) -> List[str]`:**

| Input | Output |
|---|---|
| `domain="ctdt", conf=0.9` | `["ctdt"]` |
| `domain="quydinh", conf=0.9` | `["quydinh", "stsv"]` |
| `domains=["ctdt","stsv"], conf=0.8` | `["ctdt", "stsv", "quydinh"]` (union, order preserved) |
| `conf < 0.55` | `["quydinh", "stsv", "ctdt"]` (MULTI_DOMAIN_FALLBACK) |
| no domain | `["stsv", "quydinh", "kehoach", "ctdt"]` (ALL_COLLECTIONS) |

Hỗ trợ cả interface cũ (`domain: str`) và mới (`domains: List[str]`). `domains` có precedence.

---

### `validity_filter.py` — `ValidityFilter`

**Nhiệm vụ:** Loại bỏ chunks thuộc tài liệu **superseded** (đã bị thay thế bởi phiên bản mới hơn).

**Data source:** `data/document_lineage.json`

```json
{
  "documents": [
    {"doc_id": "...", "status": "superseded", "source_file": "old_regulation.md"},
    ...
  ]
}
```

**Cơ chế:**
- Load `document_lineage.json` khi khởi tạo
- Build `_superseded_ids: Set[str]` và `_superseded_patterns: List[str]` (stem của filename)
- `is_superseded(source)` → fuzzy match: kiểm tra nếu `pattern in source.lower()`
- `filter(results, min_results=2)` → loại bỏ chunks superseded
  - Safety: nếu số kết quả còn lại < `min_results` → giữ nguyên kết quả gốc
- `reload()` → hot-reload registry từ disk

**Tích hợp:** Chạy sau reranking, trước `ReferenceResolver`.

---

### `reference_resolver.py` — `ReferenceResolver`

**Nhiệm vụ:** Detect cross-references trong retrieved chunks và fetch các điều khoản được tham chiếu.

**Regex patterns:**
- `_ARTICLE_FIRST_RE`: `"Điều 48"`, `"Điều 48 khoản 2"`, `"Điều 5 khoản 1 và khoản 2"`
- `_CLAUSE_FIRST_RE`: `"khoản 1 và khoản 2 Điều 5"`, `"khoản 3, khoản 4 Điều 5"`

**`extract_references(text) -> List[Dict]`:**
```python
# Returns one item per article:
# [{"article": int, "clause": int|None, "clauses": List[int], "raw_match": str}]
```
Các mention trùng article được gộp lại, ví dụ `khoản 1 và khoản 2 Điều 5` chỉ resolve `Điều 5` một lần.

**`ReferenceResolver.resolve(results, query) -> List[Dict]`:**
1. Build set existing IDs (hỗ trợ cả raw UUID và `{collection}/{uuid}`) + text fallback.
2. Per chunk: `extract_references(text)` → refs
3. Per ref (max `max_refs_per_chunk=2`, total `max_total_refs=3`):
   - Ưu tiên Qdrant payload scroll theo `document_id` trong cùng collection.
   - Match article bằng heading thật (`section_h3` hoặc dòng `### Điều N`), không match câu chỉ nhắc tới Điều N.
   - Trả về nhiều child chunks cùng article theo `chunk_index`; parent chunks chỉ dùng nếu không có child chunks.
   - Fallback semantic search chỉ chạy khi metadata lookup không có kết quả; query fallback có source/filename và post-filter same `document_id` hoặc same source/filename.
   - Mark: `_cross_reference=True`, `_referenced_from`, `_reference`
4. Insert resolved refs ngay sau chunk gốc đã nhắc tới reference.

Nếu `retrieval_service=None` → trả về kết quả gốc (no-op).

---

## Luồng tổng hợp đầy đủ

```
Input: (query, resolved_major, resolved_cohort, active_collections)
        │
        ▼
RetrievalService.embed_query(query)
  → bge_vec (1024-dim), e5_vec (1024-dim)
        │
        ▼
MultiCollectionSearch.search(query, bge_m3_query, e5_query, ...)
  │
  ├─ _resolve_fusion_weights(query)
  │    → vector_weight=0.7/0.4, keyword_weight=0.3/0.6
  │
  ├─ build_collection_filters() → CollectionFilter per collection
  │
  ├─ _resolve_filter_with_fallback() per collection
  │    → (qdrant HasIdCondition, es_filter) | (None, None)
  │
  ├─ ThreadPoolExecutor (max_workers=4):
  │    Per collection:
  │      QdrantStore.search(bge_m3_query, e5_query, filter=HasIdCondition)
  │        → BGE-M3 query_points + E5 query_points → _fuse_results (weighted)
  │      ElasticsearchStore.keyword_search(query, filter=es_filter)
  │
  ├─ Global sort + dedup: vector_pool (top vector_pool_k) + keyword_pool (top keyword_pool_k)
  │
  └─ _score_fusion(vector_pool, keyword_pool):
       min-max normalize + weighted sum + kehoach_recency_bonus
       → text-level dedup → top_k candidates
        │
        ▼
BGEReranker.rerank(query, documents, top_k)   [module reranking]
        │
        ▼
ValidityFilter.filter(results)
  → loại chunks superseded (document_lineage.json)
        │
        ▼
ReferenceResolver.resolve(results, query)
  → insert same-document cross-referenced chunks
        │
        ▼
Final documents (top 5-10)
```

---

## Score fusion — hai tầng

| Tầng | Vị trí | Thuật toán | Mục đích |
|---|---|---|---|
| **Tầng 1: BGE+E5** | `QdrantStore._fuse_results` | Weighted sum `0.5*bge + 0.5*e5` | Kết hợp hai vector spaces |
| **Tầng 2: Vector+Keyword** | `MultiCollectionSearch._score_fusion` | Min-max normalize + weighted sum + recency bonus | Kết hợp semantic vs keyword |

> `HybridSearch._rrf_fuse` (RRF) chỉ được gọi nếu `HybridSearch.search()` được gọi trực tiếp (không qua `MultiCollectionSearch`).

---

## LLM involvement

Module `retrieval` **không sử dụng LLM**. Chỉ dùng:
- Local neural models (BGE-M3, E5) cho embedding — load trong `RetrievalService.from_settings()`
- Qdrant API cho vector search
- Elasticsearch API cho BM25 search + metadata filtering

---

## Latency contribution

| Component | Thời gian điển hình |
|---|---|
| `embed_query()` BGE-M3 + E5 | 20-80ms |
| Metadata pre-search (ES filter per collection) | 20-80ms |
| Qdrant vector search (per collection, parallel) | 20-100ms |
| ES keyword search (per collection, parallel) | 10-50ms |
| **Parallel multi-collection search (wall clock)** | **50-200ms** |
| Score fusion + dedup | 1-5ms |
| `ValidityFilter.filter()` | <1ms |
| `ReferenceResolver.resolve()` | 5-50ms (nếu có refs) |
| **Tổng module retrieval** | **~100-400ms** |

---

## Cách thêm filter cho collection mới

```python
# 1. Subclass BaseFilterExtractor
class NewCollectionFilterExtractor(BaseFilterExtractor):
    def extract(self, query, resolved_major=None, resolved_cohort=None) -> CollectionFilter:
        ...  # build fallback chain
        return CollectionFilter(metadata_es_queries=[...])

# 2. Register trong _COLLECTION_FILTER_REGISTRY
_COLLECTION_FILTER_REGISTRY["new_collection"] = NewCollectionFilterExtractor()
```

Không cần thay đổi file nào khác.

---

## Update 2026-05-17: Tavily service initialization

- `RetrievalService.from_settings()` uses the shared
  `is_valid_tavily_api_key()` validator from `tools.tavily_search`, so startup
  and agent fallback reject the same placeholder key values.
- The shared `TavilySearchTool` receives settings-driven cache controls:
  `tavily_cache_ttl_seconds` and `tavily_cache_maxsize`.

## Update 2026-05-19: Low-confidence active-domain retention and term dates

- `CollectionSelector.select()` no longer drops active domains when confidence
  is below `0.55`; it prepends the active domain's mapped collections and then
  appends fallback collections with de-duplication. A low-confidence
  `kehoach` route therefore still searches `kehoach`.
- `KeHoachFilterExtractor._build_date_query()` ignores academic semester tokens
  such as `2025.2`, `20252`, and `2025-2` when building `date_str` wildcard
  filters. With freshness intent and no real calendar posting date, retrieval
  uses `sort_by_date_desc=True` instead.
