# Đánh giá & Lộ trình phát triển — Module Retrieval + Pipeline

> **Phạm vi:** `retrieval/` · `pipeline/flows.py` · `pipeline/rag_pipeline.py`  
> **Ngày:** 2026-04-23  
> **Revision:** v2 — cập nhật sau khi đọc pipeline

---

## 1. Kiến trúc tổng thể

```
User query
    │
    ▼
RAGPipeline.query() / query_stream()
    │
    ├─ [Cache] _route_with_cache()       TTL=45s, max=256
    │       └─ QueryRouter (classifier)
    │               └─ [Tier-3 fallback] LLM domain classify  ← chỉ khi conf < 0.55
    │
    ├─ rag_flow() / rag_flow_stream()
    │       │
    │       ├─ QueryReflector.reflect()  ← rewrite + extract entities (major, cohort)
    │       │       └─ _extract_entities() fallback nếu reflector lỗi
    │       │
    │       ├─ CollectionSelector.select()  ← domain → collections
    │       │
    │       ├─ build_major/cohort_comparison_subqueries()
    │       │       └─ nếu query có "so sánh" + 2 major/cohort → tách thành N subquery
    │       │
    │       ├─ _search_once() × N  (N = 1 hoặc số subquery)
    │       │       ├─ bge_embedder.embed_query()
    │       │       ├─ e5_embedder.embed_query()
    │       │       └─ MultiCollectionSearch.search()
    │       │               ├─ build_collection_filters()       ← major/cohort/date filter
    │       │               ├─ _resolve_filter_with_fallback()  ← ES pre-search + fallback chain
    │       │               ├─ [Thread] QdrantStore.search()   ← BGE-M3 + E5 fused
    │       │               ├─ [Thread] ES.keyword_search()    ← BM25
    │       │               └─ _score_fusion()                  ← min-max normalise + weighted sum
    │       │
    │       ├─ Fallback cascade (nếu raw_results rỗng):
    │       │       1. disable quydinh metadata filter
    │       │       2. mở rộng về tất cả collections
    │       │       3. strip comparison scaffold → query đơn giản hơn
    │       │
    │       ├─ reranker.rerank()          ← cross-encoder (đã có)
    │       ├─ _format_context()          ← char budget 8000
    │       ├─ chat_model.generate_stream()
    │       └─ SelfEvaluator → [Tavily fallback nếu score thấp]
    │
    └─ MongoLogger.log_turn()
```

---

## 2. Đánh giá lại sau khi đọc pipeline

### ✅ Những gì tôi đánh giá sai trong v1

| Điểm tôi nêu (v1) | Thực tế |
|---|---|
| `CollectionSelector` chưa tích hợp | **Đã tích hợp** — `flows.py:615` gọi `_collection_selector.select()` với domain + confidence |
| Comparison subqueries không được xử lý | **Đã xử lý đầy đủ** — `flows.py:654-682` build cả major và cohort comparison plan, có fallback khi subquery rỗng |
| Thiếu reranker | **Đã có** — `reranking.create_reranker()` được gọi trong `RAGPipeline.__init__()` |
| Thiếu fallback khi không có kết quả | **Có cascade fallback 4 tầng** rất rõ ràng trong `flows.py:1201-1270` |

### ✅ Những điểm mạnh bổ sung phát hiện từ pipeline

- **Route cache** (TTL=45s, LRU=256) tránh gọi classifier lặp cho cùng câu hỏi trong phiên.
- **Tier-3 LLM fallback** cho domain routing khi classifier confidence < 0.55 — rất ít tốn kém (~5% queries).
- **Deterministic entity fallback** (`_extract_entities`) đảm bảo `resolved_major`/`resolved_cohort` luôn được điền dù reflector lỗi.
- **`_should_strip_major_for_retrieval`**: logic thông minh — **không** strip major khỏi query khi chỉ search `quydinh` (vì collection đó dùng lexical major cue, không có `major_code` filter).
- **SelfEvaluator + Tavily fallback**: quality gate sau generation.
- **MongoDB logging** với latency và timing breakdown.

