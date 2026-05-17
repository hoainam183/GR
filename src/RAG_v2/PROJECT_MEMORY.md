# PROJECT MEMORY - RAG v2 (HUST Academic Chatbot)

> Đây là memory cấp dự án. Đọc trước khi sửa code trong `src/RAG_v2`.
> Snapshot gần nhất: 2026-05-13, đối chiếu từ source code hiện tại.

---

## 0. Documentation Workflow

- Trước khi sửa code trong module nào, đọc `MODULE.md` của module đó nếu có.
- Sau khi sửa code và verify xong, cập nhật `MODULE.md` của module bị ảnh hưởng.
- `MODULE.md` là source-of-truth cấp module; `PROJECT_MEMORY.md` là source-of-truth cấp kiến trúc, public contracts, data flow và behavior liên module.
- Chỉ cập nhật file này khi thay đổi kiến trúc, API public, schema/contract, data flow, runtime behavior hoặc bug/caution cấp hệ thống.

---

## 1. Stack & Runtime

| Layer | Tech / Source of truth |
| --- | --- |
| API | FastAPI, app factory/lifespan ở `api/main.py` |
| Pipeline | `pipeline/rag_pipeline.py` là orchestrator chính |
| Agent | LangGraph `StateGraph` + LangChain tools trong `agent/` |
| Vector store | Qdrant, named vectors `bge_m3` + `e5` |
| Keyword store | Elasticsearch, index name trùng với collection |
| Embedding | BGE-M3 + E5 multilingual ensemble |
| Reranker | BGE reranker cross-encoder |
| LLM | Gemini qua `GOOGLE_API_KEY`, model đọc từ `.env`/`config/settings.py` |
| Agent tool LLM | LM Studio local, model đọc từ `AGENT_MODEL` |
| Agent synthesis | Gemini/LM Studio/Ollama tùy `AGENT_SYNTHESIS_PROVIDER`, default code là Gemini |
| DB logging | MongoDB qua `models/mongo_logger.py` |
| Cache/session/rate limit | Redis optional trong `cache/`, mặc định phụ thuộc `redis_enabled` |
| Web | React + Vite trong `frontend/chat-companion`, dev port `8080` |
| Mobile | Expo/React Native trong `mobile/`, shared TS package trong `packages/shared` |
| Infra docker | Qdrant `6333`, Elasticsearch `9200`, MongoDB `27017`, Redis `6379` |

**Entrypoint backend**: `api/main.py` -> `create_app()` -> lifespan khởi tạo Mongo/Redis/cache, `RAGPipeline`, index Mongo, optional crawler scheduler, sau đó include routers.

---

## 2. High-Level Architecture

```text
HTTP /chat, /chat/v3, /chat/stream
  |
  v
RAGPipeline
  |
  +-- query_v3()
  |     |
  |     +-- ComplexityRouter (query/complexity_router.py)
  |     |     +-- chitchat -> canned response
  |     |     +-- simple   -> classic query()
  |     |     +-- complex  -> decomposed RAG or agent
  |
  +-- classic RAG
  |     QueryRouter -> QueryReflector -> CollectionSelector
  |     -> metadata filters -> MultiCollectionSearch
  |     -> BGE rerank -> validity filter -> reference resolver
  |     -> LLM answer / stream
  |
  +-- agent path
        ReActAgent
          +-- planner-executor for comparison/multi-source
          +-- ReAct tool loop for normal tool-calling
          +-- synthesis LLM for final answer
```

Core rule: pipeline tạo `RetrievalService.from_settings(settings)` một lần, gán vào `self._retrieval_service`, rồi inject vào `agent.tool_adapters.inject_from_retrieval_service()` để tránh load lại embedder/searcher/reranker.

---

## 3. Module Map

