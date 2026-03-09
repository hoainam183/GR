# 📋 Báo Cáo Kế Hoạch Đồ Án Tốt Nghiệp — 15 Tuần

> **Đề tài**: Xây dựng hệ thống RAG Chatbot tư vấn đại học thông minh  
> **Kiến trúc**: 8 Layers — Embedding → Hybrid Retrieval → Reranking → Query Router & Reflection → Chat Model → Self Evaluation → Tool Search → MongoDB Memory  
> **Nền tảng**: Mobile-first, UI/UX chất lượng cao  
> **Dữ liệu**: Đầy đủ, chính xác, có cấu trúc hóa  

---

## Tổng quan các Phase và Timeline

| Phase | Nội dung | Tuần | % Tích lũy | Ưu tiên |
|-------|----------|------|-------------|---------|
| **Phase 1** | Data Processing + Embedding + Hybrid Retrieval | Tuần 1–4 | 25% | 🔴 Cao nhất |
| **Phase 2** | Reranking + Query Router & Reflection | Tuần 5–6 | 40% | 🔴 Cao |
| **Phase 3** | Chat Model + Self Evaluation + Student Context | Tuần 7–9 | 60% | 🔴 Cao |
| **Phase 4** | Tool Search + MongoDB Memory + Module Routing | Tuần 10–11 | 75% | 🟡 Trung bình |
| **Phase 5** | FastAPI Backend + Pipeline Integration + Mobile UI | Tuần 12–13 | 90% | 🟡 Trung bình |
| **Phase 6** | Evaluation + Optimization + Báo cáo | Tuần 14–15 | 100% | 🟢 Hoàn thiện |

---

## Phase 1: Data Processing + Embedding + Hybrid Retrieval (Tuần 1–4) — 25%

> **Mục tiêu**: Xử lý & cấu trúc hóa dữ liệu đại học, xây dựng nền tảng embedding ensemble và hybrid search.

### 📅 Tuần 1 — Thu thập & Xử lý dữ liệu (0% → 7%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| Khảo sát nguồn dữ liệu | Thu thập tài liệu: CTĐT, quy chế, thông báo, hướng dẫn từ website trường | Danh sách nguồn dữ liệu |
| Xử lý dữ liệu thô | Parse PDF/HTML, trích xuất text, bảng biểu, metadata (ngày ban hành, phạm vi áp dụng, khóa áp dụng) | Raw text + metadata |
| Cấu trúc hóa dữ liệu | Gắn nhãn metadata cho từng văn bản: `effective_date`, `expiry_date`, `applicable_cohort` (K66, K67,...), `applicable_major`, `document_type` | Structured documents |
| Chunking strategy | Thiết kế chunking phù hợp: semantic chunking, parent-child chunks, giữ nguyên metadata | Chunked documents |
| Xây dựng training data | Tạo bộ Q&A pairs từ dữ liệu thực tế (50+ câu) | Training dataset v1 |

### 📅 Tuần 2 — Embedding Layer (7% → 13%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| `BaseEmbedder` | Viết abstract base class chuẩn interface | `embedding/base.py` |
| `BGEm3Embedder` | Wrapper cho BAAI/bge-m3, batch encoding | `embedding/bge_m3.py` |
| `E5MultilingualEmbedder` | Wrapper cho multilingual-e5-large | `embedding/e5_multilingual.py` |
| `EnsembleEmbedder` | Weighted average kết hợp 2 models | `embedding/ensemble.py` |
| Benchmark embedding | Đo tốc độ + quality trên dữ liệu đại học Việt Nam | Benchmark report |

### 📅 Tuần 3 — Qdrant + Elasticsearch Setup (13% → 19%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| Setup Qdrant | Docker, collection config, 2 vector fields (bge-m3, e5) | Qdrant running |
| `QdrantStore` | `index_documents()`, `search()`, `delete_by_metadata()` | `retrieval/qdrant_store.py` |
| Setup Elasticsearch | Docker, custom Vietnamese analyzer (lowercase, unicode folding) | ES running |
| `ElasticsearchStore` | `index_documents()`, `keyword_search()` | `retrieval/elasticsearch_store.py` |
| Index dữ liệu | Embed + index toàn bộ chunks vào Qdrant + ES | Indexed data |

