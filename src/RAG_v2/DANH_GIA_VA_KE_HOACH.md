# Đánh giá hệ thống RAG v2 & Kế hoạch cải thiện

## 1. Đánh giá hệ thống hiện tại

### 1.1 Những điểm ĐÃ TRIỂN KHAI tốt

| Module | Trạng thái | Chi tiết |
|--------|-----------|----------|
| **Clean Architecture** | ✅ Hoàn chỉnh | ABC/Protocol cho LLM, Embedding, Retrieval, Reranking; factory pattern; config-driven provider selection qua `.env` |
| **Hybrid Search** | ✅ Hoàn chỉnh | Qdrant (vector) + Elasticsearch (BM25) kết hợp qua RRF fusion; multi-collection search song song |
| **Dual Embedding** | ✅ Hoàn chỉnh | BGE-M3 + E5-Multilingual song song, named vectors trên Qdrant |
| **Reranking** | ✅ Hoàn chỉnh | BGE-Reranker-v2-m3 với BaseReranker ABC |
| **Query Router** | ✅ Hoàn chỉnh | 2 mode: classifier (zero-cost, LogisticRegression + embedding) và LLM; 6 labels (chitchat, tool_search, ctdt, quydinh, kehoach, stsv) |
| **Query Reflection** | ✅ Hoàn chỉnh | LLM-based query rewrite: giải tham chiếu đại từ, mở rộng viết tắt, tích hợp history |
| **Self Evaluation** | ✅ Hoàn chỉnh | LLM judge đánh giá Relevance, Faithfulness, Completeness → pass/fail |
| **Tavily Fallback** | ✅ Hoàn chỉnh | Web search fallback khi self-eval fail |
| **Streaming** | ✅ Hoàn chỉnh | SSE streaming API (`/chat/stream`) |
| **MongoDB Logging** | ✅ Hoàn chỉnh | Session management, turn logging, query logs |
| **Conversation History** | ✅ Cơ bản | `ChatHistoryStore` + `ConversationState` trên MongoDB; `_trim_history(limit=6)` cho LLM context; auto-load từ session_id |
| **Chunking** | ✅ Hoàn chỉnh | Hierarchical legal chunker (parent-child cho văn bản pháp lý); STSV, Kehoach, CTDT chunkers riêng biệt |
| **Metadata Enrichment** | ✅ Bộ phận | `enrich_metadata.py` trích xuất `effective_date`, `applicable_cohort`, `document_type`, `applicable_major` cho CTDT |
| **Evaluation Pipeline** | ✅ Hoàn chỉnh | evaluate_retrieval (BGE/E5/ES/Hybrid so sánh), evaluate_llm_quality, evaluate_phase3; dataset builder UI (Streamlit) |
| **API + Frontend** | ✅ Hoàn chỉnh | FastAPI backend + React (Vite + Tailwind) frontend |
| **LLM Provider** | ✅ Cơ bản | Gemini implemented; OpenAI/Azure/Ollama declared trong settings nhưng chưa implement |

### 1.2 Những THIẾU SÓT chính

| # | Thiếu sót | Mức độ | Chi tiết |
|---|-----------|--------|----------|
| 1 | **Không có Caching** | 🔴 Cao | Không có cache nào: embedding, retrieval, hay LLM response. Mỗi query đều embed lại + search lại. Đã planning nhưng chưa implement (`implementation_plan_bug` line 148-152) |
| 2 | **Không xử lý phạm vi hiệu lực** | 🔴 Cao | Metadata `effective_date`, `applicable_cohort` ĐÃ trích xuất khi chunking CTDT, NHƯNG **không được sử dụng** trong retrieval pipeline — không filter, không so sánh, không ưu tiên document mới hơn |
| 3 | **Không có Student Context** | 🔴 Cao | Không có cơ chế nhận thông tin sinh viên (khóa, ngành, chương trình). Cùng câu hỏi "yêu cầu ngoại ngữ" nhưng K66 và K68 có quy định khác nhau → hệ thống không phân biệt được |
| 4 | **Không xử lý cross-reference** | 🔴 Cao | Các điều, khoản tham chiếu lẫn nhau (VD: "theo Điều 48 Khoản 2") nhưng chunking tách riêng → mất ngữ cảnh; không có cơ chế kéo thêm chunk được tham chiếu |
| 5 | **Không xử lý conflict/override** | 🔴 Cao | Khi có nhiều quy định cùng chủ đề (quy chế 2023 vs 2025), hệ thống không biết quy định nào thay thế quy định nào |
| 6 | **History chỉ là text** | 🟡 Trung bình | History chỉ truyền raw text cho LLM; không tóm tắt, không extract entities từ history trước đó |
| 7 | **Không có User Profile** | 🟡 Trung bình | API `ChatRequest` không có field cho student info; không lưu profile user |
| 8 | **Chỉ có Gemini LLM** | 🟡 Thấp | Settings khai báo openai/azure/ollama nhưng chưa implement concrete class |
| 9 | **Không có structured data** | 🟡 Trung bình | Dữ liệu quy định chỉ ở dạng text chunks; không có knowledge graph hay database cho quan hệ giữa các quy định |

