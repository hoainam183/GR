# RAG v2 Architecture

Source-verified: 2026-05-20 from source files, MODULE.md files, PROJECT_MEMORY.md, and GitNexus index `GR` (11919 symbols, 20221 relationships, 300 execution flows).

## 1. System Goal

`RAG_v2` is a HUST academic assistant. It answers student questions over internal academic sources and optionally uses official web search for fresh plan/deadline questions.

Primary knowledge collections:

| Collection | Meaning |
| --- | --- |
| `ctdt` | Curriculum, majors, course plans, credits, prerequisites. |
| `quydinh` | Regulations, scholarships, graduation rules, foreign-language rules. |
| `kehoach` | Academic plans, registration schedules, notices, deadlines. |
| `stsv` | Student-support handbook, forms, procedures, support services. |
| `test` | Upload/dev collection. |

The system includes:

- FastAPI backend.
- Smart RAG pipeline.
- LangGraph agent for complex/multi-source questions.
- Qdrant + Elasticsearch hybrid retrieval.
- MongoDB persistence.
- Optional Redis cache/session/rate limit.
- Admin document upload/indexing pipeline.
- React web app.
- Expo mobile app.
- Shared TypeScript package.
- Offline evaluation/regression tooling.

## 2. Top-Level Module Map

```text
RAG_v2/
  api/               FastAPI app, routes, response mapping, middleware.
  auth/              JWT, OAuth, password, RBAC helpers.
  routers/           Auth HTTP router mounted under /auth.
  schemas/           Pydantic request/response contracts.
  pipeline/          RAGPipeline, RAG flows, DocumentPipeline.
  query/             Complexity routing, domain routing, reflection, decomposer.
  retrieval/         Qdrant, ES, hybrid/multi-collection search, filters, resolver.
  embedding/         BGE-M3 and E5 embedders.
  reranking/         BGE cross-encoder reranker.
  llm/               DeepSeek/Gemini/LM Studio wrappers, prompts, self-eval.
  agent/             LangGraph agent, tools, planner-executor.
  models/            Mongo models, Motor client, MongoLogger.
  cache/             Optional Redis sessions, history, LLM cache, rate limits.
  chunking/          Offline/admin chunkers and metadata enrichment.
  document_loader/   PDF -> Markdown conversion and cleanup.
  scripts/           Crawlers, indexers, metadata maintenance.
  data/              Local corpus, chunks, metadata, lineage registry.
  tools/             Tavily web-search adapter.
  utils/             Storage, tracing, chunk indexing policy, helpers.
  evaluation/        Current/historical eval framework.
  eval/              Legacy/specialized eval assets and RAGAS tooling.
  frontend/          React/Vite web app.
  mobile/            Expo/React Native app.
  packages/          Shared TypeScript package `@rag/shared`.
  backend/           Thin legacy wrapper around `api.main.app`.
  tests/             Pytest regression/unit/contract tests.
```

Each major directory above has a `MODULE.md` with module-specific contracts and checks.

## 3. Runtime Stack

| Layer | Technology / source |
| --- | --- |
| API | FastAPI in `api/main.py` |
| Chat orchestration | `pipeline/rag_pipeline.py`, `pipeline/flows.py` |
| Agent | LangGraph + LangChain StructuredTool in `agent/` |
| Query routing | `query/complexity_router.py`, `query/router.py`, `query/domain_classifier.py` |
| Query rewrite | `query/reflection.py` |
| Vector store | Qdrant named vectors `bge_m3` and `e5` |
| Keyword store | Elasticsearch indexes named by collection |
| Embeddings | BGE-M3 and multilingual E5 |
| Reranker | BGE reranker cross-encoder |
| Main LLM | DeepSeek `deepseek-v4-flash` through OpenAI-compatible endpoint by default |
| Agent tool LLM | LM Studio/OpenAI-compatible local model |
| Agent synthesis | Gemini, Ollama, or LM Studio depending on settings |
| Persistence | MongoDB through Motor and `MongoLogger` |
| Cache | Redis optional |
| Web | React + Vite |
| Mobile | Expo/React Native |
| Shared TS | `packages/shared` |

Local infrastructure defaults:

| Service | Port |
| --- | --- |
| FastAPI | `8000` |
| Web Vite | `8080` |
| Qdrant | `6333` |
| Elasticsearch | `9200` |
| MongoDB | `27017` |
| Redis | `6379` |

## 4. Backend App Lifecycle

Entrypoint:

```text
backend/main.py
  -> api.main.app
  -> create_app()
  -> lifespan()
```