### 📅 Tuần 4 — Hybrid Search + Test Phase 1 (19% → 25%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| `HybridSearcher` | Vector (Qdrant) + Keyword (ES) → RRF fusion, configurable weights | `retrieval/hybrid_search.py` |
| Config retrieval | Top_k, thresholds, weights | `retrieval/config.py` |
| Test end-to-end P1 | Test embedding → search pipeline với 20+ câu hỏi thực tế | Test report P1 |
| **Viết báo cáo P1** | Mô tả phương pháp embedding, hybrid search, input/output, kiến trúc | Chương báo cáo P1 |

### ✅ Kết quả Phase 1

| Deliverable | Mô tả |
|-------------|-------|
| **Structured Data** | Dữ liệu đại học đã cấu trúc hóa với metadata đầy đủ (khóa, ngành, hiệu lực) |
| **Dual Embedding** | BGE-M3 + E5-large ensemble cho retrieval chất lượng cao |
| **Vector + Keyword Store** | Qdrant + Elasticsearch sẵn sàng |
| **Hybrid Search** | RRF fusion hoạt động tốt |

---

## Phase 2: Reranking + Query Router & Reflection (Tuần 5–6) — 40%

> **Mục tiêu**: Thêm reranking layer, xây dựng query router thông minh và cơ chế reflection.

### 📅 Tuần 5 — Reranking + Query Router (25% → 33%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| `BGEReranker` | Load BAAI/bge-reranker-v2-m3, `rerank(query, docs)` → sorted top-K | `reranking/bge_reranker.py` |
| Tích hợp reranker | Nối reranker vào sau hybrid search | Integrated pipeline |
| `QueryRouter` | Phân loại intent: Chit-chat / RAG / Tool Search bằng LLM + few-shot | `query/router.py` |
| Router prompts | Few-shot prompts cho classification | `query/prompts.py` |
| **Xử lý phạm vi hiệu lực** | Logic xác định văn bản/quy định nào đang có hiệu lực tại thời điểm hỏi, ưu tiên văn bản mới nhất | `query/validity_checker.py` |

### 📅 Tuần 6 — Query Reflection + Test Phase 2 (33% → 40%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| `QueryReflector` | Rewrite, clarify, format standardize, add context từ history | `query/reflection.py` |
| Chain pipeline | Router → Reflection → Embedding (cho RAG flow) | Integrated chain |
| **Validity scope resolver** | Khi cùng 1 câu hỏi có nhiều phương án trả lời → chọn phương án có phạm vi hiệu lực đúng nhất | `query/validity_resolver.py` |
| Test end-to-end P2 | Test router + reflection + reranking với các loại câu hỏi khác nhau | Test report P2 |
| **Viết báo cáo P2** | Mô tả reranking model, query routing, reflection, xử lý hiệu lực | Chương báo cáo P2 |

### ✅ Kết quả Phase 2

| Deliverable | Mô tả |
|-------------|-------|
| **Reranker** | BGE-v2-M3 rerank, chọn top 5 chính xác nhất |
| **Router** | Tự phân loại chitchat / RAG / tool search |
| **Reflection** | Query rewrite + context enrichment |
| **Validity Checker** | Xác định phạm vi hiệu lực của quy định, CTĐT theo khóa/ngành |

---

## Phase 3: Chat Model + Self Evaluation + Student Context (Tuần 7–9) — 60%

> **Mục tiêu**: Xây dựng chat model, self-evaluation, và module nhận diện ngữ cảnh sinh viên.

### 📅 Tuần 7 — Chat Model Layer (40% → 47%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| `ChatModel` | Wrapper LLM API, `generate(query, context, history)`, streaming response | `llm/chat_model.py` |
| System Prompts | Prompt RAG (trích nguồn), prompt chitchat, prompt university domain | `llm/prompts.py` |
| **Student Context Prompt** | Prompt biết ngữ cảnh sinh viên (khóa, ngành, CTĐT) để trả lời chính xác | `llm/student_prompts.py` |
| Response formatting | Format response với citations, nguồn trích dẫn, điều hướng | Response template |