---

## 2. Vấn đề hiệu lực & tham chiếu giữa các Điều/Khoản

### 2.1 Hiện trạng

**Đã có (ở tầng chunking):**
- `enrich_metadata.py` trích xuất `effective_date` (regex từ filename + nội dung)
- `applicable_cohort` trích xuất (K65, K66, ... K70)
- `document_type` phân loại
- `ArticleLevelLegalChunker` chunk theo Điều, giữ context Chương

**CHƯA CÓ (ở tầng retrieval + generation):**
- ❌ Metadata filtering khi search (không filter theo `applicable_cohort` hay `effective_date`)
- ❌ Xử lý thay thế/override giữa các văn bản (VD: QĐ 5445/2025 thay thế QĐ 4600/2023)
- ❌ Cross-reference resolution ("theo Khoản 2 Điều 15" → fetch chunk Điều 15)
- ❌ Temporal reasoning (quy định nào đang có hiệu lực tại thời điểm hỏi)
- ❌ Phân biệt phạm vi áp dụng theo khóa/ngành trong cùng một quy định

### 2.2 Cách xử lý cần thiết

#### A. Metadata-aware Retrieval
```
Khi user hỏi → extract context (khóa, ngành, thời điểm)
→ build Qdrant filter: {applicable_cohort: "K68", effective_date <= now}
→ hybrid search WITH filters
→ rerank với boost cho document mới nhất
```

#### B. Cross-reference Resolution
```
Sau khi retrieve → scan answer cho pattern "Điều X", "Khoản Y Điều Z"
→ fetch thêm chunks tương ứng → add vào context
→ generate lại nếu cần
```

#### C. Document Lineage / Override Graph
```
Xây dựng mapping: {doc_id → replaces → [doc_ids]}
VD: QCDT_2025 replaces QCDT_2023
Khi retrieve → filter out superseded documents
```

---

## 3. Đánh giá yêu cầu cụ thể

### 3.1 Core Features

| Yêu cầu | Trạng thái | Chi tiết |
|----------|-----------|----------|
| **History** | ⚠️ Cơ bản | Có MongoDB storage + auto-load + LLM context window 6 turns. THIẾU: summary/compression cho session dài; entity extraction từ history |
| **Cache** | ❌ Chưa có | Không có caching layer nào. Cần: embedding cache, retrieval cache, response cache |

### 3.2 Tính năng nâng cao

| Yêu cầu | Trạng thái | Chi tiết |
|----------|-----------|----------|
| **Phạm vi hiệu lực** | ❌ Chưa xử lý | Metadata extracted nhưng không used; cần temporal filtering + override detection |
| **Multi-answer → chọn đúng nhất** | ❌ Chưa có | Khi retrieve nhiều quy định cùng chủ đề → cần logic chọn quy định có hiệu lực đúng nhất cho student context |
| **Quy định độc lập theo khóa** | ❌ Chưa xử lý | VD: TA K66 ≠ TA K67. Metadata `applicable_cohort` có nhưng không filter. Cần student profile + metadata filter |
| **Student context** | ❌ Chưa có | Không có user profile (khóa, ngành, chương trình). Cần: API field + storage + filter integration |
| **Xử lý & cấu trúc hóa dữ liệu** | ⚠️ Bộ phận | Chunking tốt, metadata enrichment cho CTDT. THIẾU: knowledge graph, structured relations giữa quy định |
| **Training** | ⚠️ Bộ phận | Domain classifier đã train. THIẾU: fine-tuning embedding, RLHF, evaluation-driven improvement loop |
| **Viết báo cáo** | ⚠️ Có sẵn | Thư mục `Baocao/` có .tex files. Cần cập nhật theo tiến độ |

---

## 4. Kế hoạch cải thiện

### Phase 1: Metadata-Aware Retrieval + Student Context (ưu tiên cao nhất)

