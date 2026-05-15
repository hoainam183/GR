# 🔍 RAG v2 — Retrieval Strategy Deep Audit (v2 — Corrected)

> **Phạm vi**: Chunking, Top-k, Re-ranking, Context Assembly, Late/Early Chunking
> **Ngày audit**: 2026-05-14 | **Hệ thống**: RAG v2 — HUST Academic Advisory Chatbot

---

## 1. CHUNKING

### 1.1 Hiện trạng (xác minh từ source code)

| Thuộc tính | Giá trị | Source |
|---|---|---|
| **Chiến lược chính** | Recursive Parent-Child (structure-based) | [recursive_chunker.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/chunking/chunker/recursive_chunker.py) |
| **Child chunk_size** | 1024 chars, overlap = 0 | Thiết kế có chủ đích — H2 headings cung cấp boundary tự nhiên |
| **Parent chunk max** | 10,000 chars (truncated) | Dùng cho context hierarchy, **KHÔNG index vào Qdrant** |
| **Indexing policy** | **Chỉ child chunks** (`level == "child"`) | [index_quydinh.py:76](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/scripts/index_quydinh.py#L76) |
| **Table protection** | ✅ Bảng < chunk_size được bảo vệ, bảng lớn tách theo rows | `_fix_mid_table_chunks()`, `_split_table_by_rows()` |
| **Section context injection** | ✅ Heading context inject cho chunks không có heading | `_inject_section_context()` |
| **Khoản context injection** | ✅ Sub-item (`a)`, `b)`) nhận context từ khoản cha | `_inject_khoản_context()` |
| **Chunker variants** | `RecursiveChunker`, `ArticleLegalChunker`, `OlmOcrLegalChunker`, `KeHoachChunker`, `StsvChunker` | Mỗi data type có chunker riêng |

### 1.2 Câu hỏi chẩn đoán

| # | Câu hỏi | Phát hiện |
|---|---|---|
| Q1 | Parent chunks có bị index gây duplicate không? | ✅ **KHÔNG** — `index_quydinh.py` filter `level == "child"` trước khi index. Parent chỉ dùng cho hierarchy metadata. |
| Q2 | Overlap = 0 có gây mất context? | ⚠️ **Rủi ro thấp-trung bình**. H2 heading boundaries cung cấp context tự nhiên. `_inject_section_context()` và `_inject_khoản_context()` bù đắp thêm. Tuy nhiên prose-heavy sections dài vẫn có thể mất context ở ranh giới 2 child chunks liền kề. |
| Q3 | 1024 chars phù hợp cho domain? | ✅ **Phù hợp**. Tài liệu quy định/CTDT có cấu trúc Điều/khoản rõ ràng, 1024 chars đủ chứa 1 Điều hoàn chỉnh. |
| Q4 | Table splitting có mất ngữ cảnh? | ✅ **Xử lý tốt**. Header auto-inject cho table continuation chunks. |

### 1.3 Đánh giá

> [!TIP]
> **Điểm mạnh nổi bật**: Khoản context injection (`_inject_khoản_context`) giải quyết đúng pain point khi RecursiveCharacterTextSplitter cắt giữa khoản pháp lý — đây là feature domain-specific rất có giá trị.

> [!NOTE]
> **Cải thiện tiềm năng**: Thêm `chunk_overlap = 64–128 chars` cho prose-heavy sections (giữ overlap = 0 cho table/structured sections) để giảm boundary information loss.

---

## 2. TOP-K & RETRIEVAL PIPELINE

### 2.1 Hiện trạng (xác minh từ source code)

**Lưu ý quan trọng**: `top_k` **không hardcode** — configurable từ `settings.top_k` (default 5) và API request. Reranker sử dụng **threshold-based filtering** — tất cả documents vượt `score_threshold` đều được giữ, bất kể `top_k`.

| Giai đoạn | Parameter | Giá trị | Source |
|---|---|---|---|
| Per-vector search (Qdrant) | `per_vector_k` | `min(top_k * 2, 100)` | [qdrant_store.py:156](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/retrieval/qdrant_store.py#L156) |
| Per-collection vector | `vector_top_k` | 50 | [settings.py:128](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/config/settings.py#L128) |
| Per-collection keyword | `keyword_top_k` | 50 | settings.py |
| Global vector pool | `vector_pool_k` | 40 | settings.py |
| Global keyword pool | `keyword_pool_k` | 40 | settings.py |
| Raw candidate pool | `raw_candidate_k` | `max(top_k * 4, 40)` | [flows.py:102](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/pipeline/flows.py#L102) |
| Reranker output | `top_k` | Configurable (default 5) | Threshold-based: chỉ giữ docs ≥ `score_threshold` |
| Default vector weight | `vector_weight` | **0.7** (MCS) / 0.8 (settings fallback) | [multi_collection_search.py:82](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/retrieval/multi_collection_search.py#L82) |
| Default keyword weight | `keyword_weight` | **0.3** (MCS) / 0.2 (settings fallback) | multi_collection_search.py:83 |

### 2.2 Pipeline Flow (chính xác)

```
Query → [BGE-M3 + E5] embed (parallel)
  ↓
Per collection (4 collections × parallel threads):
  ├─ QdrantStore.search(bge_m3, e5, filter=HasIdCondition) → vector results (50)
  └─ ES.keyword_search(query, filter=es_filter)            → keyword results (50)
  ↓
Global Vector Pool (top 40, dedup by ID) + Keyword Pool (top 40, dedup by ID)
  ↓
_score_fusion: min-max normalize → weighted sum (vec*0.7 + kw*0.3)
             + kehoach_recency_bonus + text-level dedup
  ↓
Adaptive weights: course queries → vec*0.4, kw*0.6
  ↓
~40 candidates → BGE Reranker → threshold filter (text≥0.0, table≥-5.0) → top_k
  ↓
ValidityFilter → ReferenceResolver → Context Format → LLM
```

### 2.3 Score Fusion — hai tầng (quan trọng)

| Tầng | Vị trí | Thuật toán | Mục đích |
|---|---|---|---|
| **Tầng 1: BGE+E5** | `QdrantStore._fuse_results` | Weighted sum `0.5*bge + 0.5*e5` | Kết hợp hai vector spaces |
| **Tầng 2: Vector+Keyword** | `MultiCollectionSearch._score_fusion` | Min-max normalize + weighted sum + recency bonus | Semantic vs keyword fusion |

> `HybridSearch._rrf_fuse` (RRF) chỉ dùng khi `HybridSearch.search()` gọi trực tiếp (không qua `MultiCollectionSearch`).

### 2.4 Câu hỏi chẩn đoán

| # | Câu hỏi | Phát hiện |
|---|---|---|
| Q1 | Retrieval funnel có quá aggressive không? | ⚠️ **Cần theo dõi**. 400 raw → 40+40 pool → ~40 fused → threshold-based rerank. Compression ratio phụ thuộc threshold. Nếu threshold quá cao, documents niche bị loại. |
| Q2 | Adaptive fusion weights có hoạt động tốt? | ✅ **Rất tốt**. Auto-detect course codes và course hints, shift sang kw=0.6 cho exact-match queries. |
| Q3 | Metadata pre-filter fallback chain? | ✅ **Rất tốt**. `_resolve_filter_with_fallback()` thử từng query, cuối cùng là full collection scan. |
| Q4 | Dual-vector (BGE-M3 + E5) có hiệu quả? | ✅ **Tốt**. BGE-M3 mạnh semantic tiếng Việt, E5-multilingual bổ trợ cross-lingual. |

### 2.5 Đề xuất cải thiện

1. **Tăng `vector_pool_k`/`keyword_pool_k` lên 50-60** — Giảm risk mất relevant documents trong multi-collection queries. Cost: negligible.
2. **Log fusion weight decisions** — Ghi lại khi adaptive weights kick in để monitor effectiveness.

---

## 3. RE-RANKING

### 3.1 Hiện trạng

| Thuộc tính | Giá trị | Source |
|---|---|---|
| **Model** | `BAAI/bge-reranker-v2-m3` (cross-encoder) | [bge_reranker.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/reranking/bge_reranker.py) |
| **Score threshold (text)** | 0.0 (logit boundary) | settings.py:141 |
| **Score threshold (table)** | -5.0 (relaxed) | settings.py:142, có thể override qua `.env` |
| **Filtering order** | Threshold **TRƯỚC** top_k | bge_reranker.py:137-145 — **đúng logic** |
| **Device** | Auto-detect (CUDA > MPS > CPU) | |
| **Bypass logic** | Skip reranker cho curriculum table chunks (kỳ/chẵn/lẻ queries) | `tool_adapters.py` |

### 3.2 Phân tích

| # | Câu hỏi | Phát hiện |
|---|---|---|
| Q1 | BGE-reranker-v2-m3 phù hợp tiếng Việt? | ✅ **Rất phù hợp**. Multilingual SOTA cross-encoder. |
| Q2 | Threshold 0.0 hợp lý? | ✅ **Hợp lý**. Natural logit boundary, borderline docs pass → LLM quyết định cuối. |
| Q3 | Table threshold -5.0 có quá lỏng? | ⚠️ **Có thể**. -5.0 gần pass tất cả table chunks. Default constructor là -3.0, `.env` có thể override → nên xem xét nâng lên -3.0. |
| Q4 | Reranker trên CPU có phải bottleneck? | ⚠️ **Có**. MODULE.md ghi: CPU = 300-1500ms, GPU = 50-200ms. Nếu chạy CPU → bottleneck đáng kể. |

### 3.3 Đề xuất

1. **Xem xét ColBERT late interaction** — BGE-M3 hỗ trợ ColBERT vectors (hiện `return_colbert_vecs=False`). ColBERT có thể cải thiện re-ranking cho long chunks.
2. **Log rerank score distribution** — Histogram logging để monitor model performance drift.
3. **Tune table_score_threshold** → -3.0 sau khi evaluate recall.

---

## 4. CONTEXT ASSEMBLY

### 4.1 Hiện trạng

| Thuộc tính | Giá trị | Source |
|---|---|---|
| **Per-doc char limit** | 1,500 chars | flows.py:38 |
| **Total context budget** | 8,000 chars (×2 cho list queries = 16,000) | flows.py:39 |
| **History limit** | 8 messages, 400 chars/msg, total 2,000 chars | flows.py:33-35 |
| **Context format** | `--- Văn bản: {title} [{meta}]\n{text}` | `_format_context()` |
| **Metadata injection** | major_code, major_name, applicable_cohort | flows.py:248-254 |
| **Profile injection** | User profile prepended khi không có explicit major code | `_should_prepend_profile_note()` |
| **Ordering** | Rerank score descending | Preserved from reranker |
| **Deduplication** | Text-level dedup (first 200 chars) + ID dedup | `_dedup_retrieval_candidates()` |

### 4.2 Phân tích

| # | Câu hỏi | Phát hiện |
|---|---|---|
| Q1 | 8000 chars budget đủ? | ⚠️ **Quá conservative**. Gemini Flash context window ~1M tokens. 8000 chars ≈ 3000 tokens = 0.3% capacity. Nhiều câu trả lời có thể thiếu context, đặc biệt so sánh CTDT, danh sách học phần. |
| Q2 | Context ordering tối ưu? | ✅ **Tốt**. Score descending → relevant nhất ở đầu. Research (Lost in the Middle) confirm LLMs attend best ở đầu context. |
| Q3 | Cross-reference chunks insert đúng? | ✅ **Đúng**. `ReferenceResolver` insert ngay sau chunk chứa reference. |
| Q4 | Context recovery khi quá dài? | ✅ **Có**. Graceful degradation: retry với top 2 docs, budget 1500, history limit 3. |
| Q5 | Interleave chunks từ nhiều sources? | ⚠️ **Nên cải thiện**. Chunks từ nhiều collections interleave theo score, có thể gây confusion cho LLM khi 2 quy định khác nằm cạnh nhau. |

### 4.3 Đề xuất

1. 🔴 **Tăng context budget lên 12,000–15,000 chars** — Gemini Flash thừa capacity. Extra 5000 tokens ≈ +200ms latency — negligible.
2. **Group chunks by document/source** — Thay vì interleave, group chunks cùng document liên tiếp → coherent hơn cho LLM.
3. **Tăng per-doc limit lên 2,000 chars** — 1,500 có thể truncate bảng quan trọng.

---

## 5. LATE CHUNKING vs EARLY CHUNKING

### 5.1 Hiện trạng

| Đặc điểm | Hiện tại |
|---|---|
| **Phương pháp** | Early Chunking (chunk → embed independently) |
| **Embedding max_length** | 512 tokens (cả BGE-M3 và E5) |
| **Cross-chunk context** | Không — mỗi embedding isolated |
| **Compensations** | Section context injection, khoản context injection, hierarchy_path metadata |

### 5.2 Đánh giá

**Early Chunking là lựa chọn đúng** cho hệ thống hiện tại vì:
1. BGE-M3 và E5 cùng có `max_length = 512 tokens` → không thể embed full document
2. Hệ thống đã compensate tốt bằng context injection (headings + khoản)
3. Late chunking cần model hỗ trợ long context (≥8192 tokens) và refactor embedding pipeline

### 5.3 Đề xuất (90+ ngày)

Khi upgrade embedding model → xem xét `jina-embeddings-v3` hoặc `nomic-embed-text-v1.5` (8192 tokens) để thử late chunking trên subset documents.

---

## 📊 TỔNG HỢP

### ✅ Điểm mạnh cần giữ nguyên

| # | Điểm mạnh | Chi tiết |
|---|---|---|
| 1 | **Adaptive Fusion Weights** | Tự động shift vec/kw weight cho course queries (0.7/0.3 → 0.4/0.6). Giải quyết semantic vs exact-match trade-off. |
| 2 | **Context Injection (Section + Khoản)** | Domain-specific feature rất có giá trị. Chunk isolated vẫn có heading context và khoản cha. |
| 3 | **Child-only Indexing** | Parent chunks chỉ dùng cho hierarchy metadata, không index → không lãng phí context slots. |
| 4 | **Gradual Metadata Fallback Chain** | `_resolve_filter_with_fallback()` → graceful degradation, không bao giờ zero-result. |
| 5 | **Cross-Reference Resolution** | Auto-detect "khoản 1 Điều 5", fetch referenced chunk, insert sau chunk gốc. Critical cho legal RAG. |
| 6 | **ValidityFilter** | Loại documents superseded dựa trên `document_lineage.json`. Ngăn LLM dùng quy định cũ. |
| 7 | **Threshold-based Reranking** | Dual threshold (text vs table) với filter TRƯỚC top_k. Giữ tất cả docs relevant, không cắt cứng. |
| 8 | **Dual-Vector Ensemble** | BGE-M3 + E5 tăng recall coverage cho multilingual content. |
| 9 | **Table Protection** | Không tách giữa bảng, auto-inject header cho table continuation. |

---

### 🚨 Top 3 Vấn đề cần giải quyết ngay

#### 🔴 P0: Context Budget quá Conservative

**Vấn đề**: `_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET = 8000` chars ≈ 3000 tokens, chỉ dùng 0.3% capacity của Gemini Flash (1M tokens). Khi user hỏi danh sách (list query), scaled budget = 16,000 chars vẫn rất nhỏ. Với `_DEFAULT_CONTEXT_DOC_CHAR_LIMIT = 1500`, bảng dài bị truncate.

**Impact**: LLM trả lời thiếu thông tin, đặc biệt so sánh CTDT, danh sách học phần, bảng quy đổi.

**Fix**: 
- Tăng `_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET` → **12,000–15,000** chars
- Tăng `_DEFAULT_CONTEXT_DOC_CHAR_LIMIT` → **2,000** chars
- Latency impact: +200ms (Gemini inference linear scaling) — negligible

---

#### 🟡 P1: Thiếu Retrieval Quality Monitoring & Evaluation

**Vấn đề**: Không có automated evaluation pipeline đo retrieval quality (Recall@k, MRR, nDCG). File `retrieval_evaluation_v2.md` tồn tại nhưng chỉ là documentation. Mọi config changes (chunk_size, weights, thresholds) đều blind tuning.

**Impact**: Không phát hiện khi retrieval quality degrade. Không có data-driven basis cho tuning decisions.

**Fix**:
- Tạo golden test set 50-100 question-answer pairs với expected source chunks
- Implement `Recall@5`, `MRR@5`, `nDCG@5` metrics
- Eval tool: `chunk_loader.py` + `dataset_generator.py` đã tồn tại trong `eval/RAG/`  — cần integrate thành automated pipeline

---

#### 🟡 P2: Reranker CPU Bottleneck

**Vấn đề**: BGE-reranker trên CPU = 300-1500ms (theo MODULE.md). Đây là bottleneck đáng kể trong pipeline tổng (chiếm 30-60% total latency trên CPU).

**Impact**: Latency cao cho mỗi query, đặc biệt khi candidate pool lớn (list queries có raw_candidate_k = 48).

**Fix**:
- **Short-term**: Giảm `raw_candidate_k` cho non-list queries
- **Medium-term**: Deploy trên GPU hoặc sử dụng ONNX Runtime optimization
- **Long-term**: Xem xét ColBERT late interaction (lighter inference, similar quality)

---

### 📅 Lộ trình cải thiện 30/60/90 ngày

#### 30 ngày — Quick Wins

| # | Task | Priority | Effort | Impact |
|---|---|---|---|---|
| 1 | Tăng context budget 8000 → 12000+ chars | 🔴 P0 | XS (<1h) | High — more complete answers |
| 2 | Tăng per-doc limit 1500 → 2000 chars | 🔴 P0 | XS | Medium — preserve tables |
| 3 | Tăng `vector_pool_k`/`keyword_pool_k` 40 → 50 | 🟡 | XS | Medium — better recall |
| 4 | Tạo golden eval set (30 questions) | 🟡 | M (4-8h) | High — enables data-driven tuning |
| 5 | Thêm rerank score distribution logging | 🟢 | S | Medium — monitoring |

#### 60 ngày — Quality Optimization

| # | Task | Priority | Effort | Impact |
|---|---|---|---|---|
| 6 | Implement Recall@k / MRR@k eval pipeline | 🔴 P1 | L (8-16h) | High — systematic measurement |
| 7 | Group chunks by document trong context format | 🟡 | M | Medium — coherent LLM context |
| 8 | Tune table_score_threshold (-5.0 → -3.0) | 🟢 | XS + eval | Low-medium |
| 9 | ONNX optimize reranker (CPU perf) | 🟡 P2 | M | Medium — reduce 300-1500ms bottleneck |
| 10 | Add chunk_overlap = 100 cho prose sections | 🟡 | M | Medium — boundary context |

#### 90 ngày — Advanced Retrieval

| # | Task | Priority | Effort | Impact |
|---|---|---|---|---|
| 11 | ColBERT late interaction reranking | 🟡 | L | Potentially high — lighter + accurate |
| 12 | Hypothetical Document Embedding (HyDE) | 🟡 | L | High — retrieval boost |
| 13 | A/B test framework for retrieval configs | 🟡 | L | High — systematic improvement |
| 14 | Eval late chunking với long-context model | 🟢 | XL | Potentially high |
| 15 | Fine-tune BGE-M3 on domain data | 🟢 | XL | High — domain-specific embeddings |

---

> [!TIP]
> **Tổng quan**: Hệ thống RAG v2 có architecture rất solid — đặc biệt child-only indexing, adaptive fusion, cross-reference resolution, validity filtering, và threshold-based reranking. Các vấn đề chính tập trung vào **efficiency** (context budget quá conservative) và **observability** (thiếu eval metrics) hơn là correctness. Priority 1 là tăng context budget — change đơn giản nhất mà high-impact nhất.