---

## 3. Vấn đề còn tồn tại

### 3.1 `HybridSearch` là dead code trong luồng chính ⚠️ P1

`MultiCollectionSearch.search()` **không gọi** `HybridSearch.search()` — nó gọi thẳng `hybrid.qdrant.search()` và `hybrid.es.keyword_search()` rồi tự fuse. `HybridSearch` chỉ đóng vai trò container giữ hai store, không được dùng như một search engine.

Vấn đề: bất kỳ ai đọc code sẽ nghĩ `HybridSearch` là tầng chính xử lý search. Nếu ai refactor và gọi `hybrid.search()` thay vì `MultiCollectionSearch.search()` → dùng RRF thay vì min-max weighted fusion, kết quả sẽ khác.

```python
# flows.py và retrieval/__init__.py không import HybridSearch trực tiếp cho search
# Dòng dưới trong MultiCollectionSearch KHÔNG được gọi:
hybrid.search(query=..., bge_m3_query=..., ...)  # ← dead path

# Thực tế được gọi:
hybrid.qdrant.search(...)   # ← direct store access
hybrid.es.keyword_search(...)
```

**Fix:** Đổi tên `HybridSearch` → `CollectionStores` hoặc thêm docstring rõ ràng, hoặc xóa `HybridSearch.search()` để tránh nhầm.

---

### 3.2 Min-max normalisation bất ổn với pool nhỏ ⚠️ P1

```python
# multi_collection_search.py:_score_fusion()
v_range = v_max - v_min  # pool_k mặc định = 15
norm_v = (item["score"] - v_min) / v_range
```

Khi 15 vector candidates có score cosine gần nhau (ví dụ 0.720–0.735), `v_range = 0.015`. Chunk có score 0.721 sẽ có `norm_v = 0.067` trong khi chunk có score 0.735 có `norm_v = 1.0` — khuếch đại sự chênh lệch nhỏ lên 15× so với thực tế. Thứ tự cuối phụ thuộc vào nhiễu số học hơn là semantic relevance.

**Fix đề xuất:** Chuyển về RRF thuần cho tầng global fusion — nhất quán và không bị vấn đề normalisation:

```python
def _score_fusion_rrf(
    self,
    vector_pool: List[Dict[str, Any]],
    keyword_pool: List[Dict[str, Any]],
    top_k: int,
    vector_weight: float,
    keyword_weight: float,
    rrf_k: int = 60,
) -> List[Dict[str, Any]]:
    combined: Dict[str, Dict[str, Any]] = {}

    for rank, item in enumerate(vector_pool):
        doc_id = item["id"]
        combined[doc_id] = {
            **item,
            "vector_score": item["score"],
            "keyword_score": 0.0,
            "vector_rrf": vector_weight / (rrf_k + rank + 1),
            "keyword_rrf": 0.0,
        }

    for rank, item in enumerate(keyword_pool):
        doc_id = item["id"]
        kw_rrf = keyword_weight / (rrf_k + rank + 1)
        if doc_id in combined:
            combined[doc_id]["keyword_score"] = item["score"]
            combined[doc_id]["keyword_rrf"] = kw_rrf
        else:
            combined[doc_id] = {
                **item,
                "vector_score": 0.0,
                "keyword_score": item["score"],
                "vector_rrf": 0.0,
                "keyword_rrf": kw_rrf,
            }

    for entry in combined.values():
        entry["score"] = (
            entry["vector_rrf"]
            + entry["keyword_rrf"]
            + kehoach_recency_bonus(entry)
        )

    ranked = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
    # Text dedup (giữ nguyên logic hiện tại)
    ...
    return deduped[:top_k]
```

---

### 3.3 ThreadPoolExecutor không có error isolation ⚠️ P1

```python
# multi_collection_search.py
for fut in as_completed(futures):
    name, vecs, kws = fut.result()  # ← raises nếu collection timeout
```