**Mục tiêu:** Trả lời chính xác theo khóa/ngành/thời điểm của sinh viên

#### Task 1.1: Student Profile API
- **Input/Output:** API nhận `student_info: {cohort: "K68", major: "CNTT", program: "standard"}` trong `ChatRequest`
- **Files:** `api/schemas.py`, `api/routes/chat.py`
- **Effort:** 1 ngày

#### Task 1.2: Metadata Filter Builder
- **Input:** Student profile + query context
- **Output:** Qdrant filter + ES filter objects
- **Logic:**
  - Extract cohort/date hints từ query (regex + LLM)
  - Combine với student profile
  - Build `qdrant_models.Filter` cho `applicable_cohort`, `effective_date`
- **Files:** Tạo `query/context_extractor.py` (mới), `retrieval/filter_builder.py` (mới)
- **Effort:** 2-3 ngày

#### Task 1.3: Tích hợp Filter vào Pipeline
- **Thay đổi:** `HybridSearch.search()` đã hỗ trợ `qdrant_filters` và `es_filters` — chỉ cần truyền từ pipeline
- **Files:** `pipeline/flows.py`, `pipeline/rag_pipeline.py`
- **Effort:** 1 ngày

#### Task 1.4: Temporal Ranking Boost
- **Logic:** Sau reranking, boost score cho documents có `effective_date` gần nhất
- **Files:** `pipeline/flows.py` (post-rerank step)
- **Effort:** 1 ngày

### Phase 2: Document Validity & Override Resolution

**Mục tiêu:** Tự động xác định quy định nào đang có hiệu lực, quy định nào đã bị thay thế

#### Task 2.1: Document Lineage Registry
- **Xây dựng:** JSON/MongoDB collection mapping quan hệ thay thế giữa các văn bản
  ```json
  {
    "QCDT_2025_5445": {
      "replaces": ["QCDT_2023_4600"],
      "effective_from": "2025-08-01",
      "scope": "all_cohorts"
    }
  }
  ```
- **Files:** Tạo `config/document_registry.py` (mới), `data/document_lineage.json` (mới)
- **Effort:** 2 ngày (xây dựng data + code)

#### Task 2.2: Validity Filter
- **Logic:** Trước khi đưa vào context, loại bỏ chunks từ documents đã bị thay thế (trừ khi query hỏi về lịch sử)
- **Files:** Tạo `pipeline/validity_filter.py` (mới)
- **Effort:** 1-2 ngày

#### Task 2.3: Multi-answer Conflict Resolution
- **Logic:** Khi retrieve được nhiều quy định cùng topic nhưng khác phạm vi:
  1. Group by topic
  2. Chọn quy định có hiệu lực đúng nhất cho student context
  3. Nếu ambiguous → trả lời cả hai kèm giải thích
- **Approach:** LLM-based post-processing step, hoặc rule-based nếu metadata đủ
- **Files:** Tạo `pipeline/conflict_resolver.py` (mới)
- **Effort:** 3 ngày

### Phase 3: Cross-Reference Resolution

**Mục tiêu:** Khi chunk A tham chiếu "Điều X Khoản Y", tự động kéo thêm chunk tương ứng

#### Task 3.1: Reference Extractor
- **Input:** Retrieved chunks text
- **Output:** List of `(article_num, clause_num, doc_source)` references
- **Regex patterns:** `Điều\s+\d+`, `Khoản\s+\d+\s+Điều\s+\d+`, `theo quy định tại...`
- **Files:** Tạo `query/reference_extractor.py` (mới)
- **Effort:** 1 ngày

#### Task 3.2: Reference Fetcher
- **Logic:** Dùng metadata search trong Qdrant: filter `article_num == X AND source == same_doc`
- **Files:** Tạo `retrieval/reference_fetcher.py` (mới)
- **Effort:** 1-2 ngày

#### Task 3.3: Tích hợp vào RAG Flow
- **Thay đổi flow:** Retrieve → Rerank → Extract references → Fetch referenced chunks → Merge context → Generate
- **Files:** `pipeline/flows.py`
- **Effort:** 1 ngày

### Phase 4: Caching Layer

**Mục tiêu:** Giảm latency cho repeated/similar queries

#### Task 4.1: Embedding Cache
- **Strategy:** LRU in-memory cache (functools.lru_cache hoặc cachetools)
- **Key:** Hash of query text
- **Files:** Tạo `embedding/cache.py` (mới), update `embedding/bge_m3.py`, `embedding/e5_multilingual.py`
- **Effort:** 1 ngày