### 📅 Tuần 8 — Self Evaluation + Student Profile (47% → 53%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| `SelfEvaluator` | Check quality, hallucination, completeness → pass/fail + reason | `llm/self_eval.py` |
| Fallback mechanism | Self-eval FAIL → trigger Tavily search → re-generate | Fallback pipeline |
| **`StudentProfileManager`** | Thu thập & lưu thông tin SV: khóa (K66, K67,...), ngành, CTĐT đang theo | `student/profile_manager.py` |
| **Cohort-aware retrieval** | Khi SV là K66 → ưu tiên CTĐT/quy định áp dụng cho K66 | `student/cohort_filter.py` |

### 📅 Tuần 9 — Module Routing + Test Phase 3 (53% → 60%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| **Module Router** | Điều hướng câu hỏi đến module chuyên biệt: CTĐT, quy chế, học phí, lịch thi,... | `modules/module_router.py` |
| **CTĐT Module** | Module chuyên tư vấn CTĐT: liệt kê môn, tiên quyết, tín chỉ, so sánh khóa | `modules/ctdt_module.py` |
| Phân tích thông tin SV | Từ khóa + ngành → xác định CTĐT áp dụng, quy định liên quan | Analysis logic |
| Test end-to-end P3 | Test chat model + self-eval + student context với scenarios thực tế | Test report P3 |
| **Viết báo cáo P3** | Mô tả mô hình LLM, self-eval, student context, method & input/output | Chương báo cáo P3 |

### ✅ Kết quả Phase 3

| Deliverable | Mô tả |
|-------------|-------|
| **Chat Model** | LLM wrapper với streaming, multi-prompt, student-aware |
| **Self Evaluation** | Tự kiểm tra chất lượng, trigger fallback nếu kém |
| **Student Context** | Nhận diện khóa, ngành, CTĐT → trả lời chính xác cho từng SV |
| **Module Router** | Điều hướng sang module chuyên biệt (CTĐT, quy chế,...) |

---

## Phase 4: Tool Search + MongoDB Memory (Tuần 10–11) — 75%

> **Mục tiêu**: Web search fallback, persistence layer, caching.

### 📅 Tuần 10 — Tavily + MongoDB (60% → 68%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| `TavilySearchTool` | `search(query)` → web results, parse & format, rate limiting | `tools/tavily_search.py` |
| Tích hợp fallback | Self-eval FAIL → Tavily → Chat Model → Final answer | Fallback integrated |
| Setup MongoDB | Docker/Atlas, connection pooling, retry logic | MongoDB running |
| `ChatHistoryStore` | `save_message()`, `get_history()`, `clear_history()` | `memory/chat_history.py` |
| `ConversationState` | Lưu answer + metadata, session tracking | `memory/conversation.py` |

### 📅 Tuần 11 — Caching + Additional Modules + Test Phase 4 (68% → 75%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| **Caching Layer** | Cache repeated queries + responses, TTL-based invalidation | `cache/query_cache.py` |
| **Student Profile DB** | Lưu profile SV vào MongoDB, auto-load khi chat | `memory/student_store.py` |
| **Additional Modules** | Module học phí, module lịch thi, module thủ tục hành chính | `modules/*.py` |
| Test end-to-end P4 | Test Tavily fallback, MongoDB persistence, caching | Test report P4 |
| **Viết báo cáo P4** | Mô tả tool search, memory layer, caching, module routing | Chương báo cáo P4 |

### ✅ Kết quả Phase 4

| Deliverable | Mô tả |
|-------------|-------|
| **Tavily Search** | Web search fallback khi RAG thiếu |
| **Chat History** | MongoDB lưu đầy đủ lịch sử |
| **Caching** | Cache queries lặp lại, cải thiện latency |
| **Student Profile Persistence** | Profile SV được lưu trữ, phục vụ ngữ cảnh |

---

## Phase 5: FastAPI + Pipeline Integration + Mobile UI (Tuần 12–13) — 90%

> **Mục tiêu**: Kết nối pipeline, expose API, thiết kế mobile UI/UX.

