# Tổng Quan Hệ Thống RAG v2

> Tài liệu này mô tả kiến trúc đầy đủ, luồng xử lý, và nhiệm vụ của từng file trong hệ thống RAG v2 — Chatbot hỗ trợ sinh viên Đại học Bách khoa Hà Nội.

---

## Mục Lục

1. [Tổng Quan Kiến Trúc](#1-tổng-quan-kiến-trúc)
2. [Luồng Xử Lý Request](#2-luồng-xử-lý-request)
3. [Chi Tiết Từng Layer](#3-chi-tiết-từng-layer)
   - [3.1 Config Layer](#31-config-layer)
   - [3.2 API Layer](#32-api-layer)
   - [3.3 Pipeline Layer](#33-pipeline-layer)
   - [3.4 Query Layer](#34-query-layer)
   - [3.5 Embedding Layer](#35-embedding-layer)
   - [3.6 Retrieval Layer](#36-retrieval-layer)
   - [3.7 Reranking Layer](#37-reranking-layer)
   - [3.8 LLM Layer](#38-llm-layer)
   - [3.9 Tools Layer](#39-tools-layer)
   - [3.10 Chunking Layer](#310-chunking-layer)
4. [MongoDB: Session, Turn, Query Log](#4-mongodb-session-turn-query-log)
5. [Reflect Query — Giải Thích Chi Tiết](#5-reflect-query--giải-thích-chi-tiết)
6. [Routing 3 Tầng](#6-routing-3-tầng)
7. [Sơ Đồ Dữ Liệu Đầy Đủ](#7-sơ-đồ-dữ-liệu-đầy-đủ)
8. [Danh Sách File & Nhiệm Vụ](#8-danh-sách-file--nhiệm-vụ)
9. [Cấu Hình .env Quan Trọng](#9-cấu-hình-env-quan-trọng)

---

## 1. Tổng Quan Kiến Trúc

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Frontend)                               │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ HTTP POST /chat hoặc /chat/stream
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  API LAYER  (FastAPI)                                                        │
│  api/main.py · api/routes/chat.py · api/routes/session.py                   │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ gọi pipeline.query()
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  PIPELINE LAYER  (Điều phối trung tâm)                                      │
│  pipeline/rag_pipeline.py · pipeline/flows.py · pipeline/mongo_logger.py    │
│                                                                              │
│   ┌──────────────┐    ┌───────────────┐    ┌──────────────┐                 │
│   │ RAGPipeline  │───▶│  QueryRouter  │───▶│    Intent?   │                 │
│   │  .query()    │    └───────────────┘    └──────┬───────┘                 │
│   └──────────────┘                                │                         │
│         │                              chitchat / rag / tool_search         │
│         │                                         │                         │
│         ├── chitchat ──────────────── chitchat_flow()                       │
│         └── rag ─────────────────────── rag_flow()                          │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
          ┌────────────────────┼─────────────────────┐
          ▼                    ▼                      ▼
┌─────────────────┐  ┌────────────────────┐  ┌───────────────────┐
│  QUERY LAYER    │  │  RETRIEVAL LAYER   │  │    LLM LAYER      │
│  router.py      │  │  hybrid_search.py  │  │  gemini.py        │
│  reflection.py  │  │  multi_collection  │  │  self_eval.py     │
│  classifier.py  │  │  qdrant_store.py   │  │  prompts.py       │
└─────────────────┘  │  elasticsearch.py  │  └───────────────────┘
                     └────────────────────┘
                               │
                     ┌─────────▼──────────┐
                     │  RERANKING LAYER   │
                     │  bge_reranker.py   │
                     └────────────────────┘
```

Hệ thống được xây dựng theo **Clean Architecture**:
- **Provider-agnostic**: LLM, Embedder, Reranker đều có `Base` class — swap provider qua `.env`, không sửa code.
- **Factory pattern**: `create_llm()`, `create_embedder()`, `create_reranker()`, `create_retriever()` — mọi khởi tạo tập trung qua factory.
- **Centralized config**: Mọi cấu hình đọc từ `config/settings.py` (Pydantic BaseSettings).

---

## 2. Luồng Xử Lý Request

### 2.1 Non-streaming (`POST /chat`)

```
User gửi câu hỏi
       │
       ▼
[API] chat.py nhận request
  - Tự tạo session_id nếu chưa có
  - Chuyển body.history → List[dict]
       │
       ▼
[Pipeline] RAGPipeline.query(question, history, session_id)
  │
  ├─ Load lịch sử từ MongoDB nếu có session_id nhưng history rỗng
  │
  ├─ [ROUTING - Tier 1] QueryRouter.route(question, chat_history)
  │     DomainClassifier dự đoán intent + domain (embedding-based, ~10-50ms)
  │     Trả về: {intent, domain, domains, confidence}
  │
  ├─ [ROUTING - Tier 3] Nếu intent=rag và confidence < 0.55
  │     Gọi LLM domain classify để xác nhận lại domain
  │
  ├── intent = "chitchat"?
  │     └─ chitchat_flow(question, history, chat_model)
  │           → LLM sinh câu trả lời trực tiếp (không retrieval)
  │
  └── intent = "rag"
        └─ rag_flow(question, history, reflector, embedders, searcher, ...)
              │
              ├─ [REFLECT] QueryReflector.reflect(question, history)
              │     LLM viết lại query rõ ràng hơn cho retrieval
              │
              ├─ [ROUTE COLLECTION] CollectionSelector.select(domain, confidence)
              │     domain → danh sách collections cần search
              │
              ├─ [EMBED] BGEm3Embedder + E5MultilingualEmbedder
              │     Tạo 2 vector cho search_query
              │
              ├─ [SEARCH] MultiCollectionSearch.search(...)
              │     Mỗi collection: HybridSearch (Qdrant vector + ES BM25) → RRF fusion
              │     Tất cả collections: global merge (RRF round 2)
              │
              ├─ [RERANK] BGEReranker.rerank(query, documents)
              │     Cross-encoder rescoring → top-K docs
              │
              ├─ [GENERATE] chat_model.generate(query, context, history)
              │     LLM sinh câu trả lời từ context
              │
              └─ [SELF-EVAL] SelfEvaluator.evaluate(query, context, response)
                    pass? → return answer
                    fail? → Tavily web search fallback → generate lại
       │
       ▼
[MongoDB] mongo_logger.log_turn(session_id, question, result)
  - Ghi turn vào collection `turns`
  - Ghi analytics vào `query_logs`
  - Tăng turn_count trong `sessions`
       │
       ▼
[API] Trả về ChatResponse (answer, sources, intent, session_id)
```

### 2.2 Streaming (`POST /chat/stream`)

Giống non-streaming nhưng:
- Chạy `rag_flow_stream()` — retrieval chạy trước, generation yield từng token
- Response dạng SSE: `data: <token>\n\n` và kết thúc bằng `data: [DONE]\n\n`
- Log MongoDB sau khi stream hoàn tất (qua background task)

---

## 3. Chi Tiết Từng Layer

### 3.1 Config Layer

**File duy nhất:** `config/settings.py`

Là **single source of truth** cho toàn bộ cấu hình. Sử dụng Pydantic `BaseSettings` — tự đọc biến môi trường / `.env`.

| Nhóm | Biến quan trọng | Mặc định |
|------|----------------|----------|
| Provider | `LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `RERANKER_PROVIDER` | `gemini`, `ensemble`, `bge` |
| API Keys | `GOOGLE_API_KEY`, `TAVILY_API_KEY` | — |
| Qdrant | `QDRANT_HOST`, `QDRANT_PORT` | `localhost:6333` |
| Elasticsearch | `ELASTICSEARCH_HOST`, `ELASTICSEARCH_PORT` | `localhost:9200` |
| MongoDB | `MONGODB_URI`, `MONGODB_DATABASE` | `localhost:27017`, `rag_chatbot` |
| Collections | `COLLECTIONS` | `["stsv","quydinh","kehoach","ctdt"]` |
| Retrieval | `TOP_K`, `VECTOR_TOP_K`, `KEYWORD_TOP_K` | `5`, `20`, `20` |
| Chat model | `CHAT_MODEL`, `CHAT_TEMPERATURE` | `gemini-2.5-flash`, `0.3` |
| Features | `REFLECTION_ENABLED`, `SELF_EVAL_ENABLED`, `TAVILY_FALLBACK_ENABLED` | `True`, `True`, `True` |

> Thay provider chỉ cần sửa `.env`, không cần đụng vào code.

---

### 3.2 API Layer

**Thư mục:** `api/`

```
api/
├── main.py          ← FastAPI app, lifespan (khởi tạo pipeline + mongo), CORS
├── schemas.py       ← Pydantic models: ChatRequest, ChatResponse, RetrievedDocument
└── routes/
    ├── chat.py      ← POST /chat, POST /chat/stream
    ├── session.py   ← POST /session, GET /session/{id}, GET /sessions?user_id=
    └── health.py    ← GET /health
```

**Nhiệm vụ:**
- `main.py`: Khởi tạo `RAGPipeline` và `MongoLogger` khi server start (FastAPI `lifespan`). Gán vào `app.state` để các route dùng chung.
- `schemas.py`: Định nghĩa contract input/output — `ChatRequest` có `question`, `history`, `session_id`, `top_k`.
- `chat.py`: Endpoint chính. Tự tạo session nếu không có. Gọi `pipeline.query()` qua thread executor (async-safe).
- `session.py`: CRUD session — tạo session mới, lấy session + turns, liệt kê sessions theo user.
- `health.py`: Health check endpoint cho Docker/kubernetes readiness probe.

---

### 3.3 Pipeline Layer

**Thư mục:** `pipeline/`

```
pipeline/
├── rag_pipeline.py  ← RAGPipeline class — khởi tạo & điều phối toàn bộ
├── flows.py         ← chitchat_flow, rag_flow, *_stream variants
└── mongo_logger.py  ← MongoLogger (session/turn/log persistence)
```

#### `rag_pipeline.py` — Trái tim của hệ thống

`RAGPipeline.__init__()` khởi tạo **tất cả** components:
1. `QueryRouter` (local classifier, không tốn API)
2. `QueryReflector` (Gemini LLM)
3. `BGEm3Embedder` + `E5MultilingualEmbedder`
4. `MultiCollectionSearch` (Qdrant + ES cho từng collection)
5. `BGEReranker`
6. `GeminiLLM` (chat model)
7. `SelfEvaluator`
8. `TavilySearchTool` (nếu có API key)

`RAGPipeline.query()` điều phối luồng 3-tầng routing + RAG flow. `RAGPipeline.query_stream()` là bản streaming.

#### `flows.py` — Logic chi tiết của từng flow

- `chitchat_flow()`: Format history → gọi LLM với mode="chitchat" → return answer.
- `rag_flow()`: Reflect → Select collections → Embed → Search → Rerank → Generate → SelfEval → (Tavily fallback).
- `rag_flow_stream()`: Giống `rag_flow` nhưng generation là generator — yield từng token.

> `flows.py` **không biết** về session/MongoDB — nó chỉ xử lý pure retrieval + generation logic. MongoDB logging được thực hiện ở `rag_pipeline.py` sau khi flow trả về.

#### `mongo_logger.py` — Persistence và Analytics

Xem mục [4. MongoDB](#4-mongodb-session-turn-query-log) để hiểu chi tiết.

---

### 3.4 Query Layer

**Thư mục:** `query/`

```
query/
├── router.py           ← QueryRouter (classifier mode / llm mode)
├── domain_classifier.py← DomainClassifier (2-stage: intent + domain)
├── reflection.py       ← QueryReflector (rewrite query)
├── prompts.py          ← Prompt templates cho router, reflector, LLM fallback
└── training_data.py    ← RAG_LABELS, training samples cho classifier
```

#### `router.py` — Cổng vào của query

**QueryRouter** nhận `(query, chat_history)` → trả về `{intent, domain, domains, confidence}`.

Hỗ trợ 2 mode:
- `"classifier"` (mặc định): dùng `DomainClassifier` — embedding-based, 10-50ms, **zero API cost**.
- `"llm"`: dùng OpenAI GPT-4o-mini với few-shot prompting.

Hàm `build_routing_input()` tự động prepend 2 turns gần nhất vào query trước khi classify — giúp routing chính xác với câu hỏi follow-up ngắn như *"Còn điều kiện tiên quyết là gì?"*.

#### `domain_classifier.py` — Classifier 2 tầng (không tốn API)

**Kiến trúc v3** (hai stage riêng biệt):

```
Stage 1 (Intent):
  Đầu vào: BGE-M3 embedding của query
  Model: CalibratedClassifierCV(LogisticRegression, cv=5)
  Đầu ra: {chitchat, rag, tool_search} + probability

Stage 2 (Domain, chỉ chạy khi Stage 1 → "rag"):
  Đầu vào: Cùng embedding từ Stage 1
  Model: OneVsRestClassifier(LogisticRegression) — multi-label
  Đầu ra: Subset của {ctdt, quydinh, kehoach, stsv}
```

**Tại sao 2 stage thay vì 1?**  
Stage-1 trước đây gộp intent + domain vào một OvR model duy nhất. `tool_search` có base-rate ~12%, xác suất calibrated hiếm khi vượt 0.6 threshold → F1 = 0%. Tách riêng intent classifier cho mỗi sub-classifier một task tập trung với class priors cân bằng hơn.

**Threshold quan trọng:**
- `MULTI_LABEL_THRESHOLD = 0.35` — domain được kích hoạt khi binary probability > 0.35
- `LOW_CONFIDENCE_CEILING = 0.55` — nếu confidence Stage-1 < 0.55, kích hoạt Tier-3 LLM fallback

#### `reflection.py` — Viết lại query trước khi retrieval

Xem mục [5. Reflect Query](#5-reflect-query--giải-thích-chi-tiết).

#### `prompts.py` — Template prompts cho query layer

- `ROUTER_SYSTEM_PROMPT` + `ROUTER_FEW_SHOT`: cho LLM-mode routing
- `REWRITE_SYSTEM_PROMPT`, `REWRITE_WITH_HISTORY_TEMPLATE`, `REWRITE_NO_HISTORY_TEMPLATE`: cho reflection
- `DOMAIN_CLASSIFICATION_PROMPT`: cho Tier-3 LLM domain fallback

---

### 3.5 Embedding Layer

**Thư mục:** `embedding/`

```
embedding/
├── base.py             ← BaseEmbedder ABC (embed_query, embed)
├── bge_m3.py           ← BGEm3Embedder (BAAI/bge-m3)
├── e5_multilingual.py  ← E5MultilingualEmbedder (intfloat/multilingual-e5-large)
├── ensemble.py         ← EnsembleEmbedder (kết hợp cả 2)
└── __init__.py         ← Factory: create_embedder(settings)
```

**Nhiệm vụ:**

Hệ thống dùng **dual embedding** — mỗi chunk được lưu với **2 vector** trong Qdrant (`named vectors: bge_m3, e5`):

| Model | Kích thước | Điểm mạnh |
|-------|-----------|-----------|
| BGE-M3 (BAAI/bge-m3) | 1024 dims | Đa ngôn ngữ, SOTA cho tiếng Việt |
| E5-multilingual-large | 1024 dims | Instruction-following embedding |

Khi query, **cả 2 embedder** tạo vector → search Qdrant với cả 2 named vectors → score fusion = tăng recall.

`EnsembleEmbedder` wraps cả 2 cho indexing time; ở query time `RAGPipeline` gọi từng embedder riêng.

---

### 3.6 Retrieval Layer

**Thư mục:** `retrieval/`

```
retrieval/
├── base.py                  ← BaseRetriever ABC
├── qdrant_store.py          ← QdrantStore (dual named-vector search)
├── elasticsearch_store.py   ← ElasticsearchStore (BM25 keyword search)
├── hybrid_search.py         ← HybridSearch (RRF fusion per collection)
├── multi_collection_search.py ← MultiCollectionSearch (parallel multi-collection)
├── collection_selector.py   ← CollectionSelector (domain → collections)
└── __init__.py              ← Factory: create_retriever(settings)
```

#### Kiến trúc Retrieval (4 tầng)

```
                  query_text + bge_vec + e5_vec
                           │
                           ▼
         ┌─────────────────────────────────────┐
         │      MultiCollectionSearch          │
         │  (song song qua ThreadPoolExecutor) │
         │                                     │
         │  ┌──────────┐  ┌──────────────┐     │
         │  │ stsv     │  │  quydinh     │ ... │
         │  │          │  │              │     │
         │  │  Hybrid  │  │   Hybrid     │     │
         │  │  Search  │  │   Search     │     │
         │  └────┬─────┘  └──────┬───────┘     │
         │       │               │             │
         │  ┌────▼─────┐    ┌────▼─────┐       │
         │  │ Qdrant   │    │  ES BM25 │       │
         │  │ (bge_m3  │+   │ keyword  │       │
         │  │  + e5)   │    │  search  │       │
         │  └──────────┘    └──────────┘       │
         │         ↕ RRF Fusion (per coll)      │
         └────────────┬────────────────────────┘
                      │ Global RRF merge
                      ▼
              Top-K merged results
```

**`qdrant_store.py`**: Search Qdrant với cả 2 named vectors (bge_m3 + e5), weighted score fusion.

**`elasticsearch_store.py`**: BM25 keyword search — bắt exact terms, từ viết tắt, số điều khoản.

**`hybrid_search.py`**: Kết hợp vector + BM25 qua **RRF (Reciprocal Rank Fusion)**:
```
fused_score(doc) = vector_weight × (1 / (60 + vector_rank))
                 + keyword_weight × (1 / (60 + keyword_rank))
```
Mặc định: `vector_weight=0.8, keyword_weight=0.2`.

**`multi_collection_search.py`**: Chạy `HybridSearch` song song trên tất cả collections (ThreadPoolExecutor). Sau đó merge toàn cục bằng RRF round 2.

**`collection_selector.py`**: Map domain → collections. Nếu domain rõ ràng (confidence > 0.55), chỉ search đúng collection đó. Nếu không chắc, search `["quydinh","stsv"]` fallback.

---

### 3.7 Reranking Layer

**Thư mục:** `reranking/`

```
reranking/
├── base.py          ← BaseReranker ABC + @register_reranker decorator
├── bge_reranker.py  ← BGEReranker (BAAI/bge-reranker-v2-m3 cross-encoder)
└── __init__.py      ← Factory: create_reranker(settings)
```

**Nhiệm vụ:**

Sau khi Hybrid Search trả về ~20 candidates, `BGEReranker` sử dụng **cross-encoder** (mô hình đọc cả query + document để tính relevance score) — độ chính xác cao hơn bi-encoder nhưng chậm hơn. Chỉ giữ lại `reranker_top_k=5` docs tốt nhất.

```
20 candidates → BGE cross-encoder → 5 docs chính xác nhất → LLM context
```

**Cross-encoder vs bi-encoder:**
- Bi-encoder (embedder): embed query và doc **riêng biệt** → cosine similarity. Nhanh, scalable.
- Cross-encoder (reranker): nhận **pair (query, doc)** vào cùng lúc → attention giữa chúng. Chậm hơn nhưng chính xác hơn nhiều.

---

### 3.8 LLM Layer

**Thư mục:** `llm/`

```
llm/
├── base.py      ← BaseLLM ABC (generate, generate_stream)
├── gemini.py    ← GeminiLLM (@register_llm("gemini"))
├── prompts.py   ← RAG_SYSTEM_PROMPT, CHITCHAT_SYSTEM_PROMPT, SELF_EVAL_SYSTEM_PROMPT
├── self_eval.py ← SelfEvaluator
└── __init__.py  ← Factory: create_llm(settings), register_llm decorator
```

**`gemini.py`**: Dùng Gemini API qua OpenAI-compatible endpoint. Hỗ trợ 3 mode:
- `"rag"`: RAG_SYSTEM_PROMPT + context + history
- `"chitchat"`: CHITCHAT_SYSTEM_PROMPT + history
- `"self_eval"`: SELF_EVAL_SYSTEM_PROMPT (đánh giá câu trả lời)

**`prompts.py`**: Prompt hệ thống tiếng Việt cho HUST chatbot, bao gồm các quy tắc như:
- Không trích dẫn nguồn dạng [1][2] — thay bằng tên tài liệu
- Sử dụng thông tin cá nhân sinh viên từ history
- Không bắt đầu mọi câu bằng "Chào bạn [tên]"

**`self_eval.py`**: Đánh giá câu trả lời theo 3 tiêu chí:
- **Relevance**: Câu trả lời có đúng câu hỏi không?
- **Faithfulness**: Câu trả lời có bám theo context không?
- **Completeness**: Câu trả lời có đầy đủ không?
→ Trả về `{"pass": bool, "reason": str, ...}`.

---

### 3.9 Tools Layer

**Thư mục:** `tools/`

```
tools/
└── tavily_search.py  ← TavilySearchTool (web search fallback)
```

**Khi nào được dùng:** Khi `SelfEvaluator` đánh giá câu trả lời là **fail** (không đủ chất lượng). Lúc đó pipeline gọi Tavily để tìm kiếm web, tổng hợp kết quả, và generate lại câu trả lời.

**Flow chi tiết:**
```
SelfEval fail
    │
    ▼
TavilySearchTool.search(question)
    │
    ▼
Kết quả web → format như document context
    │
    ▼
chat_model.generate(query, web_context, history)
    │
    ▼
Câu trả lời mới (có thể tốt hơn)
```

---

### 3.10 Chunking Layer

**Thư mục:** `chunking/chunker/`

| File | Nhiệm vụ |
|------|---------|
| `base_chunker.py` | `DocumentChunker` ABC |
| `hierarchical_legal_chunker.py` | `ArticleLevelLegalChunker` — chunking theo điều/khoản cho văn bản pháp quy (PyPDF2) |
| `hierarchical_legal_chunker_pymupdf.py` | Bản dùng PyMuPDF (giữ table/formula tốt hơn) |
| `olmocr_legal_chunker.py` | Chunker cho output OCR từ olmOCR |
| `kehoach_chunker.py` | Chunker đặc thù cho tài liệu kế hoạch |
| `stsv_chunker.py` | Chunker đặc thù cho tài liệu sinh viên |
| `recursive_chunker.py` | Chunker đệ quy generic (fallback) |
| `chunking.py` | `parse_legal_document_structure()` — hàm phân tích cấu trúc văn bản pháp quy |

> **Lưu ý:** Hierarchical chunker tạo parent-child chunks nhưng **chỉ child chunks được index vào Qdrant**. Parent chunks không được lưu (tiết kiệm RAM, giảm noise). Metadata của child chunk chứa `parent_id` nhưng không có lookup ngược.

---

## 4. MongoDB: Session, Turn, Query Log

**File:** `pipeline/mongo_logger.py`

### 4.1 Tổng quan 3 Collections

```
MongoDB Database: rag_chatbot
├── sessions       ← Metadata của conversation (nhẹ, không embed turns)
├── turns          ← Mỗi document = 1 cặp hỏi-đáp (tách riêng cho scalability)
└── query_logs     ← Flat analytics, 1 doc per turn (cho BI/monitoring)
```

### 4.2 Schema `sessions`

```json
{
  "session_id": "uuid4-string",      // khóa chính, unique
  "user_id": "user-abc",             // user sở hữu session (nullable)
  "title": "Điều kiện xét học bổng…", // auto-set từ câu hỏi đầu tiên (80 char)
  "created_at": "2026-04-05T10:00Z",
  "updated_at": "2026-04-05T10:30Z", // cập nhật mỗi turn
  "turn_count": 5                    // số turns, tăng atomically
}
```

**Session** đại diện cho một **cuộc hội thoại** (conversation). Khi user mở chatbot lần mới → tạo session mới. Session tồn tại xuyên suốt cuộc trò chuyện.

**Indexes:**
- `session_id` (unique) — lookup nhanh O(1)
- `(user_id, updated_at DESC)` — liệt kê sessions của user, mới nhất lên đầu

### 4.3 Schema `turns` — và ý nghĩa của `turn_id`

```json
{
  "session_id": "uuid4-string",         // FK → sessions
  "turn_id": 3,                          // ← 1-based sequential trong session
  "question": "Điều kiện xét học bổng?",
  "answer": "Theo Quy chế đào tạo 2025…",
  "intent": "rag",                       // "rag" | "chitchat" | "tool_search"
  "reflected_question": "Điều kiện xét học bổng khuyến khích học tập là gì?",
  "num_sources": 5,
  "model_name": "gemini-2.5-flash",
  "latency_ms": 2341,
  "timestamp": "2026-04-05T10:15Z"
}
```

**`turn_id`** là số thứ tự của lượt hỏi trong session đó, bắt đầu từ **1**:
- Turn 1: câu hỏi đầu tiên
- Turn 2: câu hỏi tiếp theo trong cùng session
- Turn 3: ...

`turn_id` được sinh bằng **atomic increment** vào `sessions.turn_count` (MongoDB `find_one_and_update` với `$inc`), đảm bảo không bị race condition khi concurrent requests.

**Cặp unique index:** `(session_id, turn_id)` — đảm bảo không có 2 turns trùng turn_id trong cùng session.

**`reflected_question`:** Là câu query sau khi `QueryReflector` đã rewrite (có thể `None` nếu reflection bị tắt hoặc gặp lỗi). Dùng để:
- Debug xem reflection có cải thiện query không
- Analytics: so sánh original vs reflected query

### 4.4 Schema `query_logs` — Analytics flat

```json
{
  "session_id": "uuid4-string",
  "user_id": "user-abc",
  "turn_id": 3,
  "question": "...",
  "answer": "...",
  "intent": "rag",
  "reflected_question": "...",
  "num_sources": 5,
  "model_name": "gemini-2.5-flash",
  "latency_ms": 2341,
  "timestamp": "2026-04-05T10:15Z"
}
```

Về cơ bản giống `turns` nhưng thêm `user_id`. Mục đích là làm **analytics flat table** — dễ query aggregate hơn mà không cần join với `sessions`.

**Indexes:** `session_id`, `timestamp`, `user_id` — phục vụ dashboard/monitoring.

### 4.5 `get_history()` — Load lịch sử cho context

```python
def get_history(self, session_id: str, max_turns: int = 10):
    # Lấy N turns gần nhất, sắp xếp theo thứ tự thời gian
    # Trả về: [
    #   {"role": "user", "content": "câu hỏi 1"},
    #   {"role": "assistant", "content": "trả lời 1"},
    #   {"role": "user", "content": "câu hỏi 2"},
    #   ...
    # ]
```

Pipeline tự động gọi hàm này khi `session_id` được cung cấp nhưng `history` rỗng — đảm bảo chatbot "nhớ" lịch sử hội thoại.

### 4.6 Session Title

Khi `turn_id == 1` (câu hỏi đầu tiên), session `title` được auto-set bằng 80 ký tự đầu của câu hỏi. Dùng để hiển thị trên UI danh sách session.

---

## 5. Reflect Query — Giải Thích Chi Tiết

**File:** `query/reflection.py`

### 5.1 Vấn đề Reflection giải quyết

Trong RAG, query của user thường **không tối ưu cho retrieval**:

| Vấn đề | Ví dụ | Sau reflection |
|--------|-------|---------------|
| Đại từ mơ hồ | *"Điều kiện của nó là gì?"* | *"Điều kiện xét học bổng KKHT là gì?"* |
| Viết tắt | *"Điều kiện KKHT?"* | *"Điều kiện xét học bổng khuyến khích học tập?"* |
| Quá ngắn | *"Còn điều kiện tiên quyết?"* | *"Điều kiện tiên quyết để đăng ký môn học là gì?"* |
| Thiếu ngữ cảnh | *"Bao giờ hết hạn?"* | *"Hạn cuối nộp đơn xin hoãn học là khi nào?"* |

### 5.2 Cơ chế hoạt động

```
QueryReflector.reflect(query, chat_history)
        │
        ▼
_build_user_prompt()
  - Nếu có history: REWRITE_WITH_HISTORY_TEMPLATE
      Bao gồm N turns gần nhất (mặc định 5)
  - Nếu không có history: REWRITE_NO_HISTORY_TEMPLATE
        │
        ▼
Gọi Gemini API (gemini-2.0-flash, temperature=0.3)
  System: "You are a query rewriter..."
  Input: history + query
  Output: câu query được viết lại (plain text, không explanation)
        │
        ▼
Retry logic: exponential backoff nếu RateLimitError (max 3 lần)
        │
        ▼
Nếu LLM trả về rỗng → giữ nguyên query gốc (graceful fallback)
        │
        ▼
Return: {"original": query, "rewritten": improved_query}
```

### 5.3 Prompt Rules

```
Rules:
- Resolve pronouns using chat history (e.g. "nó" → the entity)
- Expand abbreviations (e.g. "KKHT" → "khuyến khích học tập")
- Keep in Vietnamese
- Output ONLY the rewritten query, no explanation
```

### 5.4 `reflected_question` trong MongoDB

`rag_pipeline.py` log `reflected_question` riêng vào MongoDB:
```python
mongo_logger.log_turn(
    session_id=session_id,
    question=question,            # câu gốc
    result=result,
    reflected_question=reflected  # câu sau reflection
)
```

Điều này cho phép:
- **Debug**: so sánh original vs reflected để biết reflection có giúp ích không
- **Evaluation**: measure khoảng cách semantic giữa 2 câu
- **Training data**: dùng cặp (original, reflected) để fine-tune reflector

---

## 6. Routing 3 Tầng

```
User Query
    │
    ▼
[Tier 1] DomainClassifier (embedding-based, ~10-50ms, zero API cost)
    ├── intent = "chitchat" → chitchat_flow
    ├── intent = "tool_search" → (TODO: web search trực tiếp)
    └── intent = "rag"
           │
           ├── confidence ≥ 0.55?
           │      YES → Tier 2: CollectionSelector
           │      NO  → Tier 3 LLM fallback
           │
           ▼
[Tier 2] CollectionSelector (domain → collections)
    domain = "stsv"     → search collection: ["stsv"]
    domain = "quydinh"  → search collection: ["quydinh"]
    domain = "ctdt"     → search collection: ["ctdt"]
    domain = "kehoach"  → search collection: ["kehoach"]
    multi-domain        → union of all matched collections
    confidence < 0.55   → fallback: ["quydinh", "stsv"]
    no domain           → search all collections
           │
           ▼
[Tier 3] LLM Domain Fallback (chỉ khi Tier 1 confidence < 0.55)
    Gọi Gemini với DOMAIN_CLASSIFICATION_PROMPT
    Trả về: {domains: [...], confidence: "high|medium|low"}
    Merge kết quả với routing gốc → tiếp tục Tier 2
```

**4 domains (collections) tương ứng:**

| Domain | Collection | Nội dung |
|--------|-----------|---------|
| `ctdt` | ctdt | Chương trình đào tạo, môn học, tín chỉ, ngành |
| `quydinh` | quydinh | Quy chế, quy định, điều kiện, học bổng |
| `kehoach` | kehoach | Lịch học, lịch thi, deadline đăng ký, sự kiện |
| `stsv` | stsv | Thủ tục sinh viên, ký túc xá, bảo hiểm, thẻ SV |

---

## 7. Sơ Đồ Dữ Liệu Đầy Đủ

### 7.1 Data Flow khi Index

```
PDF/Markdown files
        │
        ▼
olmocr/ (OCR → Markdown)
        │
        ▼
chunking/ (ArticleLevelLegalChunker)
  Chunk theo điều/khoản/điểm
  Metadata: {title, source, article_id, chunk_id, ...}
        │
        ▼
BGEm3Embedder + E5MultilingualEmbedder
  Tạo 2 vectors per chunk
        │
   ┌────┴────┐
   ▼         ▼
Qdrant     Elasticsearch
(vector)   (BM25 index)
collection: stsv/quydinh/kehoach/ctdt
```

### 7.2 Data Flow khi Query

```
User question (string)
        │
   ┌────▼─────────────────────────────────────────────────────┐
   │                   RAGPipeline.query()                    │
   │                                                          │
   │  question → [QueryRouter] → intent + domain + confidence │
   │                                                          │
   │  intent=rag → [QueryReflector] → search_query            │
   │                                                          │
   │  domain+conf → [CollectionSelector] → target_collections │
   │                                                          │
   │  search_query → [BGE-M3 Embedder] → bge_vec (1024-dim)  │
   │  search_query → [E5 Embedder]     → e5_vec (1024-dim)   │
   │                                                          │
   │  bge_vec+e5_vec+text → [MultiCollectionSearch]          │
   │    per collection:                                       │
   │      Qdrant(bge_m3 + e5) → 20 vector results            │
   │      Elasticsearch(BM25) → 20 keyword results           │
   │      RRF fusion → per-collection top-N                  │
   │    global merge: RRF round 2 → top-20                   │
   │                                                          │
   │  top-20 → [BGEReranker] → top-5 (cross-encoder)         │
   │                                                          │
   │  top-5 → format_context → context string                │
   │                                                          │
   │  (question + context + history) → [GeminiLLM] → answer  │
   │                                                          │
   │  (question + context + answer) → [SelfEvaluator]        │
   │    pass → return answer                                  │
   │    fail → [TavilySearch] → web context → re-generate    │
   └──────────────────────────────────────────────────────────┘
        │
        ▼
MongoDB: log_turn(session_id, question, reflected, answer, intent, ...)
        │
        ▼
API Response: {answer, sources, intent, session_id, ...}
```

---

## 8. Danh Sách File & Nhiệm Vụ

### `config/`

| File | Nhiệm vụ |
|------|---------|
| `settings.py` | Single source of truth. Pydantic BaseSettings đọc từ `.env`. Định nghĩa tất cả config knobs. |

### `api/`

| File | Nhiệm vụ |
|------|---------|
| `main.py` | FastAPI app entry point. `lifespan()` khởi tạo RAGPipeline + MongoLogger khi startup. CORS middleware. Mount routers. |
| `schemas.py` | Pydantic models: `ChatRequest`, `ChatResponse`, `RetrievedDocument`, `HistoryMessage`. |
| `routes/chat.py` | `POST /chat` (sync answer) và `POST /chat/stream` (SSE). Auto-create session. |
| `routes/session.py` | `POST /session`, `GET /session/{id}`, `GET /sessions?user_id=`. |
| `routes/health.py` | `GET /health` — health check. |

### `pipeline/`

| File | Nhiệm vụ |
|------|---------|
| `rag_pipeline.py` | `RAGPipeline` class. Khởi tạo toàn bộ system. `query()` và `query_stream()` là public API. Điều phối 3-tier routing và các flows. |
| `flows.py` | Pure logic: `chitchat_flow`, `rag_flow`, `chitchat_flow_stream`, `rag_flow_stream`. Không biết về HTTP hay MongoDB. |
| `mongo_logger.py` | `MongoLogger`. CRUD cho 3 collections: sessions, turns, query_logs. `get_history()` cho context loading. |

### `query/`

| File | Nhiệm vụ |
|------|---------|
| `router.py` | `QueryRouter`. Mode "classifier" (DomainClassifier) hoặc "llm" (OpenAI). `build_routing_input()` thêm context từ history. |
| `domain_classifier.py` | `DomainClassifier`. 2-stage: Stage-1 intent (CalibratedLR), Stage-2 domain (OvR LR). Train, save/load `.joblib`. `predict()`. |
| `reflection.py` | `QueryReflector`. Rewrite query qua Gemini. Xử lý rate limit với exponential backoff. |
| `prompts.py` | Prompt templates: Router few-shot, Reflection system/user, Domain classification (LLM fallback). |
| `training_data.py` | `RAG_LABELS` và training samples cho DomainClassifier. |

### `embedding/`

| File | Nhiệm vụ |
|------|---------|
| `base.py` | `BaseEmbedder` ABC: `embed_query(text)`, `embed(texts)`. |
| `bge_m3.py` | `BGEm3Embedder`. Dùng `FlagEmbedding` lib. |
| `e5_multilingual.py` | `E5MultilingualEmbedder`. Dùng SentenceTransformers. |
| `ensemble.py` | `EnsembleEmbedder`. Dùng cho indexing time (embed cả 2 cùng lúc). |
| `__init__.py` | `create_embedder(settings)` factory. |

### `retrieval/`

| File | Nhiệm vụ |
|------|---------|
| `base.py` | `BaseRetriever` ABC. |
| `qdrant_store.py` | `QdrantStore`. Search Qdrant với 2 named vectors. Score fusion. |
| `elasticsearch_store.py` | `ElasticsearchStore`. BM25 keyword search. |
| `hybrid_search.py` | `HybridSearch`. Kết hợp Qdrant + ES qua RRF. `filter_by_score()`. |
| `multi_collection_search.py` | `MultiCollectionSearch`. Parallel search per collection. Global merge. Factory `from_collection_names()`. |
| `collection_selector.py` | `CollectionSelector`. domain + confidence → target collections list. |
| `__init__.py` | `create_retriever(settings)` factory. |

### `reranking/`

| File | Nhiệm vụ |
|------|---------|
| `base.py` | `BaseReranker` ABC + `@register_reranker` decorator. |
| `bge_reranker.py` | `BGEReranker`. Cross-encoder BAAI/bge-reranker-v2-m3. |
| `__init__.py` | `create_reranker(settings)` factory. Trả về `None` nếu provider="none". |

### `llm/`

| File | Nhiệm vụ |
|------|---------|
| `base.py` | `BaseLLM` ABC: `generate()`, `generate_stream()`. |
| `gemini.py` | `GeminiLLM` dùng OpenAI-compatible Gemini endpoint. 3 modes: rag/chitchat/self_eval. |
| `prompts.py` | System prompts tiếng Việt: `RAG_SYSTEM_PROMPT`, `CHITCHAT_SYSTEM_PROMPT`, `SELF_EVAL_SYSTEM_PROMPT`. User templates. |
| `self_eval.py` | `SelfEvaluator`. Đánh giá relevance + faithfulness + completeness. Parse JSON từ LLM. |
| `__init__.py` | `create_llm(settings)` factory + `@register_llm` decorator. |

### `tools/`

| File | Nhiệm vụ |
|------|---------|
| `tavily_search.py` | `TavilySearchTool`. Web search fallback khi self-eval fail. |

### `chunking/chunker/`

| File | Nhiệm vụ |
|------|---------|
| `base_chunker.py` | `DocumentChunker` ABC. |
| `hierarchical_legal_chunker.py` | Chunking theo điều/khoản cho văn bản pháp quy (PDF → PyPDF2). |
| `hierarchical_legal_chunker_pymupdf.py` | Bản PyMuPDF: giữ table và format tốt hơn. |
| `olmocr_legal_chunker.py` | Chunker cho file Markdown output từ olmOCR. |
| `kehoach_chunker.py` | Chunker đặc thù tài liệu kế hoạch học tập. |
| `stsv_chunker.py` | Chunker đặc thù tài liệu sinh viên. |
| `recursive_chunker.py` | Overlap-based recursive chunker (generic fallback). |
| `chunking.py` | `parse_legal_document_structure()` — parse cấu trúc điều/khoản/điểm. |

---

## 9. Cấu Hình .env Quan Trọng

```bash
# LLM
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your-key-here
CHAT_MODEL=gemini-2.5-flash

# Embedding
EMBEDDING_PROVIDER=ensemble   # ensemble | bge_m3 | e5

# Reranking
RERANKER_PROVIDER=bge         # bge | none

# Databases
QDRANT_HOST=localhost
QDRANT_PORT=6333
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=rag_chatbot

# Collections
COLLECTIONS=["stsv","quydinh","kehoach","ctdt"]

# Features
REFLECTION_ENABLED=true
SELF_EVAL_ENABLED=true
TAVILY_FALLBACK_ENABLED=true
TAVILY_API_KEY=your-tavily-key

# Routing
ROUTER_MODE=classifier        # classifier | llm
DOMAIN_ROUTING_ENABLED=true
DOMAIN_CONFIDENCE_THRESHOLD=0.65

# Retrieval tuning
TOP_K=5
VECTOR_TOP_K=20
KEYWORD_TOP_K=20
VECTOR_WEIGHT=0.8
KEYWORD_WEIGHT=0.2
RERANKER_TOP_K=5
```

---

*Tài liệu được tạo tự động từ codebase — April 2026*