```text
RAG_v2/
├── api/
│   ├── main.py                 # FastAPI app, lifespan, CORS, router include
│   ├── dependencies.py         # resolve pipeline/session dependencies
│   ├── response_mapper.py      # normalize pipeline output -> API shape
│   └── routes/
│       ├── chat.py             # /chat, /chat/v3, /api/chat/v3, /chat/stream
│       ├── health.py           # /health, /api/admin/reload-validity
│       ├── metrics.py          # /metrics/usage, /metrics/eval
│       ├── retrieval.py        # /retrieval/search diagnostic endpoint
│       ├── session.py          # /session, /session/{id}, /sessions
│       └── upload.py           # /admin document pipeline endpoints
│
├── pipeline/
│   ├── rag_pipeline.py         # RAGPipeline orchestrator
│   ├── flows.py                # chitchat_flow, rag_flow, rag_flow_stream
│   └── document_pipeline.py    # admin upload convert/clean/chunk/index/rollback
│
├── agent/
│   ├── react_agent.py          # LangGraph agent, planner/executor, synthesis
│   ├── lc_tools.py             # LANGGRAPH_TOOLS, TOOL_MAP
│   ├── tool_adapters.py        # execute_tool + retrieval adapter impl
│   ├── state.py                # AgentState, ToolResult
│   └── graph_state.py          # LangGraph state TypedDict
│
├── retrieval/
│   ├── service.py              # shared RetrievalService wrapper
│   ├── multi_collection_search.py
│   ├── qdrant_store.py
│   ├── elasticsearch_store.py
│   ├── metadata_filters.py
│   ├── collection_selector.py
│   ├── validity_filter.py
│   └── reference_resolver.py
│
├── query/
│   ├── complexity_router.py    # Tier-0 chitchat/simple/complex
│   ├── router.py               # domain classifier/router
│   ├── reflection.py           # rewrite + entity extraction
│   └── domain_classifier.py
│
├── models/
│   ├── database.py             # Motor singleton + indexes
│   ├── mongo_logger.py         # sessions, turns, query_logs, agent_traces
│   ├── document.py             # DocumentRecord, DocumentChunk
│   └── user.py                 # UserDocument
│
├── auth/                       # JWT, Microsoft OAuth, password, RBAC
├── routers/auth.py             # /auth router
├── schemas/                    # Pydantic API contracts
├── cache/                      # Redis manager, session/history/LLM cache, limiter
├── embedding/                  # BGE-M3, E5 embedders
├── reranking/                  # BGE reranker
├── frontend/chat-companion/    # React web app
├── mobile/                     # Expo app
└── packages/shared/            # shared TS API/types/utils
```

---

## 4. Runtime Query Flow

### 4.1 `query_v3()` smart entrypoint

- Chạy `ComplexityRouter` trước mọi branch.
- `chitchat`: trả canned response, không gọi LLM/retrieval.
- `complex` + multi-source decomposition hợp lệ: chạy decomposed RAG và trả `mode=rag_v2_decomposed`.
- `simple` hoặc `agent_enabled=false`: fallback về classic `query()` và trả `mode=rag_v2`.
- Các complex còn lại: chạy `query_agent()`, nếu agent lỗi thì fallback classic RAG trừ khi caller yêu cầu `require_agent=True`.

### 4.2 Classic RAG flow

- Load history từ Mongo/Redis cache nếu có `session_id`.
- Route domain bằng `QueryRouter`, có route cache.
- Tier-3 Gemini classification chỉ chạy khi confidence < `0.55` và margin top-vs-second < `0.25`.
- Rewrite query bằng `QueryReflector`; nếu reflect fail dùng original query và deterministic entity fallback.
- `QueryReflector` có guard deterministic cho follow-up so sánh ngắn: các câu như
  "so với ngành của tôi" hoặc "so về học phí" được rewrite thành query standalone
  theo topic hiện tại/user turn gần nhất và cặp mã ngành từ current/history/profile.
- `CollectionSelector` map domain sang target collections; low confidence có fallback multi-collection.
- Metadata prefilter qua `build_collection_filters()` -> ES metadata search -> Qdrant `HasIdCondition`.
- Hybrid retrieval chạy Qdrant vector + ES keyword song song, merge cross-collection, rerank bằng BGE.
- Sau retrieval: validity filter, reference resolver, context formatting kèm metadata header, LLM generation.
- Optional: post-retrieval LLM cache, self-eval, Tavily fallback tùy settings.
- Tavily fallback is controlled by `TAVILY_FALLBACK_ENABLED`; when enabled,
  `RAGPipeline` initializes `SelfEvaluator` even if direct `SELF_EVAL_ENABLED`
  is false, because self-eval is the quality gate for web fallback.
