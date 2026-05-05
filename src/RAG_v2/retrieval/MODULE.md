# Module: `retrieval` — Document Retrieval Layer

## Tổng quan

Module `retrieval` chịu trách nhiệm **tìm kiếm và lọc tài liệu** từ kho dữ liệu (Qdrant + Elasticsearch). Đây là module phức tạp nhất về mặt kỹ thuật, thực hiện **hybrid search** (vector + BM25) song song trên nhiều collection, kết hợp metadata pre-filtering, score fusion, và deduplication.

---

## Cấu trúc file

```
retrieval/
├── __init__.py              # Factory: create_retriever()
├── service.py               # RetrievalService — singleton orchestrator
├── multi_collection_search.py  # MultiCollectionSearch — chạy parallel search
├── hybrid_search.py         # HybridSearch — kết hợp Qdrant + ES cho 1 collection
├── qdrant_store.py          # QdrantStore — vector search (BGE-M3 + E5)
├── elasticsearch_store.py   # ElasticsearchStore — keyword search (BM25)
├── metadata_filters.py      # Build metadata pre-filters (major, cohort, date)
├── collection_selector.py   # CollectionSelector — chọn collections từ domain
├── validity_filter.py       # ValidityFilter — lọc chunk không hợp lệ
├── reference_resolver.py    # ReferenceResolver — resolve cross-references
└── base.py                  # BaseRetriever abstract class
```

> **Đã di chuyển:** `search_multi.py`, `index_to_es.py` → `scripts/`

---

## Nhiệm vụ chi tiết

### `service.py` — `RetrievalService`

**Nhiệm vụ:** Singleton service tập trung tất cả retrieval infrastructure.

Được tạo một lần lúc startup, inject vào cả `RAGPipeline` và `agent/tool_adapters`.

```python
service = RetrievalService.from_settings(settings)
# Chứa: bge_embedder, e5_embedder, searcher, reranker, tavily_tool
```

**Quan trọng:** Đảm bảo embedder models chỉ **load 1 lần** vào bộ nhớ, tránh OOM.

---

### `multi_collection_search.py` — `MultiCollectionSearch`

**Nhiệm vụ:** Chạy hybrid search trên **nhiều collection song song** (ThreadPoolExecutor).

**Chiến lược tìm kiếm (7 bước):**

```
Step 0: Metadata pre-search (ES filter)
        → Lấy doc IDs thỏa mãn major/cohort/date filters
        → Truyền vào Qdrant như HasIdCondition
        
Step 1: Vector search (Qdrant, mỗi collection)  ┐ parallel
Step 2: Keyword search (ES BM25, mỗi collection) ┘ threads
        
Step 3: Global pool vector results (sort by cosine, dedup, top pool_k)
Step 4: Global pool keyword results (sort by BM25, dedup, top pool_k)

Step 5: Min-max normalize both score ranges
Step 6: Fusion score = vector_weight * norm_vec + keyword_weight * norm_kw
        + kehoach_recency_bonus()
        
Step 7: Text-level deduplication + return top_k
```

**Adaptive fusion weights:**
- Mặc định: `vector=0.7, keyword=0.3`
- Nếu query chứa course code / "môn học" → **keyword=0.6, vector=0.4** (bias về exact match)

---

### `hybrid_search.py` — `HybridSearch`

Wrapper cho một cặp `(QdrantStore, ElasticsearchStore)`.

```python
hybrid = HybridSearch(qdrant_store, es_store)
# Dùng trong MultiCollectionSearch._fetch_one()
```

---

### `qdrant_store.py` — `QdrantStore`

**Nhiệm vụ:** Vector similarity search trên Qdrant.

- **Multi-vector:** BGE-M3 vector + E5 vector riêng biệt, score fusion nội bộ
- **Payload:** mỗi point có `text`, `metadata` (source, title, major_code, date…)
- **Filter:** Nhận `HasIdCondition` từ metadata pre-search

```python
results = qdrant.search(bge_m3_query=bge_vec, e5_query=e5_vec, top_k=20)
```

---