#### Task 4.2: Retrieval Cache
- **Strategy:** TTL-based cache (5 phút) cho search results
- **Key:** Hash of (query_vector, filters, top_k)
- **Files:** Tạo `retrieval/cache.py` (mới)
- **Effort:** 1 ngày

#### Task 4.3: Semantic Cache cho LLM Response
- **Strategy:** Nếu query mới có cosine similarity > 0.95 với query đã cache → trả kết quả cache
- **Files:** Tạo `llm/semantic_cache.py` (mới)
- **Effort:** 2 ngày

### Phase 5: Enhanced History & Session Management

#### Task 5.1: History Summarization
- **Logic:** Khi history > 10 turns → LLM tóm tắt thành summary; giữ summary + 4 turns gần nhất
- **Files:** Tạo `memory/history_summarizer.py` (mới)
- **Effort:** 1 ngày

#### Task 5.2: User Profile Persistence
- **Logic:** Lưu student info vào MongoDB, auto-load theo user_id/session
- **Files:** Update `memory/conversation.py`, `pipeline/mongo_logger.py`
- **Effort:** 1 ngày

### Phase 6: Báo cáo & Evaluation

#### Task 6.1: Evaluation Dataset cho Validity/Cohort Scenarios
- **Xây dựng:** Test cases: cùng câu hỏi, khác khóa → expect khác answer
- **Files:** `evaluation/data/validity_test_cases.json` (mới)
- **Effort:** 2 ngày

#### Task 6.2: Cập nhật Báo cáo
- **Files:** `Baocao/3_De_xuat.tex`, `Baocao/5_Thuc_nghiem.tex`, `Baocao/6_Ket_luan.tex`
- **Effort:** 2-3 ngày

---

## Tổng quan Timeline

```
Phase 1 (Metadata + Student Context)     ██████████  ~5-6 ngày
Phase 2 (Validity + Override)             ████████████  ~6-7 ngày
Phase 3 (Cross-Reference)                 ██████  ~3-4 ngày
Phase 4 (Caching)                         ██████  ~4 ngày
Phase 5 (Enhanced History)                ████  ~2 ngày
Phase 6 (Evaluation + Báo cáo)            ██████  ~4-5 ngày
                                          ─────────────────────
                                          Tổng: ~24-28 ngày
```

## Kiến trúc mục tiêu (sau cải thiện)

```
User Query + Student Profile
        │
        ▼
┌─ Query Router (classifier/LLM) ─┐
│                                   │
│  ┌─ Context Extractor ──────┐    │ ← NEW: extract cohort/date from query
│  │  cohort, date, topic     │    │
│  └──────────────────────────┘    │
│                                   │
│  ┌─ Query Reflector ────────┐    │
│  │  rewrite + enrich        │    │
│  └──────────────────────────┘    │
│                                   │
├─── chitchat ──► Chat Model        │
│                                   │
├─── rag ──────────────────────────┤
│    │                              │
│    ▼                              │
│  ┌─ Filter Builder ─────────┐    │ ← NEW: build Qdrant/ES filters
│  │  cohort + date + scope   │    │
│  └──────────────────────────┘    │
│    │                              │
│    ▼                              │
│  ┌─ Hybrid Search (filtered) ┐   │ ← CHANGED: pass metadata filters
│  │  Qdrant + ES + RRF        │   │
│  └────────────────────────────┘  │
│    │                              │
│    ▼                              │
│  ┌─ Validity Filter ────────┐    │ ← NEW: remove superseded docs
│  └──────────────────────────┘    │
│    │                              │
│    ▼                              │
│  ┌─ Reranker ───────────────┐    │
│  │  + temporal boost         │   │ ← CHANGED: boost recent docs
│  └──────────────────────────┘    │
│    │                              │
│    ▼                              │
│  ┌─ Reference Resolver ─────┐    │ ← NEW: fetch cross-referenced chunks
│  └──────────────────────────┘    │
│    │                              │
│    ▼                              │
│  ┌─ Conflict Resolver ──────┐    │ ← NEW: pick best among competing regs
│  └──────────────────────────┘    │
│    │                              │
│    ▼                              │
│  ┌─ LLM Generate ──────────┐    │
│  │  + Self Eval              │   │
│  │  + Tavily Fallback        │   │
│  └──────────────────────────┘    │
│                                   │
└───────────────────────────────────┘
        │
        ▼
   Response + Sources + Session Log
```