Một collection Qdrant/ES timeout hoặc trả lỗi → crash toàn bộ request. Với 4 collections chạy song song, xác suất ít nhất 1 lỗi cao hơn xác suất 0 lỗi ở môi trường production.

```python
# Fix:
for fut in as_completed(futures):
    col_name = futures[fut]
    try:
        name, vecs, kws = fut.result(timeout=8.0)
    except Exception as exc:
        logger.error(
            "Collection '%s' fetch failed: %s — continuing without it.",
            col_name,
            exc,
        )
        collection_counts[col_name] = {"vector": 0, "keyword": 0, "error": str(exc)}
        continue
```

---

### 3.4 Embedding không được batch khi có comparison subqueries ⚠️ P2

Với query dạng so sánh, `_search_once` được gọi 2 lần (mỗi lần cho một major/cohort):

```python
# flows.py
for subquery, subquery_major in major_compare_plan:   # 2 lần
    raw_results_buffer.extend(_search_once(subquery, ...))
```

Mỗi lần `_search_once` gọi `bge_embedder.embed_query()` và `e5_embedder.embed_query()` riêng biệt → 2 forward passes qua mỗi embedding model. Với BGE-M3 (1024-dim), latency embed ~50-100ms mỗi lần, thêm ~100-200ms tổng cho comparison queries.

**Fix:** Batch embed trước, truyền vector vào `_search_once`:

```python
# flows.py — trước vòng lặp subquery
all_subqueries = [q for q, _ in major_compare_plan] or compare_subqueries or [retrieval_query]
bge_vecs = bge_embedder.embed_queries(all_subqueries)   # batch
e5_vecs = e5_embedder.embed_queries(all_subqueries)     # batch

for i, (subquery, subquery_major) in enumerate(major_compare_plan):
    raw_results_buffer.extend(
        _search_once(subquery, target_collections,
                     precomputed_bge=bge_vecs[i],
                     precomputed_e5=e5_vecs[i], ...)
    )
```

Yêu cầu `BaseEmbedder` có method `embed_queries(texts: List[str]) -> List[List[float]]`.

---

### 3.5 `self.last_sources` / `self.last_intent` / `self.last_timings` không thread-safe ⚠️ P2

```python
# rag_pipeline.py
self.last_sources: List[Dict[str, Any]] = []  # mutated on every call
self.last_intent: str = intent
self.last_timings: Dict[str, float] = {}
```

Nếu `RAGPipeline` được khởi tạo một lần và dùng chung cho nhiều request (pattern thông thường trong FastAPI), hai request đồng thời sẽ ghi đè nhau. Caller đọc `pipeline.last_sources` sau khi stream xong có thể nhận sources của request khác.

**Fix A (đơn giản):** Trả sources và intent trong return value / callback, không lưu vào instance:

```python
# Thay vì instance attribute, trả về tuple:
def query_stream(self, ...) -> Generator[str, None, None]:
    # yield từng chunk...
    # Sau khi stream xong, caller lấy sources từ reranked list được trả về trước đó
    ...
```

**Fix B (nếu cần giữ pattern hiện tại):** Dùng `threading.local()`:

```python
import threading
_thread_local = threading.local()

# Thay self.last_sources = ... bằng:
_thread_local.last_sources = reranked
```

---

### 3.6 `_elapsed_ms` và `_log_timings` định nghĩa 2 lần ⚠️ P3

Hàm này xuất hiện giống hệt nhau trong cả `flows.py` và `rag_pipeline.py`. Nên chuyển vào `pipeline/utils.py` và import dùng chung.

---

### 3.7 `import json as _json` trong hot path ⚠️ P3

```python
# rag_pipeline.py:_llm_domain_classify()
import json as _json  # ← inside function body, called on every Tier-3 invocation
```

Python cache import nên không tốn kém lắm, nhưng theo convention nên đặt ở đầu file.

---

### 3.8 ID mismatch giữa Qdrant và ES vẫn tiềm ẩn ⚠️ P2