- Tavily now has a pre-generation enrichment path shared by `rag_flow()` and
  `rag_flow_stream()`: dynamic/time-sensitive queries, no-source retrieval, or
  raw rerank fallback can fetch official web context before generation. This is
  gated by `WEB_FALLBACK_ON_DYNAMIC` for dynamic queries.
- Post-generation Tavily regeneration is only for explicit insufficiency:
  no-info answer text, no sources, or self-eval returning
  `should_web_search=true` with `answer_status` of `insufficient` or
  `stale_risk`. Plain `pass=false` self-eval is diagnostic.
- `SELF_EVAL_MIN_TOP_SCORE` defaults to `100.0` for local BGE raw-logit scores.
  The old `0.72` probability-style threshold incorrectly skipped self-eval for
  high raw logits such as `5.25`.
- `rag_flow_stream()` retrieval trước rồi stream token qua LLM; metadata SSE gửi cuối luồng.

### 4.3 Agent flow

- `query_agent()` gọi `ReActAgent.run()` và gom agent docs qua `ContextVar` để map vào API/UI trace.
- `ReActAgent` có 2 path:
  - Planner-executor cho comparison/multi-source: decompose, require every plan step to have a valid query/collection, execute retrieval steps song song, synthesize.
  - ReAct loop cho query khác: local tool-calling LLM bind tools, execute, loop đến synthesis/clarify/error; direct model answers are accepted only after at least one tool result.
- Planner/decomposer tránh auto-inject `user_context.major_code` vào comparison query để giảm bias.
- Tool results được trim cho context, nhưng trace/log đầy đủ lưu qua Mongo.

---

## 5. Collections & Retrieval Contracts

| Collection | Nội dung | Runtime metadata filter chính |
| --- | --- | --- |
| `ctdt` | Chương trình đào tạo, môn học, tín chỉ, học kỳ | `major_code`, `major_name` |
| `quydinh` | Quy định học vụ, học bổng, tốt nghiệp | `applicable_cohort` |
| `kehoach` | Kế hoạch học kỳ, lịch đăng ký, thông báo | `date_str` |
| `stsv` | Hỗ trợ sinh viên, biểu mẫu, thủ tục | không prefilter metadata chính |
| `test` | Collection hợp lệ cho upload/dev | tùy metadata upload |

Agent collection aliases:

| Agent key | Internal collection |
| --- | --- |
| `chuong_trinh` | `ctdt` |
| `quy_dinh` | `quydinh` |
| `ke_hoach` | `kehoach` |
| `ho_tro_sv` | `stsv` |

Retrieval facts:

- Qdrant store dùng named vectors `bge_m3` và `e5`, mỗi vector 1024 dim, cosine distance.
- Qdrant search gọi cả hai vectors rồi fuse theo weight BGE/E5.
- Elasticsearch `keyword_search()` hiện là `multi_match` trên `text^1.0`, `title^1.5`, `best_fields`, fuzziness `AUTO`, kèm optional filters.
- `MultiCollectionSearch` prefix result id dạng `{collection}/{id}` khi merge global results.
- Fusion dùng min-max normalize vector/keyword pool, rồi weighted sum.
- Default code settings: `vector_weight=0.8`, `keyword_weight=0.2`.
- Course-like queries (`môn`, `học phần`, mã học phần...) tăng keyword weight lên ít nhất `0.6`.
- `kehoach_recency_bonus` có thể cộng điểm nhỏ cho tài liệu gần đây.
- `ReferenceResolver` ưu tiên same-document Qdrant payload lookup theo `document_id` cho các tham chiếu kiểu `Điều/Khoản`, rồi insert chunks được resolve ngay sau chunk gốc; fallback semantic search bị post-filter cùng document/source.

