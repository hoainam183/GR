# Module: `pipeline` — Orchestration Layer (Bộ điều phối chính)

## Tổng quan

Module `pipeline` là **trái tim điều phối** của toàn bộ hệ thống RAG v2. Nó kết nối tất cả các module lại với nhau: routing → reflection → retrieval → reranking → generation → logging. Đây là module duy nhất có tầm nhìn end-to-end về toàn bộ request.

---

## Cấu trúc file

```
pipeline/
├── rag_pipeline.py    # RAGPipeline class — orchestrator chính
└── flows.py           # Các flow cụ thể: rag_flow, chitchat_flow (và streaming)
```

> **Đã di chuyển:**
> - `mongo_logger.py` → `models/mongo_logger.py`
> - `auto_crawler.py` → `scripts/auto_crawler.py`
> - `index_kehoach.py`, `index_quydinh.py`, `index_stsv.py` → `scripts/`

---

## Nhiệm vụ chi tiết

### `rag_pipeline.py` — Class `RAGPipeline`

**Constructor** (`__init__`):
- Khởi tạo `RetrievalService` (embedder BGE-M3 + E5, searcher, reranker)
- Khởi tạo `QueryReflector` (LLM-based query rewrite)
- Khởi tạo `QueryRouter` (classifier-based routing)
- Khởi tạo `ChatModel` (Gemini / LM Studio)
- Khởi tạo `ComplexityRouter` + `ReActAgent` (LangGraph)
- Khởi tạo `ValidityFilter` + `ReferenceResolver`
- Thiết lập **route cache** (TTL=45s) và **reflect cache** (TTL=30s)

**Method `query()` — Non-streaming RAG:**
```
1. history_load      (MongoDB, nếu có session_id và không có history)
2. routing           (QueryRouter.route → intent + domain + confidence)
3. tier3_domain_fallback (LLM classify nếu confidence < 0.55)
4. chitchat_flow      (nếu intent == "chitchat")
   hoặc rag_flow      (nếu intent == "rag")
5. Merge timings + RequestTrace
6. Log to MongoDB
```

**Method `query_stream()` — Streaming:**
- Giống `query()` nhưng generation được stream token-by-token
- Routing + retrieval + reranking vẫn chạy **synchronously** trước
- Sau khi có context, gọi `chat_model.generate_stream()`

**Method `query_agent()` — Force agent path:**
- Bỏ qua QueryRouter, gọi thẳng `ReActAgent.run()`
- Fallback về `query()` nếu agent fail hoặc disabled

**Method `query_v3()` — Smart routing (Week 3):**
```
ComplexityRouter.route(question)
    ├── "chitchat" → _handle_chitchat() (hardcoded reply, no LLM)
    ├── "simple"   → query()  (RAG pipeline)
    └── "complex"  → query_agent()  (LangGraph ReAct)
```

**Caching strategy:**
- Route cache: tránh gọi lại classifier cho cùng query trong 45s
- Reflect cache: tránh gọi lại LLM rewriter cho cùng query trong 30s

---

### `flows.py` — Các flow cụ thể

#### `chitchat_flow()`
```
trim_history → chat_model.generate(mode="chitchat") → return answer
```
**Không có retrieval, không embedding, không reranking.**

#### `rag_flow()` — Full RAG pipeline
```
Step 1: reflection    → QueryReflector.reflect() [LLM call - Gemini]
Step 2: entity extraction → _extract_entities() [regex, no LLM]
Step 3: collection routing → CollectionSelector.select()
Step 4: query normalization → strip_major_from_query_for_retrieval()
Step 5: top_k resolution → _resolve_top_k() [list-query detection]
         - Nếu query chứa "các", "tất cả", "danh sách"... → top_k x2 (max 12)
         - Context char budget cũng tăng tương ứng (x2 = 16000)
Step 6: embed → bge_embedder.embed_query() + e5_embedder.embed_query()
Step 7: search → MultiCollectionSearch.search() [Qdrant + ES parallel]
Step 8: dedup candidates
Step 9: rerank → BGEReranker.rerank()
Step 10: validity_filter → ValidityFilter.filter()
Step 11: reference_resolver → ReferenceResolver.resolve()
Step 12: format_context → _format_context() (budget-limited string)
Step 13: generate → chat_model.generate(mode="rag") [LLM call - Gemini]
Step 14: self_eval → SelfEvaluator.evaluate() [optional, LLM call]
Step 15: tavily_fallback → nếu self_eval fail [optional]
```

