# HUST Academic Chatbot — System Architecture

> Hệ thống chatbot học vụ Đại học Bách khoa Hà Nội, sử dụng RAG, Hybrid Search và LangGraph Agent.

## 1. Tổng Quan Hệ Thống

```mermaid
graph TB
    subgraph Clients["🖥️ Clients"]
        Web["React + Vite<br/>Web App"]
        Mobile["Expo / React Native<br/>Mobile App"]
    end

    subgraph API["⚡ FastAPI Backend :8000"]
        ChatRoute["/chat • /chat/v3 • /chat/stream"]
        AuthRoute["/auth • OAuth • JWT"]
        SessionRoute["/session • /sessions"]
        AdminRoute["/admin/documents"]
        OtherRoutes["/health • /metrics • /retrieval<br/>/bookmarks • /feedback • /lookup • /notifications"]
    end

    subgraph Core["🧠 RAG Core"]
        Pipeline["RAGPipeline<br/>Orchestrator"]
        QueryLayer["Query Layer<br/>Complexity → Domain → Reflection"]
        RAGFlow["Classic RAG Flow"]
        Agent["LangGraph Agent<br/>ReAct + Planner-Executor"]
    end

    subgraph Retrieval["🔍 Retrieval Engine"]
        RetService["RetrievalService"]
        BGE["BGE-M3<br/>1024d"]
        E5["E5-multilingual<br/>1024d"]
        MultiSearch["MultiCollectionSearch"]
        Reranker["BGE Reranker v2-m3"]
        Tavily["Tavily Web Search"]
    end

    subgraph Stores["💾 Data Stores"]
        Qdrant[("Qdrant :6333<br/>Vector DB")]
        ES[("Elasticsearch :9200<br/>BM25 Keyword")]
        Mongo[("MongoDB :27017<br/>Persistence")]
        Redis[("Redis :6379<br/>Cache (optional)")]
    end

    subgraph DataPipeline["📥 Data Ingest"]
        AdminUpload["DocumentPipeline<br/>PDF → MD → Chunk → Index"]
        Crawler["AutoCrawler<br/>kehoach • quydinh"]
        Scripts["CLI Scripts<br/>index • metadata"]
    end

    Web & Mobile --> API
    ChatRoute --> Pipeline
    Pipeline --> QueryLayer --> RAGFlow & Agent
    RAGFlow & Agent --> RetService
    RetService --> BGE & E5 & MultiSearch & Reranker
    RetService -.-> Tavily
    MultiSearch --> Qdrant & ES
    RAGFlow --> LLM["Gemini LLM"]
    Agent --> SynthLLM["Agent Synthesis LLM"]
    Pipeline --> Mongo & Redis
    AdminRoute --> AdminUpload
    AdminUpload --> Qdrant & ES & Mongo
    Crawler --> Qdrant & ES
```

---

## 2. Cấu Trúc Thư Mục

```text
GR/
└── src/RAG_v2/
    ├── api/                    # FastAPI app, routes, middleware, response mapper
    ├── auth/                   # JWT, Microsoft OAuth, password, RBAC
    ├── pipeline/               # RAGPipeline, flows.py, DocumentPipeline
    ├── query/                  # ComplexityRouter, DomainClassifier, Reflector, Decomposer
    ├── retrieval/              # Qdrant, Elasticsearch, hybrid search, filters, resolver
    ├── embedding/              # BGE-M3, E5, ensemble embedders
    ├── reranking/              # BGE cross-encoder reranker
    ├── llm/                    # Gemini, LM Studio, prompts, self-eval
    ├── agent/                  # LangGraph ReAct + planner-executor
    ├── models/                 # MongoDB models, MongoLogger
    ├── schemas/                # Pydantic API contracts
    ├── cache/                  # Redis session, history, LLM cache, rate limiter
    ├── tools/                  # Tavily web search adapter
    ├── config/                 # Settings (load from .env)
    ├── chunking/               # Legal, curriculum, STSV, kehoach chunkers
    ├── document_loader/        # PDF/Docx → Markdown
    ├── scripts/                # Crawlers, indexers, metadata tools
    ├── data/                   # Domain datasets (ctdt, quydinh, kehoach, stsv)
    ├── frontend/chat-companion/# React web app
    ├── mobile/                 # Expo mobile app
    ├── packages/shared/        # Shared TS types, API clients, Zustand stores
    ├── eval/, evaluation/      # Golden datasets, evaluation runners
    └── docker-compose.yml      # Local infra
```