Canonical major codes:

```text
BF1, BF2, BF-E12
CH1, CH2, CH-E11
EE1, EE2, EE-E18, EE-E8, EE-EP
EV1, EV2
HE1
IT1, IT2, IT-E6, IT-E7, IT-E10, IT-E15, IT-EP
ME1, ME2, ME-GU, ME-LUH, ME-NUT
MI1, MI2
MS1, MS2, MS3, MS5, MS-E3
TE-EP, TROY-IT, TX1
```

Major-code normalization accepts dash, Unicode-dash, spaced, and compact variants
such as `ME-GU`, `ME GU`, `ME–GU`, `MSE3`, `BFE12`, and `TROY IT`.
For CTĐT international/song ngữ documents, query reflection may add English
retrieval keywords and final RAG answers should translate English context into
Vietnamese when answering.

Cohort format runtime: `K` + 2-3 chữ số, ví dụ `K65`, `K70`.

---

## 6. Public API Contracts

### Chat

- `POST /chat`: classic response mapper, mode `auto|rag|agent`.
- `POST /chat/v3`: smart routing response shape cho UI trace/debug.
- `POST /api/chat/v3`: alias của `/chat/v3`.
- `POST /chat/stream`: SSE stream, gửi `session`, token chunks, `metadata`, `done`.
- `GET /chat/suggest`: suggested questions for mobile, based on query params or authenticated profile.
- If `Authorization: Bearer` is present, chat routes derive `user_id` and `user_context` from the JWT-backed DB user and ignore spoofable body identity fields.

`ChatRequest` fields chính:

```python
question: str
mode: "auto" | "rag" | "agent"
top_k: int = 5
history: list[ChatMessage]
session_id: str | None
user_context: UserContext | None
user_id: str | None
```

`ChatResponse`/v3 metadata có thể gồm:

```python
answer
retrieved_documents
target_collections
collection_scores
reflected_question
applied_filters
collection_results
mode, route, tools, tool_calls, iterations
agent_trace, agent_error
timings_ms
session_id
turn_id
routing_probabilities
reflection_prompt
llm_prompt
```

### Auth & RBAC