Startup sequence in `api/main.py:lifespan()`:

1. Load `.env` from the RAG_v2 root.
2. Build `Settings`.
3. Initialize `MongoLogger` when `mongodb_enabled`.
4. Initialize Redis manager/session/cache/history/rate limiter when Redis flags are enabled.
5. Store settings and runtime resources in `app.state`.
6. Build one `RAGPipeline` in an executor because model loading is heavy.
7. Create Mongo indexes.
8. Warm up the local agent LLM if available.
9. Optionally schedule `scripts.auto_crawler` if `crawler_enabled`.

Shutdown:

- stop APScheduler crawler if started
- close Redis manager if initialized

Important singleton contract:

```text
RAGPipeline creates one RetrievalService.
Agent tools receive that same service via inject_from_retrieval_service().
```

## 5. Public HTTP Surface

Routers registered by `create_app()`:

| Route | File | Purpose |
| --- | --- | --- |
| `POST /chat` | `api/routes/chat.py` | Non-streaming chat, mapped to `ChatResponse`. |
| `POST /chat/v3` | `api/routes/chat.py` | Smart response with trace/debug metadata. |
| `POST /api/chat/v3` | `api/routes/chat.py` | Alias of `/chat/v3`. |
| `POST /chat/stream` | `api/routes/chat.py` | SSE streaming endpoint. |
| `GET /chat/suggest` | `api/routes/chat.py` | Suggested questions. |
| `GET /health` | `api/routes/health.py` | Backend health. |
| `POST /api/admin/reload-validity` | `api/routes/health.py` | Reload validity registry. |
| `POST /retrieval/search` | `api/routes/retrieval.py` | Raw retrieval diagnostic endpoint. |
| `POST /session` | `api/routes/session.py` | Create session. |
| `GET /session/{session_id}` | `api/routes/session.py` | Session metadata and turns. |
| `GET /sessions` | `api/routes/session.py` | Intended session list route. |
| `GET /sessions/me` | `api/routes/session.py` | Intended authenticated session list route. |
| `PATCH /session/{session_id}` | `api/routes/session.py` | Rename owned session. |
| `DELETE /session/{session_id}` | `api/routes/session.py` | Hard delete owned session. |
| `GET /metrics/usage` | `api/routes/metrics.py` | Usage metrics. |
| `GET /metrics/eval` | `api/routes/metrics.py` | Eval dashboard payload. |
| `/auth/*` | `routers/auth.py` | OAuth, manual auth, profile, admin create. |
| `/admin/documents*` | `api/routes/upload.py` | Admin document upload/review/index pipeline. |
| `/bookmarks*` | `api/routes/bookmark.py` | Saved answers/folders. |
| `/feedback*` | `api/routes/feedback.py` | Answer ratings/comments. |
| `/lookup/*` | `api/routes/lookup.py` | Mobile quick lookup. |
| `/notifications*` | `api/routes/notification.py` | User notification inbox/subscriptions. |
| `/admin/notifications` | `api/routes/notification_admin.py` | Admin notification creation. |

Auth:

- `/auth` routes are mounted by `api/main.py` from `routers/auth.py`.
- Admin upload routes use `auth.rbac.require_admin`.
- Superadmin is configured by `SUPERADMIN_USER_IDS`, not a DB role.

## 6. Chat Request And Response Contract

`schemas/chat.py:ChatRequest` includes:

```python
question: str
mode: "auto" | "rag" | "agent"
top_k: int
history: list[HistoryMessage] | None
session_id: str | None
user_context: UserContext | None
user_id: str | None
```

If a valid Bearer token exists, chat/session routes derive identity and profile from the DB user. Body-supplied `user_id` and `user_context` are legacy/dev inputs and should not override authenticated identity.

Response fields can include:

- `answer`
- `retrieved_documents`
- `session_id`
- `turn_id`
- `mode`
- `route`
- `target_collections`
- `collection_scores`
- `reflected_question`
- `routing_probabilities`
- `applied_filters`
- `collection_results`
- `timings_ms`
- `request_trace`
- `agent_trace`
- `tools_used`
- `tool_calls`
- `iterations`

`api/response_mapper.py` normalizes pipeline/agent outputs into the API schema.

Streaming event contract:

```text
{"type":"session","session_id":"..."}
{"type":"token","delta":"..."}
{"type":"metadata", ...}
{"type":"done"}
```

## 7. Query Processing

High-level flow:

```text
raw question + history + profile
  -> ComplexityRouter
  -> QueryRouter / DomainClassifier
  -> optional Tier-3 LLM domain classification
  -> CollectionSelector
  -> QueryReflector
  -> metadata filters + retrieval query
```