---

## 3. Flow 1: Backend Startup

```mermaid
sequenceDiagram
    participant U as Uvicorn
    participant L as lifespan()
    participant S as Settings
    participant M as MongoLogger
    participant R as RedisManager
    participant P as RAGPipeline
    participant C as AutoCrawler

    U->>L: startup
    L->>S: load .env → Settings()
    L->>M: init MongoLogger (if mongodb_enabled)
    L->>R: init Redis, SessionStore, RateLimiter, LLMCache, HistoryCache
    L->>P: build RAGPipeline in executor (load embedders, searcher, reranker, agent)
    L->>M: create_indexes() (sessions, turns, users, documents...)
    L->>P: warmup agent LLM (background task)
    L->>C: schedule AutoCrawler daily (if crawler_enabled)
    L-->>U: app ready on :8000
```

---

## 4. Flow 2: Chat Request Processing (Tổng Quan)

```mermaid
flowchart TD
    A["Client gửi POST /chat hoặc /chat/stream"] --> B["API Layer"]
    B --> B1["Authenticate JWT (optional)"]
    B1 --> B2["Resolve session_id + history"]
    B2 --> B3{"mode?"}

    B3 -->|"auto"| C["pipeline.query_v3()"]
    B3 -->|"rag"| D["pipeline.query()"]
    B3 -->|"agent"| E["pipeline.query_agent()"]

    C --> F["ComplexityRouter"]
    F -->|"chitchat"| G["🗨️ Hardcoded response<br/>no retrieval"]
    F -->|"simple"| H["📚 Classic RAG Flow"]
    F -->|"complex + multi_source"| I["QueryDecomposer"]
    F -->|"complex (other)"| J["🤖 LangGraph Agent"]

    I -->|"≥ 2 subqueries"| K["Decomposed RAG<br/>per-domain retrieval"]
    I -->|"< 2"| H
    J -->|"success"| L["Agent Result"]
    J -->|"disabled/error"| H

    H --> M["Final Answer"]
    K --> M
    L --> M
    G --> M

    M --> N["MongoLogger.log_turn()"]
    N --> O["API Response / SSE Stream"]

    style G fill:#4ade80,color:#000
    style H fill:#60a5fa,color:#000
    style K fill:#a78bfa,color:#000
    style L fill:#f97316,color:#000
```

---

## 5. Flow 3: Query Processing Layer (Chi Tiết)

```mermaid
flowchart TD
    Raw["Raw question + history + user_context"] --> CR["ComplexityRouter<br/>regex + heuristics"]

    CR --> T0{"tier?"}
    T0 -->|"chitchat"| CHIT["Return canned response"]
    T0 -->|"simple"| QR["QueryRouter"]
    T0 -->|"complex"| SUB{"complex_subtype?"}

    SUB -->|"multi_source"| DEC["QueryDecomposer<br/>LLM JSON split"]
    SUB -->|"comparison"| AGENT_P["Agent Planner path"]
    SUB -->|"personal_check / general"| AGENT_R["Agent ReAct / RAG fallback"]

    QR --> DC["DomainClassifier<br/>BGE-M3 + LogisticRegression"]
    DC --> CONF{"confidence < 0.55<br/>AND margin < 0.25?"}
    CONF -->|"yes"| T3["Tier-3 Gemini LLM classify"]
    CONF -->|"no"| CS["CollectionSelector"]
    T3 --> CS

    CS --> REF["QueryReflector"]
    REF --> R1["Strip PII/noise"]
    R1 --> R2["Merge user_context + session profile"]
    R2 --> R3["LLM rewrite → standalone query"]
    R3 --> R4["Regex entity extraction"]
    R4 --> ENT["Entities: major_code, cohort,<br/>course_code, semester, academic_year"]
    ENT --> READY["Search-ready query + filters"]
```

---

## 6. Flow 4: Classic RAG Flow (Chi Tiết)