- Auth router được include prefix `/auth`.
- Routes: `GET /auth/login`, `GET /auth/callback`, `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `PATCH /auth/me`, `POST /auth/logout`, `POST /auth/admin/create`.
- `PATCH /auth/me` supports `major_code` in addition to profile fields used by chat context.
- Microsoft OAuth chỉ chấp nhận email domain `@sis.hust.edu.vn`.
- JWT có `sub`, `email`, `role`, `iat`, `exp`; role đọc lại từ DB khi login.
- Role DB: `student` mặc định, `admin` cho admin.
- Superadmin không phải DB role; xác định bằng `SUPERADMIN_USER_IDS`.
- Upload/admin endpoints dùng `require_admin`; tạo admin dùng superadmin check.

### Session, Metrics, Health, Retrieval

- `POST /session`, `GET /session/{session_id}`, `GET /sessions?user_id=...`, `GET /sessions/me`.
- `DELETE /session/{session_id}` and `PATCH /session/{session_id}` require JWT auth
  and only operate on sessions owned by the current user. Ownership accepts the
  canonical Mongo `_id` plus legacy aliases (`email`, `username`, `student_id`).
  Delete removes session metadata, turns, query logs, agent traces, and Redis
  history cache. Rename updates `title` without changing `updated_at`.
- `GET /sessions/me` merges the same owner aliases and deduplicates by
  `session_id`, newest first, so pre-auth-migration web sessions remain visible.
- `GET /health`, `POST /api/admin/reload-validity`.
- `GET /metrics/usage`, `GET /metrics/eval`.
- `POST /retrieval/search` là diagnostic endpoint cho raw retrieval.
- Mobile feature APIs:
  - `POST/GET/DELETE /bookmarks`, `GET/POST /bookmark-folders`.
  - `POST /feedback`.
  - `GET /lookup/ctdt/{major_code}`, `/lookup/regulations`, `/lookup/calendar`, `/lookup/compare`.
  - `GET /notifications`, `PUT /notifications/{id}/read`, `POST /notifications/subscribe`.

### Admin Document Pipeline

All `/admin/*` document endpoints yêu cầu admin role:

- `POST /admin/documents`: upload document, validate collection/converter.
- `GET /admin/documents`, `GET /admin/documents/{doc_id}`, `DELETE /admin/documents/{doc_id}`.
- `POST /admin/documents/{doc_id}/convert`, `/clean`, `/chunk`, `/index`, `/pipeline`.
- `POST /admin/documents/{doc_id}/rollback`.
- Review endpoints: `/markdown`, `/cleaned`, `/chunks`, `/chunk-strategies`, `/chunks/select`.
- Discovery endpoints: `GET /admin/converters`, `GET /admin/chunkers`.

`DocumentPipeline` supports PyMuPDF4LLM/Docling conversion, clean, chunk, embed/index to Mongo/Qdrant/ES, delete indexed data by `document_id`, and rollback by status.

---

## 7. Agent Tools

`LANGGRAPH_TOOLS` in `agent/lc_tools.py` currently contains exactly:

| Tool | Bound to LangGraph LLM | Purpose |
| --- | --- | --- |
| `rag_search` | yes | Search one logical collection |
| `web_search` | yes | Tavily/web fallback |
| `clarify_question` | yes | Ask user one clarification and stop turn |

`web_search` uses HUST official/extended domains plus authoritative education
domains only; general news sites are not in the default Tavily scope. The tool
uses `TAVILY_MAX_RESULTS` and `TAVILY_SEARCH_DEPTH` from settings.

Important: `execute_tool()` in `agent/tool_adapters.py` still supports `multi_rag_search`, `compare_cohorts`, and `compare_programs` for backward compatibility, tests, and direct callers. These are not currently in `LANGGRAPH_TOOLS`, so the ReAct LLM is not schema-bound directly to them. Comparison/multi-source work is handled primarily by the planner-executor path.

Tool adapter details:

- `COLLECTION_MAP` maps agent keys to internal collection names.
- `_rag_search` strips PII/student ids, maps major/cohort, uses raw query for ES and stripped query for vectors.
- `_RAG_CACHE` is a small FIFO in-process cache.
- Reranker access is protected by a lock because the tokenizer path is not thread-safe.
- `execute_retrieval_plan()` runs steps in a thread pool with a fresh `contextvars.copy_context().run` per task.

---

## 8. Web, Mobile, Shared Package

### Web app

- Located at `frontend/chat-companion`.
- Stack: React 18, Vite, TanStack Query, axios, shadcn/Radix UI, markdown renderer.
- Vite dev server config uses port `8080`.
- API base URL defaults to `http://localhost:8000` unless `VITE_API_URL` is set.
- Main routes include `/`, `/chat`, `/chat/:sessionId`, `/login`, `/register`, `/complete-profile`, `/trace`, `/retrieval`, `/admin`, `/admin/documents/:id`.
- `ChatContainer` supports `/chat/stream`, session history, metadata/debug panel, and route/session invalidation.
- Authenticated web chat/session requests attach the JWT from `localStorage.token`.
  The conversation sidebar supports search, date grouping, inline rename, hard
  delete, mobile sheet rendering, and desktop resizing persisted in
  `localStorage` key `sidebar:size`.
- Admin UI uses `services/adminApi.ts` for upload pipeline actions and polling.
- `AdminGuard` currently checks `localStorage.user.role === "admin"`.

### Mobile app

- Located at `mobile`.
- Stack: Expo, React Native, React Query, React Navigation, NativeWind, SecureStore, `react-native-sse`, `@rag/shared`.
- API base URL uses `EXPO_PUBLIC_API_BASE_URL`, then emulator/simulator defaults.
- Streaming uses `/chat/stream` with non-streaming `/chat/v3` fallback before the first token.
- Auth uses a single JWT access token in SecureStore; `401` clears SecureStore and auth state.
- Bottom tabs cover Chat, Lookup, Bookmarks, Notifications, and Profile. MMKV caches sessions, suggestions, and bookmarks for partial offline read access.
- In Expo Go, the mobile offline cache uses an in-memory fallback because `react-native-mmkv` requires NitroModules that are only available in a rebuilt native/dev-client app; native builds still use MMKV when available.

### Shared package

- Located at `packages/shared`.
- Exports API client, auth/chat/session/bookmark/feedback/lookup/notification helpers, shared types, stores, constants and normalization utilities.
- `UserPublic` is normalized with canonical `id` from backend `_id`.

---

## 9. Settings & ENV

Config source: `config/settings.py` using Pydantic BaseSettings and `src/RAG_v2/.env`.

Key settings families:

```env
GOOGLE_API_KEY=...
TAVILY_API_KEY=...
TAVILY_FALLBACK_ENABLED=false
TAVILY_SEARCH_DEPTH=basic
TAVILY_MAX_RESULTS=3
WEB_FALLBACK_ON_DYNAMIC=true
WEB_FALLBACK_ON_NO_INFO=true
TAVILY_CACHE_TTL_SECONDS=3600
TAVILY_CACHE_MAXSIZE=200
LM_STUDIO_BASE_URL=...
LLM_PROVIDER=gemini
EMBEDDING_PROVIDER=ensemble
RERANKER_PROVIDER=bge
AGENT_ENABLED=true
AGENT_MODEL=...
AGENT_SYNTHESIS_PROVIDER=gemini
CHAT_MODEL=...
QDRANT_HOST=localhost
QDRANT_PORT=6333
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=rag_chatbot
MONGODB_ENABLED=true
REDIS_ENABLED=false
RATE_LIMIT_ENABLED=true
SUPERADMIN_USER_IDS=...
UPLOAD_DIR=...
```

Do not hardcode provider/model/host values in code; use settings/env.

---

## 10. Conventions

- Python file names: `snake_case.py`.
- Classes: `PascalCase`.
- Pipeline entrypoints are async, but many retrieval/store calls are sync and are moved to threads by callers where needed.
- Loggers use `logger = logging.getLogger(__name__)`.
- Search result ids after cross-collection merge use `{collection}/{doc_id}`.
- Fallbacks are expected: agent error -> classic RAG, filter empty -> relaxed/no filter, reflection fail -> original query, retrieval empty -> broader search or web fallback when enabled.
- Chat history context budget is trimmed before prompt construction.
- `CLARIFY_SENTINEL` lives in `schemas/constants.py` and marks clarify-tool output.

---

## 11. Known Bugs & Cautions

- `/retrieval/search` tries `pipeline.service`, while `RAGPipeline` exposes `self._retrieval_service`; this can force a cold `RetrievalService.from_settings()` load instead of reusing the warmed service.
- Auto-crawler reuse in `api/main.py` also checks `pipe.retrieval_service`, but `RAGPipeline` currently has no public `retrieval_service` attribute.
- `rag_flow_stream()` initializes stream metadata trace, but does not pass `trace_out` into `MultiCollectionSearch.search()`, so `applied_filters`/`collection_results` may be empty in stream metadata.
- `DocumentPipeline.chunk()` writes a debug chunk dump to a hard-coded absolute path under `/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/data/quydinh/admin_upload`.
- Redis-backed cache/session/rate-limit behavior is inactive when `redis_enabled=false`, even if related feature flags/defaults are true.
- OAuth redirect and dev ports are inconsistent: web Vite config uses `8080`, while auth callback redirect code uses `http://localhost:5173`.
- Elasticsearch keyword search does not currently implement custom course-field boosting beyond `text^1.0`, `title^1.5`, fuzziness and filters. Keep course-query boosting documented at the hybrid fusion layer, not as ES query behavior.

---

## 12. Files Usually Ignored For Architecture Review

- Tests unless verifying current behavior.
- `node_modules`, `.venv`, caches, build outputs.
- `volumes/`, upload folders, generated chunks, raw data artifacts.
- Eval datasets/reports unless the change affects eval behavior or public metrics.