### `elasticsearch_store.py` — `ElasticsearchStore`

**Nhiệm vụ:** Keyword (BM25) search + metadata filtering.

- **BM25 search:** `keyword_search(query, top_k, filters)` — tìm kiếm từ khóa
- **Metadata filter search:** `metadata_filter_search(es_query)` — lọc theo metadata
- **Chunk ID resolution:** `resolve_chunk_ids_for_qdrant()` — map ES doc IDs → Qdrant IDs

**Boosting đặc biệt:**
- `should` clauses với boost cao hơn cho: tên khoá học, mã khoá học, từ khoá chương trình

---

### `metadata_filters.py` — Pre-filtering

**Nhiệm vụ:** Xây dựng filter chain cho từng collection dựa trên entities được extract.

**Filter logic theo collection:**

| Collection | Metadata được filter |
|---|---|
| `ctdt` | `major_code`, `applicable_major` |
| `quydinh` | `major_code`, `applicable_major` (looser) |
| `kehoach` | `academic_year`, `semester`, date range |
| `stsv` | Không filter (toàn bộ) |

**Fallback chain:** Nếu filter chặt → 0 kết quả → thử filter lỏng hơn → nếu vẫn 0 → bỏ filter.

**Hàm quan trọng:**
- `build_collection_filters()` — entry point chính
- `_extract_major_code()` — regex extract major code từ query
- `extract_major_codes()` — extract tất cả major codes
- `strip_major_from_query_for_retrieval()` — loại major phrase khỏi query để tránh bias

---

### `collection_selector.py` — `CollectionSelector`

**Nhiệm vụ:** Chọn tập collections cần search dựa trên domain + confidence.

```python
# domain="ctdt", confidence=0.9 → ["ctdt"]
# domain="ctdt", confidence=0.6 → ["ctdt", "quydinh"]  (mở rộng thêm)
# domains=["ctdt","quydinh"] → ["ctdt", "quydinh"]
```

---

### `validity_filter.py` — `ValidityFilter`

**Nhiệm vụ:** Loại bỏ chunks không hợp lệ sau reranking.

Kiểm tra: độ dài tối thiểu, chunk không phải header/footer, nội dung có nghĩa.

---

### `reference_resolver.py` — `ReferenceResolver`

**Nhiệm vụ:** Resolve cross-references trong retrieved chunks.

Ví dụ: chunk nói "xem điều 3.2" → resolver tìm thêm chunk của điều 3.2 và merge vào.

---

## Luồng tổng hợp

```
(bge_vec, e5_vec, query, resolved_major, resolved_cohort, target_collections)
    │
    ▼
MultiCollectionSearch.search()
    │
    ├── build_collection_filters() → metadata pre-filters per collection
    │
    ├── ThreadPoolExecutor (parallel per collection):
    │       ├── QdrantStore.search(bge_m3_query, e5_query, filter=HasIdCondition)
    │       └── ElasticsearchStore.keyword_search(query, filter=es_filter)
    │
    ├── Global sort + dedup (vector pool + keyword pool)
    ├── Score fusion (min-max normalize + weighted sum)
    └── Text dedup → return top_k candidates
    
    ▼
BGEReranker.rerank() [xem module reranking]

    ▼
ValidityFilter.filter()

    ▼
ReferenceResolver.resolve()

    ▼
Reranked documents (top 5-10)
```

---

## LLM involvement

Module `retrieval` **không sử dụng LLM**. Chỉ dùng:
- Local neural models (BGE-M3, E5) cho embedding
- Qdrant API cho vector search
- Elasticsearch API cho BM25 search

---

## Latency contribution

| Component | Thời gian điển hình |
|---|---|
| Metadata pre-search (ES filter) | 20-80ms |
| Qdrant vector search (per collection) | 20-100ms |
| ES keyword search (per collection) | 10-50ms |
| **Parallel multi-collection search** | **50-200ms** (wall clock) |
| Score fusion + dedup | 1-5ms |
| ValidityFilter | 1-5ms |
| ReferenceResolver | 5-50ms |
| **Tổng module retrieval** | **~80-340ms** |