```mermaid
flowchart TD
    Q["Question + history"] --> TRIM["Trim history theo limit"]
    TRIM --> ROUTE["QueryRouter + domain routing"]
    ROUTE --> P0{"P0 query-only<br/>cache hit?"}
    P0 -->|"hit"| RET_CACHE["Return cached answer"]
    P0 -->|"miss"| REFLECT["QueryReflector.reflect()"]

    REFLECT --> ENTITY["Entity fallback extraction"]
    ENTITY --> SELECT["CollectionSelector<br/>chọn collections đích"]
    SELECT --> NORM["Normalize query<br/>expand comparison subqueries"]

    NORM --> EMBED["Embed: BGE-M3 + E5"]
    EMBED --> SEARCH["MultiCollectionSearch"]

    subgraph HybridSearch["Hybrid Search Engine"]
        SEARCH --> META["ES metadata pre-filter<br/>fallback chain"]
        META --> PAR["ThreadPoolExecutor<br/>per collection"]
        PAR --> QD["Qdrant vector search<br/>(BGE + E5 weighted)"]
        PAR --> KW["ES BM25 keyword search"]
        QD --> FUSE["Min-max score fusion<br/>vector 0.8 + keyword 0.2"]
        KW --> FUSE
    end

    FUSE --> EMPTY{"Kết quả rỗng?"}
    EMPTY -->|"yes"| RETRY["Retry chain:<br/>1. decomposed query<br/>2. disable quydinh filter<br/>3. all collections<br/>4. relaxed comparison"]
    EMPTY -->|"no"| DEDUP["Dedup by id/text"]
    RETRY --> DEDUP

    DEDUP --> RERANK["BGE Reranker<br/>cross-encoder scoring"]
    RERANK --> THRESH["Filter by threshold<br/>before top-k cut"]
    THRESH --> VALID["ValidityFilter<br/>drop superseded docs"]
    VALID --> REFS["ReferenceResolver<br/>insert Điều/khoản refs"]

    REFS --> P2{"P2 doc-aware<br/>cache hit?"}
    P2 -->|"hit"| RET_CACHE
    P2 -->|"miss"| CTX["Format context<br/>budget: 12k/24k chars"]

    CTX --> GEN["Gemini LLM generate"]
    GEN --> WRITE["Write P2 + P0 cache"]
    WRITE --> EVAL{"Self-eval enabled<br/>AND top_score < 0.72?"}
    EVAL -->|"fail"| TAV["Tavily web search<br/>+ regenerate"]
    EVAL -->|"skip/pass"| FINAL["✅ Final answer"]
    TAV --> FINAL
```

---

## 7. Flow 5: Hybrid Retrieval (Chi Tiết)

```mermaid
flowchart LR
    subgraph Input
        Q["Search Query"]
    end

    subgraph Embedding
        Q --> BGE["BGE-M3 → 1024d vector"]
        Q --> E5_["E5 → 1024d vector"]
        Q --> BM25["Keyword tokenize"]
    end

    subgraph VectorSearch["Qdrant Vector Search"]
        BGE --> Q1["Named vector: bge_m3"]
        E5_ --> Q2["Named vector: e5"]
        Q1 --> WF["Weighted fusion<br/>BGE + E5"]
        Q2 --> WF
    end

    subgraph KeywordSearch["Elasticsearch BM25"]
        BM25 --> ES_["multi_match<br/>text^1.0 + title^1.5<br/>fuzziness AUTO"]
    end

    subgraph Fusion["Score Fusion"]
        WF --> NV["Min-max normalize<br/>vector scores"]
        ES_ --> NK["Min-max normalize<br/>keyword scores"]
        NV --> SF["Weighted sum<br/>vector×0.8 + keyword×0.2"]
        NK --> SF
    end

    subgraph Post["Post-processing"]
        SF --> DD["Dedup"]
        DD --> RR["BGE Reranker"]
        RR --> TOP["Top-K candidates"]
    end
```

**Metadata Pre-filter theo Collection:**

| Collection | Filter | Fallback |
|---|---|---|
| `ctdt` | `major_code`, fuzzy `major_name` | generic/null |
| `quydinh` | `applicable_cohort`, `applicable_major` | no filter |
| `kehoach` | `date_str` month/year wildcard | no filter |
| `stsv` | Không pre-filter | — |

---

## 8. Flow 6: LangGraph Agent