**List-query top_k scaling (thêm 2026-05-02):**
- `_LIST_QUERY_RE`: regex detect query liệt kê (các/tất cả/danh sách/liệt kê/những...)
- `_resolve_top_k(base, question)`: nếu match → `min(base * 2, 12)`, else → `base`
- Cũng scale `context_char_budget` lên `_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET * 2`
- **Motivation**: "các học phần tiếng nhật của IT-E6" có 10 chunk riêng biệt, top_k=5 sẽ bỏ sót JP1120, JP2126, JP2132, JP2210, JP2220

#### `rag_flow_stream()`
- Giống `rag_flow()` nhưng step 12 là `generate_stream()` → yield chunks
- Retrieval steps 1-11 vẫn chạy synchronous

---

### `mongo_logger.py` — MongoDB Logging

**Nhiệm vụ:**
- `log_turn()`: ghi một lượt hội thoại (question, answer, sources, timings, latency)
- `get_history()`: lấy lịch sử hội thoại cho session
- `log_agent_trace()`: ghi toàn bộ trace của agent (tool calls, iterations)

**Schema MongoDB:**
```json
{
  "session_id": "...",
  "question": "...",
  "answer": "...",
  "reflected_question": "...",
  "sources": [...],
  "latency_ms": 4500,
  "timings_ms": {"reflection": 800, "search": 200, "rerank": 150, "generate": 3200},
  "timestamp": "2026-04-26T..."
}
```

---

## Các flow quyết định routing

```
Incoming query
    │
    ▼
ComplexityRouter (regex patterns)
    ├── "chitchat"  ────────────► hardcoded reply (0ms LLM)
    ├── "simple"    ──┐
    └── "complex"  ──┘
                      │
                      ▼
               QueryRouter (embedding classifier)
                    │
                    ├── intent="chitchat" ──► chitchat_flow() [LLM]
                    └── intent="rag"
                            │
                            ▼
                     confidence < 0.55?
                    ├── YES → Tier-3 LLM domain classify [LLM]
                    └── NO  → rag_flow() [LLM x2-3]
```

---

## LLM involvement

| Step | LLM | Điều kiện |
|---|---|---|
| Tier-3 domain fallback | Gemini (chat) | Khi classifier confidence < 0.55 |
| Query reflection | Gemini (reflection model) | Luôn luôn (nếu enabled) |
| Answer generation | Gemini (chat) | Luôn luôn |
| Self-evaluation | Gemini (reuse chat) | Khi top_score < threshold |
| Chitchat response | Gemini (chat) | intent == chitchat |

---

## Latency contribution (điển hình)

| Stage | Thời gian điển hình |
|---|---|
| routing (cache miss) | 10-50ms |
| reflection (LLM call) | **500-2000ms** ⚠️ |
| embed BGE + E5 | 30-100ms |
| search (Qdrant + ES parallel) | 50-300ms |
| rerank (BGE cross-encoder) | **100-800ms** |
| generate answer (LLM call) | **3000-15000ms** ⚠️ |
| self_eval (optional, LLM) | 1000-5000ms (thường bị skip) |
| **Total** | **4000-18000ms** |

> ⚠️ **LLM calls là bottleneck chính** của toàn bộ pipeline.

---

### `auto_crawler.py` — Auto Daily Crawl Pipeline (đã di chuyển sang `scripts/`)

**Nhiệm vụ:** Tự động crawl bài viết mới từ ctt.hust.edu.vn hàng ngày. Hỗ trợ 2 pipelines:
- **kehoach**: `DisplayListBaiViet` + `DisplayListKeHoach` → collection `kehoach` (retention 6 tháng)
- **quydinh**: `DisplayQuyChe` → collection `quydinh` (retention 8 năm)

**Classes:**
- `GenericCrawler` — incremental crawl, tham số hóa `list_path`, `id_param`, `output_file`
- `ChunkProcessor` — wrapper quanh `KeHoachChunker`, tham số hóa `source_label`, `chunks_file`
- `DualIndexer` — embed BGE-M3 + E5, upsert Qdrant + ES
- `RetentionManager` — xoá bài >N tháng, tham số hóa `output_file`, `chunks_file`
- `AutoCrawlPipeline` — orchestrator: `run_kehoach()`, `run_quydinh()`, `run()`

**CLI:** `python -m scripts.auto_crawler --pipeline kehoach|quydinh|all --module crawl|chunk|index|retention|all`