### 📅 Tuần 12 — Pipeline + FastAPI (75% → 83%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| `RAGPipeline` | Kết nối toàn bộ: Router → Reflection → Embed → Search → Rerank → Chat → Self-Eval | `pipeline/rag_pipeline.py` |
| Pipeline flows | `chitchat_flow()`, `rag_flow()`, `ctdt_flow()` | `pipeline/flows.py` |
| FastAPI app | CORS, middleware, error handling, singleton models | `api/main.py` |
| API Routes | `POST /chat` (SSE streaming), `GET /health`, `POST /student/profile` | `api/routes/*.py` |
| Pydantic schemas | `ChatRequest`, `ChatResponse`, `StudentProfile`, `HealthResponse` | `api/schemas.py` |
| Config centralized | Pydantic BaseSettings + `.env`, tất cả service configs | `config/settings.py` |

### 📅 Tuần 13 — Mobile UI/UX + Integration Test (83% → 90%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| **Mobile UI Design** | Thiết kế giao diện chat mobile-first: đẹp, trực quan, responsive | UI mockup + design system |
| **Frontend Implementation** | React Native / Flutter: chat screen, history, student info, module navigation | Mobile frontend code |
| **Student Onboarding UI** | Flow nhập thông tin SV (khóa, ngành) khi lần đầu sử dụng | Onboarding screen |
| API integration | Kết nối frontend ↔ backend, SSE streaming hiển thị | Integrated app |
| **Viết báo cáo P5** | Mô tả kiến trúc tổng thể, pipeline, API, UI/UX design | Chương báo cáo P5 |

### ✅ Kết quả Phase 5

| Deliverable | Mô tả |
|-------------|-------|
| **Full Pipeline** | End-to-end: User → Router → (Chitchat/RAG/CTĐT) → Response |
| **API Server** | FastAPI streaming, health check, student profile |
| **Mobile App** | Giao diện chat mobile đẹp, trực quan, có module navigation |
| **Config** | Centralized settings, dễ deploy |

---

## Phase 6: Evaluation + Optimization + Báo cáo (Tuần 14–15) — 100%

> **Mục tiêu**: Đánh giá toàn diện, tối ưu, hoàn thiện báo cáo.

### 📅 Tuần 14 — Evaluation + Optimization (90% → 95%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| Evaluation dataset | 100+ Q&A pairs domain đại học, đa dạng loại câu hỏi | `evaluation/dataset.json` |
| Retrieval metrics | Hit Rate, MRR, NDCG trên dataset | Retrieval report |
| Response metrics | Faithfulness, Relevance, Completeness (dùng LLM-as-judge) | Response report |
| So sánh configs | Ensemble vs single model, có/không reranking, có/không student context | Comparison table |
| **Validity test** | Test xử lý phạm vi hiệu lực: quy định cũ/mới, khóa khác nhau | Validity test report |
| Optimization | Tune weights, top-K, batch size, caching tuning, latency profiling | Optimized config |

### 📅 Tuần 15 — Hoàn thiện báo cáo + Demo (95% → 100%)

| Công việc | Chi tiết | Output |
|-----------|----------|--------|
| **Tổng hợp báo cáo** | Hoàn thiện toàn bộ các chương: mở đầu, lý thuyết, đề xuất, thực nghiệm, kết luận | Báo cáo hoàn chỉnh |
| Phương pháp & mô hình | Mô tả chi tiết: input/output mỗi layer, data flow, training process | Chương phương pháp |
| Kết quả thực nghiệm | Trình bày metrics, biểu đồ, so sánh, phân tích | Chương thực nghiệm |
| Demo recording | Quay video demo hệ thống hoạt động end-to-end | Demo video |
| Presentation | Chuẩn bị slide bảo vệ | PowerPoint/PDF |
| Code cleanup | Refactor, docstrings, README cập nhật | Clean codebase |

### ✅ Kết quả Phase 6

| Deliverable | Mô tả |
|-------------|-------|
| **Evaluation Report** | Metrics đầy đủ retrieval + response + validity |
| **Optimized System** | Hệ thống đã tune cho domain đại học |
| **Báo cáo hoàn chỉnh** | Đầy đủ phương pháp, mô hình, input/output, kết quả |
| **Demo** | Video + presentation sẵn sàng bảo vệ |

---

## Tổng kết % Tiến Độ Theo Tuần