```mermaid
flowchart TD
    START(("START")) --> ROUTE{"execution_path?"}

    subgraph PlannerPath["Planner-Executor Path"]
        ROUTE -->|"comparison / multi_source"| DECOMPOSE["_decompose_node()<br/>LLM tách câu hỏi"]
        DECOMPOSE --> PLAN["_planner_node()<br/>LLM tạo JSON plan"]
        PLAN --> VALIDATE{"≥ 50% steps valid?"}
        VALIDATE -->|"yes"| EXEC["_executor_node()<br/>parallel retrieval"]
        VALIDATE -->|"no"| REACT
        EXEC --> SYNTH["_synthesize_node()<br/>tổng hợp tiếng Việt"]
    end

    subgraph ReActPath["ReAct Loop Path"]
        ROUTE -->|"general / default"| REACT["ReAct Agent Node<br/>Local LM Studio model"]
        REACT --> DECIDE{"output?"}
        DECIDE -->|"tool_calls"| TOOLS["Execute Tools"]
        DECIDE -->|"direct answer"| EXTRACT["Extract answer"]
        DECIDE -->|"error / max iter / loop"| SYNTH2["Synthesis fallback"]

        TOOLS --> AFTER{"after tools?"}
        AFTER -->|"continue"| REACT
        AFTER -->|"error"| SYNTH2
        AFTER -->|"clarify / end"| EXTRACT
    end

    SYNTH --> END_((END))
    SYNTH2 --> END_
    EXTRACT --> END_
```

**Agent Tools:**

| Tool | Mô tả |
|---|---|
| `rag_search` | Tìm kiếm 1 collection nội bộ |
| `web_search` | Tavily fallback cho dữ liệu thiếu/mới |
| `clarify_question` | Hỏi lại user khi query mơ hồ |

---

## 9. Flow 7: SSE Streaming

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI /chat/stream
    participant P as RAGPipeline
    participant LLM as Gemini LLM

    C->>API: POST /chat/stream (SSE)
    API->>API: resolve session, auth
    API->>C: data: {"type":"session","session_id":"..."}

    alt chitchat
        API->>P: chitchat_flow_stream()
        P-->>C: data: {"type":"token","delta":"..."}
    else complex + agent
        API->>P: query_agent() (blocking)
        P-->>C: data: {"type":"token","delta":"<full agent answer>"}
    else simple RAG
        API->>P: rag_flow_stream()
        P->>P: retrieval + rerank (blocking)
        P->>LLM: generate_stream()
        loop mỗi token
            LLM-->>C: data: {"type":"token","delta":"..."}
        end
    end

    API->>C: data: {"type":"metadata", ...trace...}
    API->>C: data: {"type":"done"}

    Note over API: Streaming KHÔNG chạy self-eval / Tavily fallback
```

---

## 10. Flow 8: Authentication

```mermaid
flowchart TD
    subgraph MSAuth["Microsoft OAuth Flow"]
        A1["Client → GET /auth/login"] --> A2["Redirect → Microsoft"]
        A2 --> A3["User đăng nhập @sis.hust.edu.vn"]
        A3 --> A4["GET /auth/callback"]
        A4 --> A5["Exchange code → validate email"]
        A5 --> A6["Parse HUST metadata<br/>(student_id, cohort, major)"]
        A6 --> A7["Upsert MongoDB user"]
        A7 --> A8["Issue JWT → redirect frontend"]
    end

    subgraph Manual["Manual Auth"]
        B1["POST /auth/register"] --> B2["Create user + hash password"]
        B3["POST /auth/login"] --> B4["Verify → Issue JWT"]
    end

    subgraph Protected["Protected Routes"]
        C1["Bearer JWT in header"]
        C1 --> C2["Decode → get user_id, role"]
        C2 --> C3{"role?"}
        C3 -->|"student"| C4["Normal access"]
        C3 -->|"admin"| C5["Admin routes enabled"]
    end
```

---

## 11. Flow 9: Admin Document Upload

```mermaid
flowchart TD
    UP["Admin uploads PDF"] --> STORE["LocalStorage<br/>uploads/{doc_id}/original.pdf"]
    STORE --> REC["MongoDB documents<br/>status: uploaded"]

    REC --> CONV["convert_pdf<br/>(pymupdf4llm / docling)"]
    CONV --> MD["markdown.md"]
    MD --> CLEAN["clean_markdown()"]
    CLEAN --> CMD["cleaned.md"]

    CMD --> CHUNK["Chunk with strategy<br/>(recursive / hierarchical / olmocr)"]
    CHUNK --> CHUNKS["MongoDB document_chunks"]

    CHUNKS --> POLICY["is_indexable_chunk()<br/>skip parent/header"]
    POLICY --> EMB["Embed: BGE-M3 + E5"]
    EMB --> QD["Qdrant upsert"]
    EMB --> ES_["ES bulk index"]
    ES_ --> DONE["status: indexed ✅"]

    REC -.->|"Status lifecycle"| SL["uploaded → converting → converted<br/>→ cleaning → cleaned → chunking<br/>→ chunked → embedding → indexed"]