`resolve_chunk_ids_for_qdrant()` có logic fallback 2 bước — sự tồn tại của fallback này cho thấy đã từng xảy ra mismatch. Hiện không có script để kiểm tra định kỳ xem 2 store có đồng bộ không sau khi index lại.

---

## 4. Lộ trình phát triển (cập nhật)

### P1 — Sửa ngay

| # | Việc | File | Effort |
|---|---|---|---|
| 3.1 | Làm rõ vai trò `HybridSearch` — đổi tên hoặc xóa `search()` method | `hybrid_search.py` | Thấp |
| 3.2 | Thay min-max bằng RRF trong `_score_fusion` | `multi_collection_search.py` | Thấp |
| 3.3 | Error isolation trong `ThreadPoolExecutor` | `multi_collection_search.py` | Thấp |

### P2 — Sprint tiếp theo

| # | Việc | File | Effort | Impact |
|---|---|---|---|---|
| 3.4 | Batch embedding cho comparison subqueries | `flows.py` + `embedding/base.py` | Trung bình | Giảm latency ~100-200ms |
| 3.5 | Fix thread-safety `last_sources`/`last_intent` | `rag_pipeline.py` | Thấp | Stability |
| 3.8 | Thêm script verify ID alignment Qdrant ↔ ES | `retrieval/index_to_es.py` | Thấp | Reliability |

### P3 — Tối ưu dài hạn

| # | Việc | Ghi chú |
|---|---|---|
| 3.6 | DRY utils — `_elapsed_ms`, `_log_timings` | Chuyển vào `pipeline/utils.py` |
| 3.7 | Move `import json` lên đầu file | Code hygiene |
| Cache tầng retrieval | Cache kết quả `metadata_filter_search` (major_code filter ít thay đổi) | Giảm ES round-trip |
| Async IO | Migrate Qdrant/ES client sang async khi cần scale | Chỉ cần nếu > 50 concurrent users |
| Monitoring timing | Thêm per-stage timing vào `trace_out` (metadata_filter_ms, fusion_ms) | Observability |

---

## 5. Sơ đồ luồng xử lý so sánh (đã hoạt động đúng)

```
Query: "so sánh môn lập trình của IT-E6 và IT-E7"
    │
    ├─ build_major_comparison_subqueries_for_retrieval()
    │       → [("môn lập trình của ngành IT-E6", "IT-E6"),
    │           ("môn lập trình của ngành IT-E7", "IT-E7")]
    │
    ├─ _search_once("môn lập trình của ngành IT-E6", major="IT-E6")
    │       └─ metadata filter: major_code=IT-E6 → HasIdCondition Qdrant
    │
    ├─ _search_once("môn lập trình của ngành IT-E7", major="IT-E7")
    │       └─ metadata filter: major_code=IT-E7 → HasIdCondition Qdrant
    │
    ├─ _dedup_retrieval_candidates(buffer, top_k=20)
    │
    └─ reranker.rerank(query="môn lập trình", docs=20_candidates, top_k=5)
```

Logic này đã đúng và đầy đủ. Cải tiến duy nhất ở đây là batch embed (mục 3.4).

---

## 6. Tóm tắt

Pipeline hiện tại ở mức **production-ready** về mặt logic — routing, reflection, comparison handling, fallback cascade, và reranking đều được xây dựng kỹ. Ba vấn đề cần sửa ngay là kỹ thuật thuần túy (dead code clarity, fusion stability, error isolation) không ảnh hưởng đến correctness của hệ thống nhưng là rủi ro latent. Vấn đề quan trọng nhất về correctness là **thread-safety** (3.5) nếu pipeline được deploy dưới dạng singleton trong FastAPI.

Hệ thống đã có reranker, comparison query handling, và self-eval — những thứ nhiều RAG pipeline chưa có. Hướng phát triển tiếp theo hợp lý nhất là **batch embedding** (giảm latency cho comparison queries) và **retrieval cache** cho metadata filters.