`ComplexityRouter` returns:

- `chitchat`
- `simple`
- `complex`

Complex subtypes:

- `comparison`
- `multi_source`
- `personal_check`
- `general`

`DomainClassifier` is two-stage:

1. intent: `chitchat`, `rag`, `tool_search`
2. RAG domains: `ctdt`, `quydinh`, `kehoach`, `stsv`

`QueryRouter` does a second pass with history only for short, low-confidence follow-up queries. Long self-contained queries should not be biased by old session domains.

`QueryReflector`:

- strips PII/noise
- merges profile context only when appropriate
- rewrites to standalone query with LLM
- blocks hallucinated major/cohort/semester injection
- deterministically handles short comparison follow-ups
- extracts entities through regex and metadata helpers

Profile bleed rule:

```text
Generic/latest/freshness queries must not inherit major, cohort, or semester from profile/history unless the current query asks for profile-dependent context.
```

## 8. RAG Pipeline

Primary class: `pipeline/rag_pipeline.py:RAGPipeline`.

Smart entrypoint:

```text
query_v3()
  -> chitchat: direct/canned chitchat response
  -> simple: classic query()
  -> complex + multi_source/comparison: decomposed RAG
  -> complex general/personal_check: agent, with classic RAG fallback
```

Classic RAG flow in `pipeline/flows.py:rag_flow()`:

```text
history trim
  -> query-only cache when safe
  -> route/select/reflect/entities
  -> metadata filters
  -> BGE/E5 embed
  -> MultiCollectionSearch
  -> retry relaxed strategies if empty
  -> dedup
  -> BGE rerank
  -> ValidityFilter
  -> ReferenceResolver
  -> context formatting
  -> LLM generate
  -> cache/log metadata
  -> optional self-eval/Tavily fallback
```

Important behaviors:

- List/enumeration queries can request larger context.
- Kehoach freshness/dynamic routing can lock to `kehoach`.
- Course-like queries bias retrieval fusion toward keyword matching.
- Context-size errors can trigger reduced-context retry.
- Streaming retrieves first, then streams tokens; it does not run post-generation self-eval/Tavily.

## 9. Retrieval

Runtime wrapper: `retrieval/service.py:RetrievalService`.

`RetrievalService.from_settings()` builds:

- BGE-M3 embedder
- E5 embedder
- `MultiCollectionSearch`
- optional reranker
- optional Tavily tool

Qdrant:

- one collection per domain
- named vectors `bge_m3` and `e5`
- 1024 dimensions each
- cosine distance

Elasticsearch:

- index names match collection names
- keyword search over text/title-style fields
- metadata-only search resolves filtered ids for Qdrant conditions

Multi-collection search:

```text
build metadata filters
  -> resolve ES metadata fallback chain
  -> parallel Qdrant vector + ES keyword search per collection
  -> global vector pool
  -> global keyword pool
  -> min-max score normalization
  -> weighted fusion
  -> kehoach recency bonus
  -> dedup
  -> top-k candidates
```

Default fusion settings in source:

- `vector_weight=0.8`
- `keyword_weight=0.2`

Metadata filter behavior:

| Collection | Filter logic |
| --- | --- |
| `ctdt` | major code/name with generic fallback |
| `quydinh` | cohort/major applicability with null fallback |
| `kehoach` | real posting-date filters or freshness sort |
| `stsv` | no default prefilter |

Post-retrieval:

- `ValidityFilter` drops superseded docs from `data/document_lineage.json` where safe.
- `ReferenceResolver` resolves same-document legal references such as `Dieu` and `Khoan`.

## 10. Agent

Primary class: `agent/react_agent.py:ReActAgent`.

The agent is used for complex queries when `agent_enabled=True`.

Planner-executor path:

```text
comparison/multi_source
  -> decompose
  -> planner JSON
  -> validate steps
  -> parallel retrieval executor
  -> synthesis LLM
```

ReAct path:

```text
general complex
  -> local tool-calling LLM
  -> tools
  -> loop until answer/clarify/error/max
  -> synthesis fallback when needed
```

LLM-bound tools:

| Tool | Purpose |
| --- | --- |
| `rag_search` | Search one logical collection. |
| `web_search` | Tavily web search for fresh/missing data. |
| `clarify_question` | Ask one clarification and stop. |

Adapter-only legacy tools:

- `multi_rag_search`
- `compare_cohorts`
- `compare_programs`

Agent collection aliases:

| Agent key | Internal collection |
| --- | --- |
| `chuong_trinh` | `ctdt` |
| `quy_dinh` | `quydinh` |
| `ke_hoach` | `kehoach` |
| `ho_tro_sv` | `stsv` |

Thread-safety:

- per-request docs are stored in a ContextVar
- agent RAG cache is lock-protected
- reranker calls are serialized by `_RERANKER_LOCK`

## 11. Admin Document Pipeline

HTTP owner: `api/routes/upload.py`.

Pipeline owner: `pipeline/document_pipeline.py:DocumentPipeline`.

Flow:

```text
admin upload PDF
  -> LocalStorage original file
  -> Mongo documents status=uploaded
  -> convert_pdf()
  -> markdown
  -> clean()
  -> cleaned markdown
  -> chunk()
  -> Mongo document_chunks
  -> approve/select chunks
  -> embed_and_index()
  -> Qdrant + Elasticsearch + Mongo indexed counts
```

Status lifecycle:

```text
uploaded -> converting -> converted -> cleaning -> cleaned
-> chunking -> chunked -> embedding -> indexed
```

Rollback can step back from indexed/chunked/cleaned/converted states and delete indexed Qdrant/ES data by `document_id`.

Indexing policy:

```text
utils.chunk_indexing.is_indexable_chunk()
  rejects parent/header chunks
```

Parent/header chunks can remain in Mongo for review but should not consume retrieval slots.

## 12. Persistence And Cache

Mongo access styles:

- `models/database.py`: async Motor singleton and FastAPI dependency.
- `models/mongo_logger.py`: sync durable logging for chat/session traces.

Core Mongo collections:

- `users`
- `sessions`
- `turns`
- `query_logs`
- `agent_traces`
- `documents`
- `document_chunks`
- `bookmarks`
- `bookmark_folders`
- `feedback`
- `notifications`
- `notification_subscriptions`

Redis is optional and controlled by:

- `redis_enabled`
- `use_redis_session`
- `use_redis_cache`
- `use_redis_history`
- `rate_limit_enabled`

Redis keys:

- `session:{sid}`
- `user_sessions:{uid}`
- `history:{sid}`
- `llm_cache:{sha}`
- `llm_cache:q:{sha}`
- `doc_cache_tag:{did}`
- `rate:min:{id}`
- `rate:day:{id}`

Redis behavior is fail-soft. If Redis fails, the backend should use Mongo or bypass the cache/rate limit instead of crashing.

## 13. Auth And User Context

Auth modules:

- `auth/jwt_handler.py`
- `auth/microsoft.py`
- `auth/password.py`
- `auth/rbac.py`
- `routers/auth.py`
- `schemas/user.py`
- `models/user.py`

Supported auth:

1. Microsoft OAuth under `/auth/login` and `/auth/callback`.
2. Manual register/login.
3. JWT-backed `/auth/me` and profile update.
4. Superadmin-created admin accounts.

Chat user context fields:

```python
student_id
cohort
major
major_code
full_name
```

These feed query reflection, entity fallback, generation profile notes, and UI identity.

## 14. Data And Ingestion

Curated data lives under `data/`:

```text
data/
  document_lineage.json
  ctdt/
  kehoach/
  quydinh/
  stsv/
```

Offline ingestion paths:

- `scripts/index_ctdt` style functionality is represented by domain-specific index scripts and chunk data.
- `scripts/index_kehoach.py`
- `scripts/index_quydinh.py`
- `scripts/index_stsv.py`
- `scripts/index_to_es.py`
- `scripts/auto_crawler.py`

Auto crawler flow:

```text
crawl official source
  -> save JSON
  -> chunk
  -> embed
  -> index Qdrant + ES
  -> retention cleanup
```

`data/document_lineage.json` is the source for superseded/active document filtering.

## 15. Tavily Web Fallback

Owner: `tools/tavily_search.py`.

Tavily is optional and created once in `RetrievalService` when key validation passes.

Non-streaming classic RAG can use Tavily in two stages:

1. Pre-generation enrichment:
   - no sources
   - dynamic/freshness query
   - low retrieval confidence

2. Post-generation fallback:
   - no-info answer
   - no sources
   - self-eval requests web with insufficient/stale-risk status

Both stages require:

```text
tavily_fallback_enabled=True
valid tavily_api_key
```

Agent web search uses HUST official/extended domains and authoritative education domains.

## 16. Web App

Path: `frontend/chat-companion`.

Stack:

- React 18
- Vite
- React Router
- TanStack Query
- shadcn/Radix UI
- Axios and Fetch streaming
- Tailwind CSS

Routes:

- `/`
- `/chat`
- `/chat/:sessionId`
- `/login`
- `/register`
- `/complete-profile`
- `/trace`
- `/retrieval`
- `/eval`
- `/admin`
- `/admin/documents/:id`
- `/bookmarks`
- `/notifications`

Important web files:

- `src/services/chatApi.ts`
- `src/services/adminApi.ts`
- `src/components/chat/ChatContainer.tsx`
- `src/components/sidebar/ConversationSidebar.tsx`
- `src/components/trace/PipelineTrace.tsx`
- `src/pages/DocumentReview.tsx`

## 17. Mobile App

Path: `mobile`.

Stack:

- Expo SDK 54
- React Native
- React Navigation
- TanStack Query
- Zustand
- SecureStore
- MMKV when native runtime supports it
- `react-native-sse`
- `@rag/shared`

Main tabs:

- Chat
- Lookup
- Bookmarks
- Notifications
- Profile

Streaming uses `/chat/stream`; non-streaming fallback uses `/chat/v3`.

Mobile uses one access token. There is no backend refresh-token endpoint as of this snapshot.

## 18. Shared TypeScript Package

Path: `packages/shared`.

Exports:

- Axios API client factory
- chat/auth/session/bookmark/feedback/lookup/notification API helpers
- chat/auth/mobile types
- Zustand auth/chat store factories
- response normalization utilities
- API path constants

Keep `packages/shared/src/utils/constants.ts` synchronized with FastAPI route paths.

## 19. Evaluation

Current evaluation framework: `evaluation/`.

Two suites:

- Current policy eval: production retrieval against currently indexed documents.
- Historical email eval: conversation/advisory behavior over historical context.

Important commands:

```bash
python -m evaluation.two_layer_eval current --persist
python -m evaluation.two_layer_eval historical --judge --persist
python evaluation/evaluate_current_pipeline.py --golden eval/golden_dataset.json --labels evaluation/search_strategy_labels.jsonl --k 10
```

RAGAS and legacy eval tooling live under `eval/`.

API dashboard:

```text
GET /metrics/eval?suite=current_policy
GET /metrics/eval?suite=historical_email
```

Frontend dashboard:

```text
/eval
```

## 20. Settings

Central settings file: `config/settings.py`.

Important groups:

- providers and API keys
- agent model/synthesis
- Qdrant/Elasticsearch/Mongo/Redis hosts
- collections
- chat model
- retrieval top-k/pools/weights/context budgets
- reranker thresholds
- Tavily fallback/cache
- reflection/domain routing
- crawler schedule/retention
- Redis/session/cache/history/rate-limit flags
- superadmin/upload/CORS/API host and port

Do not hard-code provider/model/host values when a setting exists.

## 21. Known Cautions

1. `api/routes/retrieval.py` reads `getattr(pipeline, "service", None)`, while `RAGPipeline` stores the shared retrieval service as `_retrieval_service`. Without a public property, `/retrieval/search` can cold-load a new `RetrievalService`.

2. `api/main.py` auto-crawler reuse checks `hasattr(pipe, "retrieval_service")`, but `RAGPipeline` currently does not expose that property.

3. `api/routes/session.py` intends `/sessions` and `/sessions/me` by combining router prefix `/session` with route paths `"s"` and `"s/me"`. Keep route behavior covered by tests because this shape is easy to break.

4. `DocumentPipeline.chunk()` has had debug/output behavior under `data/quydinh/admin_upload`; verify before relying on this path in production.

5. Redis features are inactive unless both `redis_enabled` and the relevant per-feature flags are true.

6. Agent ReAct LLM is schema-bound only to `rag_search`, `web_search`, and `clarify_question`. Do not assume legacy comparison tools are visible to the LLM.

7. Streaming chat does not run post-generation self-eval/Tavily fallback.

8. Root `README.md` may lag behind `PROJECT_MEMORY.md`, `MODULE.md`, and this file for current runtime behavior.

## 22. High-Level Mental Model

```text
Client asks question
  -> FastAPI resolves auth/session/user_context
  -> RAGPipeline.query_v3 smart-routes
     -> chitchat: direct response
     -> simple: classic RAG
     -> multi-source/comparison: decomposed RAG
     -> complex: LangGraph agent with RAG fallback
  -> RetrievalService searches Qdrant + Elasticsearch
  -> BGE reranker selects grounded context
  -> Validity/reference post-processing
  -> DeepSeek/agent synthesis answers
  -> Mongo/Redis persist logs, sessions, caches
  -> API maps response for web/mobile trace/debug UI
```