| Tuần | Phase | Nội dung chính | % Tích lũy |
|------|-------|---------------|-------------|
| 1 | P1 | Thu thập & cấu trúc hóa dữ liệu | 7% |
| 2 | P1 | Embedding Layer (BGE-M3 + E5) | 13% |
| 3 | P1 | Qdrant + Elasticsearch setup | 19% |
| 4 | P1 | Hybrid Search + test P1 + báo cáo | 25% |
| 5 | P2 | Reranking + Query Router + validity checker | 33% |
| 6 | P2 | Query Reflection + validity resolver + test P2 | 40% |
| 7 | P3 | Chat Model + student context prompts | 47% |
| 8 | P3 | Self Evaluation + Student Profile + cohort-aware retrieval | 53% |
| 9 | P3 | Module Router + CTĐT Module + test P3 | 60% |
| 10 | P4 | Tavily + MongoDB Memory | 68% |
| 11 | P4 | Caching + Additional Modules + test P4 | 75% |
| 12 | P5 | Pipeline orchestration + FastAPI backend | 83% |
| 13 | P5 | Mobile UI/UX + integration test | 90% |
| 14 | P6 | Evaluation + Optimization | 95% |
| 15 | P6 | Hoàn thiện báo cáo + Demo + Presentation | 100% |

---

## Các tính năng đặc biệt (ngoài hỏi đáp cơ bản)

### 1. Xử lý phạm vi hiệu lực quy định
- Mỗi văn bản/quy định được gắn metadata: `effective_date`, `expiry_date`, `superseded_by`
- Khi trả lời → kiểm tra quy định nào đang có hiệu lực tại thời điểm hiện tại
- Khi có văn bản mới thay thế → tự động ưu tiên văn bản mới

### 2. Phân biệt theo khóa/ngành (Cohort-aware)
- Quy định/CTĐT có thể khác nhau giữa các khóa (K66 ≠ K67)
- Hệ thống lưu thông tin SV → tự động lọc kết quả phù hợp với khóa/ngành
- Cùng 1 câu hỏi, SV K66 và K67 có thể nhận câu trả lời khác nhau

### 3. Module chuyên biệt
- **CTĐT Module**: Tư vấn chương trình đào tạo, môn học, tín chỉ, tiên quyết
- **Quy chế Module**: Quy chế đào tạo, thi cử, điểm số
- **Học phí Module**: Thông tin học phí, miễn giảm, deadline
- **Lịch thi Module**: Lịch thi, phòng thi, ca thi

### 4. Đa phương án trả lời
- Khi có nhiều phương án → ranking theo phạm vi hiệu lực + relevance score
- Chọn phương án đúng nhất, có hiệu lực gần nhất

---

## Phương pháp & Mô hình

### Input/Output tổng thể

```
INPUT:
├── User query (câu hỏi)
├── Student profile (khóa, ngành, CTĐT) — optional
├── Chat history (lịch sử hội thoại)
└── Current timestamp (thời điểm hỏi)

OUTPUT:
├── Answer (câu trả lời)
├── Sources (nguồn trích dẫn)
├── Confidence score
├── Validity info (phạm vi hiệu lực)
└── Related questions (câu hỏi liên quan)
```

### Data Flow

```
User Query
  ↓
[Query Router] → Chitchat? → [Chat Model] → Response
  ↓ (RAG)
[Query Reflection] — rewrite + add student context + chat history
  ↓
[Ensemble Embedding] — BGE-M3 + E5-large
  ↓
[Hybrid Search] — Qdrant (vector) + Elasticsearch (keyword) → RRF fusion
  ↓
[Validity Filter] — lọc theo phạm vi hiệu lực + khóa/ngành
  ↓
[BGE Reranker] — rerank → Top 5
  ↓
[Chat Model] — generate answer với context + student info
  ↓
[Self Evaluator] — check quality/hallucination
  ├── PASS → Final Answer → Save MongoDB
  └── FAIL → [Tavily Search] → regenerate → Final Answer → Save MongoDB
```

---

## Lưu trữ DB (MongoDB)

| Collection | Dữ liệu | Mục đích |
|------------|----------|----------|
| `chat_history` | Messages (role, content, timestamp) | Lịch sử hội thoại |
| `conversations` | Session metadata, status, last_active | Quản lý phiên |
| `student_profiles` | Khóa, ngành, CTĐT, preferences | Ngữ cảnh sinh viên |
| `query_cache` | Query hash → response, TTL | Cache kết quả |
| `evaluation_logs` | Query, response, scores, feedback | Đánh giá chất lượng |
