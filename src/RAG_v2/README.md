# RAG_v2 — Hệ thống Chatbot Học vụ ĐHBK Hà Nội

Hệ thống RAG (Retrieval-Augmented Generation) thế hệ 2, phục vụ tra cứu thông tin học vụ tại Đại học Bách khoa Hà Nội. Tích hợp hybrid search, LangGraph agentic reasoning, và streaming response.

---

## Stack công nghệ

| Layer | Technology |
|-------|-----------|
| API | FastAPI + SSE |
| Orchestration | `pipeline/rag_pipeline.py` + `flows.py` |
| Agent | LangGraph `StateGraph` |
| Vector store | Qdrant (BGE-M3 + E5 named vectors) |
| Keyword store | Elasticsearch BM25 |
| Embedding | BGE-M3 + E5-multilingual (1024-dim) |
| Reranker | BGE-reranker-v2-m3 |
| Main LLM | Gemini (OpenAI-compatible endpoint) |
| Agent tool LLM | LM Studio local (qwen2.5-7b-instruct) |
| Persistence | MongoDB (Motor async) |
| Cache | Redis (optional, falls back to MongoDB) |
| Web | React + Vite + TanStack Query + shadcn |
| Mobile | Expo / React Native + @rag/shared |

---

## Cấu trúc thư mục

```
RAG_v2/
├── api/                  # FastAPI routes, middleware, schemas
├── pipeline/             # Orchestrator: rag_pipeline.py, flows.py
├── query/                # Query understanding: router, reflector, decomposer
├── retrieval/            # Hybrid search: Qdrant + ES, fusion, filters
├── embedding/            # BGE-M3 + E5 embedders
├── reranking/            # BGE cross-encoder reranker
├── llm/                  # Gemini + LM Studio providers, self-eval
├── agent/                # LangGraph ReAct + Planner-Executor agent
├── cache/                # Redis: LLM cache, session, history, rate limiter
├── models/               # MongoDB: users, sessions, documents, chunks
├── chunking/             # Offline text chunking pipeline
├── document_loader/      # PDF → Markdown conversion
├── schemas/              # Shared Pydantic schemas
├── config/               # Settings (pydantic-settings)
├── scripts/              # CLI utilities, indexing scripts
├── data/                 # Training data, reference docs
├── eval/                 # Evaluation scripts
├── frontend/chat-companion/  # React web UI
├── mobile/               # Expo mobile app
└── docker-compose.yml
```

---

## Flow tổng thể của hệ thống

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User (Web / Mobile)                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP / SSE
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI (api/)                                    │
│  Auth → Rate Limit → Session Lookup → Route to pipeline             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 RAGPipeline.query_v3() (pipeline/)                   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │            Tier-0: ComplexityRouter (query/)                  │  │
│  │  regex/heuristics → chitchat | simple | complex              │  │
│  └───────────────┬───────────────┬───────────────────────────────┘  │
│                  │               │                                  │
│           chitchat         simple/complex                           │
│                  │               │                                  │
│                  ▼               ▼                                  │
│        _handle_chitchat() [Tier-1] QueryRouter (ML classifier)     │
│                                  │                                  │
│                   ┌──────────────┼──────────────────┐              │
│                   │              │                  │              │
│                simple   comparison/           complex              │
│                   │     multi_source           (other)             │
│                   │              │                  │              │
│                   ▼              ▼                  ▼              │
│            rag_flow()   _query_decomposed()   query_agent()        │
│                   │              │                  │              │
│                   │        QueryDecomposer     LangGraph Agent     │
│                   │         (sub-queries)          (fallback)      │
│                   └──────────────┴──────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                Classic RAG Flow (pipeline/flows.py)                 │
│                                                                     │
│  0.  P0 Cache check (cache/)                                        │
│  1.  QueryReflector (query/) — rewrite, PII strip, entity extract   │
│  2.  CollectionSelector (retrieval/) — chọn collections            │
│  3.  Decompose comparison queries                                   │
│  4.  Embed (embedding/) → Hybrid Search (retrieval/)               │
│        Qdrant BGE-M3 + E5  ──┐                                     │
│        Elasticsearch BM25 ───┴── Score Fusion                      │
│  5.  Deduplication                                                  │
│  6.  BGE Reranker (reranking/) — cross-encoder scoring              │
│  7.  ValidityFilter (retrieval/) — lọc tài liệu hết hiệu lực       │
│  8.  ReferenceResolver (retrieval/) — resolve tham chiếu chéo      │
│  9.  P2 Cache check (cache/)                                        │
│  10. Format context (1500 chars/doc, 8000 total)                    │
│  11. LLM Generation (llm/) — Gemini                                 │
│  12. Cache write P2 + P0                                            │
│  13. SelfEvaluator → Tavily fallback (nếu score < 0.72)            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LangGraph Agent (agent/)                         │
│                                                                     │
│  comparison/multi_source path:                                      │
│    decompose → planner → executor (parallel retrieval) → synthesize │
│                                                                     │
│  general complex path:                                              │
│    ReAct loop: agent ↔ tools (rag_search / web_search / clarify)   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 Persistence & Cache                                  │
│  MongoDB (models/): users, sessions, turns, agent_traces, docs      │
│  Redis (cache/):    session, history, LLM cache, rate limit         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Offline Data Ingest Pipeline