```

---

## 12. Flow 10: Auto Crawler

```mermaid
flowchart LR
    SCHED["APScheduler<br/>daily cron"] --> CRAWL["AutoCrawlPipeline"]
    CRAWL --> FETCH["Fetch HUST APIs<br/>DisplayListBaiViet<br/>DisplayListKeHoach<br/>DisplayQuyChe"]
    FETCH --> JSON["Save JSON"]
    JSON --> CHUNK_["Chunk"]
    CHUNK_ --> EMB_["Embed BGE-M3 + E5"]
    EMB_ --> IDX["Index Qdrant + ES"]
    IDX --> RET["Retention cleanup"]
```

---

## 13. Persistence & Cache

```mermaid
flowchart TD
    subgraph MongoDB["MongoDB Collections"]
        U_["users"] --- S_["sessions"] --- T_["turns"]
        QL["query_logs"] --- AT["agent_traces"]
        DOC["documents"] --- DC["document_chunks"]
        BK["bookmarks"] --- BKF["bookmark_folders"]
        FB["feedback"]
        NF["notifications"] --- NS["notification_subscriptions"]
    end

    subgraph RedisKeys["Redis Key Patterns"]
        RS["session:{sid}"] --- RUS["user_sessions:{uid}"]
        RH["history:{sid}"]
        RC["llm_cache:{sha}"] --- RCQ["llm_cache:q:{sha}"]
        RDC["doc_cache_tag:{did}"]
        RR["rate:min:{id}"] --- RRD["rate:day:{id}"]
    end
```

---

## 14. Technology Stack

| Layer | Công nghệ |
|---|---|
| **API** | FastAPI + SSE, Uvicorn |
| **Orchestration** | `pipeline/rag_pipeline.py`, `pipeline/flows.py` |
| **Agent** | LangGraph StateGraph, LangChain tools |
| **Vector Search** | Qdrant (named vectors: `bge_m3` + `e5`, 1024d, cosine) |
| **Keyword Search** | Elasticsearch BM25, ICU analyzer |
| **Embedding** | `BAAI/bge-m3` + `intfloat/multilingual-e5-large` |
| **Reranking** | `BAAI/bge-reranker-v2-m3` cross-encoder |
| **Main LLM** | Gemini (OpenAI-compatible endpoint) |
| **Agent Tool LLM** | LM Studio local (qwen2.5-7b-instruct) |
| **Persistence** | MongoDB (Motor async + MongoLogger sync) |
| **Cache** | Redis (optional: session, history, LLM cache, rate limit) |
| **Web Frontend** | React + Vite + TanStack Query + shadcn/Radix UI |
| **Mobile** | Expo/React Native + `@rag/shared` + SecureStore + MMKV |
| **Infra** | Docker Compose (Qdrant, ES, MongoDB, Redis) |

---

## 15. Data Sources

| Collection | Nội dung | Filter chính |
|---|---|---|
| `ctdt` | Chương trình đào tạo, môn học, tín chỉ | `major_code`, `major_name` |
| `quydinh` | Quy chế, quy định học vụ, học bổng | `applicable_cohort`, `applicable_major` |
| `kehoach` | Kế hoạch học kỳ, lịch, thông báo | `date_str` |
| `stsv` | Sổ tay sinh viên, thủ tục, biểu mẫu | Không pre-filter |

---

## 16. Local Development

```bash
cd src/RAG_v2

# Start infrastructure
docker compose up -d qdrant elasticsearch mongodb redis

# Start backend
make backend  # hoặc: .venv/bin/python backend/main.py

# Start web frontend
cd frontend/chat-companion && npm run dev
```

| Service | Port |
|---|---|
| Backend API | `8000` |
| Qdrant | `6333` |
| Elasticsearch | `9200` |
| MongoDB | `27017` |
| Redis | `6379` |
| Web Frontend | `5173` |

---

## 17. Module Documentation

Xem chi tiết từng module tại `MODULE.md` tương ứng và [ARCHITECTURE.md](src/RAG_v2/ARCHITECTURE.md).