```
Raw PDF / Markdown
    │
    ▼
document_loader/ — PDF to Markdown (olmOCR / PyMuPDF)
    │
    ▼
chunking/ — Hierarchical legal chunker
    Docling/PyMuPDF format: Article-level, parent-child
    Output: {id, readable_id, content, parent_id, metadata}
    │
    ▼
scripts/index_*.py — Batch embed + upsert
    → Qdrant (BGE-M3 + E5 named vectors)
    → Elasticsearch (text + metadata)
```

### Admin Upload Pipeline (online)

```
POST /upload → converting → cleaning → chunking → embedding → indexed
                                                            (or: failed)
```

---

## Query Routing — 3-tier Decision

```
Tier-0: ComplexityRouter (regex, ~0ms)
    ↓ nếu không đủ confidence
Tier-1: DomainClassifier (BGE-M3 + Logistic Regression, ~50ms)
    ↓ confidence < 0.55 && margin < 0.25
Tier-3: Gemini LLM classify (~1–3s, chỉ dùng khi fallback)
```

---

## Cấu hình local development

```bash
# Khởi động services
docker-compose up qdrant elasticsearch mongodb redis

# Backend
cd src/RAG_v2
make backend        # uvicorn api.main:app --reload

# Frontend
cd frontend/chat-companion
bun dev
```

**Ports:**

| Service | Port |
|---------|------|
| Backend API | 8000 |
| Qdrant | 6333 |
| Elasticsearch | 9200 |
| MongoDB | 27017 |
| Redis | 6379 |
| Frontend | 5173 |

---

## Module README

Mỗi module có file `README.md` mô tả chi tiết luồng hoạt động:

| Module | Mô tả |
|--------|-------|
| [api/README.md](api/README.md) | FastAPI routes, startup sequence, streaming SSE |
| [pipeline/README.md](pipeline/README.md) | Orchestrator, 13-step rag_flow, agent routing |
| [query/README.md](query/README.md) | ComplexityRouter, DomainClassifier, Reflector, Decomposer |
| [retrieval/README.md](retrieval/README.md) | Hybrid search, Qdrant + ES, fusion, filters |
| [embedding/README.md](embedding/README.md) | BGE-M3, E5-multilingual, ensemble |
| [reranking/README.md](reranking/README.md) | BGE cross-encoder reranker |
| [llm/README.md](llm/README.md) | Gemini, LM Studio, SelfEvaluator, prompts |
| [agent/README.md](agent/README.md) | LangGraph topology, Planner-Executor, ReAct tools |
| [cache/README.md](cache/README.md) | Dual-layer LLM cache, session, history, rate limit |
| [models/README.md](models/README.md) | MongoDB models, MongoLogger, DocumentRecord |
| [chunking/README.md](chunking/README.md) | Hierarchical legal chunker pipeline |

---

## Latency Budget (typical request)

| Bước | Thời gian |
|------|---------|
| API overhead | 3–8ms |
| Query routing + reflection | 50–200ms |
| Embedding | 30–100ms (GPU) |
| Hybrid search (Qdrant + ES) | 50–300ms |
| Reranking (20 candidates, GPU) | 50–200ms |
| LLM generation (non-streaming) | 2000–15000ms ← bottleneck |
| **Tổng (P50)** | **~3–6 giây** |
