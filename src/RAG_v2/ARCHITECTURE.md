# RAG v2 Architecture

Source-verified: 2026-06-02 from source files, `MODULE.md` files, `PROJECT_MEMORY.md`, and GitNexus index `GR` (16,920 nodes, 28,737 relationships, 300 execution flows).

## 1. System Goal

`RAG_v2` is a HUST academic assistant. It answers student questions over internal academic sources and can optionally use official web search for fresh plan/deadline questions.

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
- LangGraph Planner-Executor agent for complex/multi-source questions.
- Qdrant + Elasticsearch hybrid retrieval.
- MongoDB persistence.
- Optional Redis session/cache/history/rate-limit layer.
- Admin document upload/review/indexing pipeline.
- Admin crawler staging/review/indexing workflow.
- React/Vite web app.
- Expo/React Native mobile app.
- Shared TypeScript package.
- Offline evaluation/regression tooling.

## 2. Top-Level Module Map

```text
RAG_v2/
  api/               FastAPI app, routes, response mapping, middleware.
  auth/              JWT, refresh-token, password, OAuth, RBAC helpers.
  routers/           Auth HTTP router mounted under /auth.
  schemas/           Pydantic request/response contracts.
  pipeline/          RAGPipeline, RAG flows, DocumentPipeline.
  query/             Complexity routing, domain routing, reflection, decomposition.
  retrieval/         Qdrant, ES, hybrid/multi-collection search, filters, resolver.
  embedding/         BGE-M3 and multilingual E5 embedders.
  reranking/         BGE cross-encoder reranker.
  llm/               DeepSeek/Gemini/LM Studio wrappers, prompts, self-eval.
  agent/             LangGraph Planner-Executor agent and retrieval/web adapters.
  models/            Mongo models, Motor client, MongoLogger, system config.
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
| Agent | LangGraph Planner-Executor in `agent/react_agent.py` |
| Query routing | `query/complexity_router.py`, `query/router.py`, `query/domain_classifier.py` |
| Query rewrite | `query/reflection.py` |
| Vector store | Qdrant named vectors `bge_m3` and `e5` |
| Keyword store | Elasticsearch indexes named by collection |
| Embeddings | BGE-M3 and multilingual E5 |
| Reranker | BGE reranker cross-encoder |
| Main LLM | DeepSeek `deepseek-v4-flash` by default |
| Agent planner/synthesis | Gemini by default, with Ollama or LM Studio/OpenAI-compatible fallback |
| Persistence | MongoDB through Motor and `MongoLogger` |
| Cache | Redis optional/fail-soft |
| Web | React + Vite |
| Mobile | Expo/React Native |
| Shared TS | `packages/shared` |

Important default settings in `config/settings.py`:

| Setting | Default |
| --- | --- |
| `llm_provider` | `deepseek` |
| `chat_model` | `deepseek-v4-flash` |
| `agent_enabled` | `True` |
| `agent_model` | `qwen2.5-7b-instruct` |
| `agent_synthesis_provider` | `gemini` |
| `agent_synthesis_model` | `gemini-3.1-flash-lite` |
| `tavily_fallback_enabled` | `False` |
| `redis_enabled` | `True` |
| `crawler_enabled` | `True` |

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
3. Merge persisted admin LLM overrides from Mongo `system_config/llm_config` when available.
4. Require `google_api_key` because Gemini-backed components may need it.
5. Initialize `MongoLogger` when `mongodb_enabled`.
6. Initialize Redis manager/session/cache/history/rate limiter when Redis flags are enabled.
7. Store settings and runtime resources in `app.state`.
8. Build one `RAGPipeline` in an executor because model loading is heavy.
9. Create Mongo indexes.
10. Check Mongo version for admin stats feature gating.
11. Warm up the agent LLM if available.
12. Optionally schedule `scripts.auto_crawler` if `crawler_enabled`.

Shutdown:

- stop APScheduler crawler if started
- close Redis manager if initialized

Important singleton contract:

```text
RAGPipeline creates one RetrievalService.
Agent adapters receive that same service through inject_from_retrieval_service().
```

Current caveat: `RAGPipeline` stores the service as `_retrieval_service`; there is no public `service` or `retrieval_service` property in source.

## 5. Public HTTP Surface

Routers registered by `create_app()`:

| Route | File | Purpose |
| --- | --- | --- |
| `GET /` | `api/main.py` | Basic service status. |
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
| `GET /sessions` | `api/routes/session.py` | Intended session list route from prefix `/session` + path `s`. |
| `GET /sessions/me` | `api/routes/session.py` | Intended authenticated session list route from prefix `/session` + path `s/me`. |
| `PATCH /session/{session_id}` | `api/routes/session.py` | Rename owned session. |
| `DELETE /session/{session_id}` | `api/routes/session.py` | Hard delete owned session. |
| `GET /metrics/usage` | `api/routes/metrics.py` | Usage metrics. |
| `GET /metrics/eval` | `api/routes/metrics.py` | Eval dashboard payload. |
| `/auth/*` | `routers/auth.py` | OAuth, manual auth, refresh, profile, admin create. |
| `/admin/documents*` | `api/routes/upload.py` | Admin document upload/review/index pipeline. |
| `/admin/stats/*` | `api/routes/admin_stats.py` | Admin overview/users/query/agent/feedback/system stats. |
| `/admin/users/{user_id}/status` | `api/routes/admin_stats.py` | Admin user activation toggle. |
| `/admin/crawler/*` | `api/routes/admin_stats.py` | Manual crawl, staged chunk review, crawler indexing. |
| `/admin/config*` | `api/routes/admin_stats.py` | Runtime toggles, LLM config, API key/env config. |
| `/admin/notifications*` | `api/routes/notification_admin.py` | Admin notification creation/broadcast. |
| `/bookmarks*` | `api/routes/bookmark.py` | Saved answers/folders. |
| `/bookmark-folders*` | `api/routes/bookmark.py` | Bookmark folders. |
| `/feedback*` | `api/routes/feedback.py` | Answer ratings/comments/stats. |
| `/lookup/*` | `api/routes/lookup.py` | Mobile quick lookup. |
| `/notifications*` | `api/routes/notification.py` | User notification inbox/subscriptions. |

Auth:

- `/auth` routes are mounted by `api/main.py` from `routers/auth.py`.
- Admin upload/stats/config/crawler routes use admin/superadmin guards where required.
- Superadmin is configured by `SUPERADMIN_USER_IDS`, not a DB role alone.

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

Mode behavior:

- `auto`: `RAGPipeline.query_v3()`.
- `rag`: force classic RAG through `RAGPipeline.query()`.
- `agent`: force agent path where supported. `/chat` returns 503 if agent is disabled; `/chat/v3` returns a RAG fallback payload with `agent_error`.

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
- `context_trace`
- `rerank_trace`
- `answer_quality_gate`
- `fusion_weights`
- `timings_ms`
- `agent_trace`
- `tools_used`
- `tool_calls`
- `iterations`
- `error` / `agent_error`

`api/response_mapper.py` normalizes pipeline/agent outputs into the API schema.

Streaming event contract:

```text
{"type":"session","session_id":"..."}
{"type":"token","delta":"..."}
{"type":"metadata", ...}
{"type":"error","error":"..."}
{"type":"done"}
```

## 7. Query Processing

High-level flow for classic RAG:

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

Current complex subtypes:

- `comparison`
- `multi_source`
- `general`

The old `personal_check` subtype is intentionally removed. Personal-reference eligibility/graduation wording routes as `multi_source`, so it reaches the Planner-Executor when the agent is enabled.

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

Construction builds:

- `Settings`
- one `RetrievalService.from_settings(settings)`
- BGE/E5/searcher/reranker/Tavily aliases from that service
- `QueryRouter`
- `QueryReflector`
- `QueryDecomposer`
- `ComplexityRouter`
- chat LLM through `llm.create_llm()`
- optional `SelfEvaluator`
- optional `ReActAgent`
- `ValidityFilter`
- `ReferenceResolver`
- runtime LLM reload lock/cache state

Smart entrypoint:

```text
query_v3()
  -> chitchat: local canned handler, no retrieval
  -> simple: classic query()
  -> complex: query_agent()
     -> comparison/multi_source: agent decompose -> planner -> executor -> synthesize
     -> general/missing subtype: agent planner -> executor -> synthesize
     -> fallback to classic RAG when agent is disabled/errors unless require_agent=True
```

Typical returned modes:

- `chitchat`
- `rag_v2`
- `agent`
- `rag_v2_fallback`

`_query_decomposed()` still exists as a legacy helper, but `query_v3()` no longer bypasses the agent for multi-source complex questions.

Classic RAG flow in `pipeline/flows.py:rag_flow()`:

```text
history trim
  -> query-only cache when safe
  -> route/select/reflect/entities
  -> metadata filters
  -> BGE/E5 embed
  -> MultiCollectionSearch
  -> retry relaxed strategies if empty
  -> sibling expansion before rerank when enabled
  -> BGE rerank with fallback to original question/raw fusion if needed
  -> HyDE fallback when reranked recall is poor
  -> ValidityFilter
  -> ReferenceResolver
  -> score-cliff pruning
  -> parent context expansion
  -> optional pre-generation Tavily enrichment
  -> context formatting
  -> LLM generate
  -> optional self-eval / local retry / Tavily fallback
  -> cache/log metadata
```

Important behaviors:

- List/enumeration queries can request larger context.
- Kehoach freshness/dynamic routing can lock to `kehoach`.
- Course-like queries bias retrieval fusion toward keyword matching.
- Reranker calls receive configured thresholds and `reranker_min_top_k`.
- Context-size errors can trigger reduced-context retry.
- Cache writes are restricted to stable local answers: answered status, no no-info/no-source/self-eval-failed markers, no dynamic/stale-risk signal, and no web fallback.
- Streaming runs retrieval first, can do pre-generation web enrichment, then streams tokens; it intentionally avoids post-generation self-eval/Tavily.

Runtime LLM reload:

- `prepare_llm_config_reload()` builds replacement chat LLM, reflector, decomposer, self-evaluator, agent, and Tavily references before Mongo persistence.
- `commit_llm_config_reload()` hot-swaps the prepared runtime under a lock, clears route cache, updates the shared retrieval service settings/Tavily, and reinjects the service into agent adapters.

## 9. Retrieval

Runtime wrapper: `retrieval/service.py:RetrievalService`.

`RetrievalService.from_settings()` builds:

- BGE-M3 embedder
- E5 embedder
- `MultiCollectionSearch`
- optional reranker
- optional Tavily tool
- in-process raw search result cache

Qdrant:

- one collection per domain
- named vectors `bge_m3` and `e5`
- 1024 dimensions each
- cosine distance

Elasticsearch:

- index names match collection names
- keyword search over text/title-style fields
- metadata-only search resolves filtered ids for Qdrant `HasIdCondition`
- fallback field resolution handles ID mismatches where possible

Multi-collection search:

```text
build collection metadata filters
  -> resolve ES metadata fallback chain
  -> translate matching ids into Qdrant/ES filters
  -> parallel Qdrant vector + ES keyword search per collection
  -> global vector pool
  -> global keyword pool
  -> min-max linear fusion or RRF fusion
  -> kehoach recency bonus
  -> text-level dedup
  -> top-k candidates
```

Default retrieval settings in source:

| Setting | Default |
| --- | --- |
| `collections` | `["stsv", "quydinh", "kehoach", "ctdt"]` |
| `top_k` | `5` |
| `vector_top_k` | `50` |
| `keyword_top_k` | `50` |
| `raw_candidate_multiplier` | `4.0` |
| `raw_candidate_min` | `20` |
| `vector_weight` | `0.8` |
| `keyword_weight` | `0.2` |
| `parent_context_enabled` | `True` |

Metadata filter behavior:

| Collection | Filter logic |
| --- | --- |
| `ctdt` | Major code/name with generic fallback. |
| `quydinh` | Cohort/major applicability with null fallback. |
| `kehoach` | Month/year/freshness filters or date-desc strategy. |
| `stsv` | No default prefilter. |

Post-retrieval:

- `ValidityFilter` drops superseded docs from `data/document_lineage.json` where safe.
- `ReferenceResolver` resolves same-document legal references such as `Dieu` and `Khoan`.
- Parent context expansion can fetch parent chunks from Qdrant after rerank.

## 10. Agent

Primary class: `agent/react_agent.py:ReActAgent`.

The public class name remains `ReActAgent` for import compatibility, but the runtime graph is Planner-Executor. The old ReAct tool-binding loop and clarify tool path have been removed.

Agent flow:

```text
RAGPipeline.query_agent()
  -> init_agent_docs()
  -> ReActAgent.run(query, history, user_context, complexity_subtype, top_k)
     -> route_entry
        -> comparison/multi_source: decompose -> planner
        -> general/missing subtype: planner
     -> validate plan
     -> executor when plan is valid and has steps
     -> optional web_search when plan.needs_web
     -> synthesize
  -> get_agent_docs()
  -> API response mapper + Mongo agent trace
```

Planner-Executor behavior:

- `_decompose_node()` uses the synthesis LLM only for `comparison` and `multi_source`.
- `_planner_node()` asks for JSON retrieval steps.
- `_validate_plan()` requires valid `query` and collection fields.
- `_executor_node()` calls `execute_retrieval_plan()` with the effective `top_k`.
- If every retrieval step is empty, the agent returns a deterministic no-information answer.
- Planner invalid JSON, empty steps, or invalid collection sets `state.error`; `RAGPipeline.query_agent()` handles fallback policy.

Direct legacy adapter tools still supported for tests/older callers:

- `rag_search`
- `multi_rag_search`
- `compare_cohorts`
- `compare_programs`
- `web_search`

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
- retrieval plan steps run in a thread pool with copied contextvars

## 11. Admin Document And Crawler Pipelines

Document HTTP owner: `api/routes/upload.py`.

Document pipeline owner: `pipeline/document_pipeline.py:DocumentPipeline`.

Document upload flow:

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

Crawler review owner: `scripts/auto_crawler.py` plus `api/routes/admin_stats.py`.

Current crawler flow:

```text
crawl official sources
  -> save JSON
  -> chunk content
  -> stage pending crawler_runs/crawler_chunks in Mongo
  -> admin review/edit staged chunks
  -> index_staged_crawler_run()
  -> embed with BGE/E5
  -> index Qdrant + Elasticsearch
  -> append reviewed chunks to archive
  -> invalidate LLM cache
  -> trigger post-index eval
  -> create notifications when applicable
```

Supported crawler targets in source include:

- `kehoach`
- `quydinh`

Default manual/scheduled/CLI `all` crawler runs stage data for review; direct CLI indexing is disabled in favor of admin review/index endpoints.

## 12. Persistence And Cache

Mongo access styles:

- `models/database.py`: async Motor singleton and FastAPI dependency.
- `models/mongo_logger.py`: sync durable logging for chat/session traces.

Core Mongo collections:

- `users`
- `refresh_tokens`
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
- `system_config`
- `crawler_runs`
- `crawler_chunks`

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
- `llm_cache:stats`
- `doc_cache_tag:{did}`
- `rate:min:{id}`
- `rate:day:{id}`

Redis behavior is fail-soft. If Redis fails, the backend should use Mongo or bypass the cache/rate limit instead of crashing.

## 13. Auth And User Context

Auth modules:

- `auth/jwt_handler.py`
- `auth/microsoft.py`
- `auth/password.py`
- `auth/refresh_tokens.py`
- `auth/rbac.py`
- `routers/auth.py`
- `schemas/user.py`
- `models/user.py`

Supported auth:

1. Microsoft OAuth under `/auth/login` and `/auth/callback`.
2. Manual register/login.
3. Refresh-token rotation through `/auth/refresh`.
4. JWT-backed `/auth/me` and profile update.
5. Refresh-token revocation through `/auth/logout`.
6. Superadmin-created admin accounts.

Refresh-token contract:

- Web receives refresh credentials as an HttpOnly cookie.
- Mobile sends `client_type="mobile"` and receives `refresh_token` in JSON.
- Refresh tokens are hashed in Mongo `refresh_tokens`.
- Rotation detects reuse/revocation families through `auth/refresh_tokens.py`.

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

- domain-specific index scripts under `scripts/`
- `scripts/index_kehoach.py`
- `scripts/index_quydinh.py`
- `scripts/index_stsv.py`
- `scripts/index_to_es.py`
- `scripts/index_parent_child.py`
- `scripts/auto_crawler.py`
- `scripts/update_data.py`
- `scripts/update_metadata.py`

Standalone indexers generally:

```text
load chunks
  -> filter already-indexed chunks where implemented
  -> embed in batches
  -> upsert Qdrant named vectors
  -> index Elasticsearch payload/text where supported
```

`data/document_lineage.json` is the source for superseded/active document filtering.

## 15. Tavily Web Fallback

Owner: `tools/tavily_search.py`.

Tavily is optional and created once in `RetrievalService` when key validation passes. `tavily_fallback_enabled` defaults to `False`.

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

Agent web search uses the agent adapter path and is only invoked when the planner requests it.

## 16. Web App

Path: `frontend/chat-companion`.

Stack:

- React 18
- Vite
- React Router
- TanStack Query
- shadcn/Radix UI
- Axios and Fetch/ReadableStream for SSE
- Tailwind CSS
- local service/type modules plus available `@rag/shared`

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

Protected route behavior:

- `RequireAuth`: chat/profile/bookmarks/notifications.
- `RequireAdmin`: trace/retrieval/eval/admin/document review.
- Unauthenticated direct navigation redirects to `/login?next=<path>`.
- Non-admin users reaching admin routes redirect to `/chat`.

Important web files:

- `src/App.tsx`
- `src/services/chatApi.ts`
- `src/services/authSession.ts`
- `src/services/adminApi.ts`
- `src/components/chat/ChatContainer.tsx`
- `src/components/sidebar/ConversationSidebar.tsx`
- `src/components/trace/PipelineTrace.tsx`
- `src/pages/DocumentReview.tsx`
- `src/pages/AdminPage.tsx`

Web auth behavior:

- Access tokens are kept in memory only.
- Legacy `localStorage.token` / `localStorage.access_token` are read once for migration and removed.
- User cache remains in localStorage.
- Refresh tokens are HttpOnly cookies set by the backend.
- Axios and streaming fetch helpers refresh once on 401 and retry the original request once.

## 17. Mobile App

Path: `mobile`.

Stack:

- Expo SDK 54
- React Native 0.81
- React 19
- React Navigation bottom tabs/native stacks
- TanStack Query
- Zustand
- SecureStore
- MMKV when native runtime supports it
- `react-native-sse`
- NativeWind/Tailwind-style styling
- `@rag/shared`

Root navigation:

```text
RootNavigator
  -> AuthStack when unauthenticated
  -> MainTabNavigator when authenticated
```

Main tabs:

- Chat
- Lookup
- Bookmarks
- Notifications
- Profile

Chat stack:

- Session list
- Chat detail

Mobile API/auth behavior:

- `mobile/src/services/api.ts` injects access tokens and has single-flight refresh-on-401.
- Mobile stores access and refresh tokens in SecureStore.
- Login/register calls use `client_type="mobile"` to receive JSON refresh tokens.
- `useStreamChat()` opens `/chat/stream` through `react-native-sse`.
- If streaming fails before the first token, it refreshes/retries once and can fall back to non-streaming `/chat/v3`.

Mobile no longer uses only one access token; it has a backend refresh-token flow.

## 18. Shared TypeScript Package

Path: `packages/shared`.

Exports:

- Axios API client factory
- chat/auth/session/bookmark/feedback/lookup/notification API helpers
- chat/auth/mobile types
- Zustand auth/chat store factories
- response normalization utilities
- profile options
- API path constants

`packages/shared/src/utils/constants.ts` currently includes:

- `/chat`
- `/chat/v3`
- `/chat/stream`
- `/health`
- `/auth/login`
- `/auth/register`
- `/auth/me`
- `/auth/refresh`
- `/sessions`
- `/sessions/me`
- `/session`
- `/bookmarks`
- `/bookmark-folders`
- `/feedback`
- `/lookup/ctdt`
- `/lookup/regulations`
- `/lookup/calendar`
- `/lookup/compare`
- `/chat/suggest`
- `/notifications`
- `/notifications/subscribe`

Keep these paths synchronized with FastAPI route paths.

## 19. Evaluation

Current evaluation framework: `evaluation/`.

Main suites:

- Current policy eval: production retrieval against currently indexed documents.
- Historical email eval: conversation/advisory behavior over historical context.
- SFT/backend eval helpers for frontend-style API payload validation.
- Post-index eval hooks after crawler indexing.

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
- auth/admin/upload/CORS/API host and port

Do not hard-code provider/model/host values when a setting exists.

Admin LLM config:

- `GET /admin/config/llm` returns effective runtime LLM settings with keys masked.
- `PUT /admin/config/llm` prepares a pipeline reload, persists whitelisted overrides in Mongo, commits the prepared runtime, and invalidates Redis LLM answers when generation tuning changes.
- Startup merges non-empty persisted values over `.env`/defaults.

## 21. Known Cautions

1. `api/routes/retrieval.py` reads `getattr(pipeline, "service", None)`, while `RAGPipeline` stores the shared retrieval service as `_retrieval_service`. Without a public property, `/retrieval/search` can cold-load a new `RetrievalService`.

2. `api/main.py` auto-crawler reuse checks `hasattr(pipe, "retrieval_service")`, but `RAGPipeline` currently does not expose that property.

3. `api/routes/session.py` intends `/sessions` and `/sessions/me` by combining router prefix `/session` with route paths `"s"` and `"s/me"`. Keep route behavior covered by tests because this shape is easy to break.

4. `DocumentPipeline.chunk()` has had debug/output behavior under `data/quydinh/admin_upload`; verify before relying on this path in production.

5. Redis features are inactive unless both `redis_enabled` and the relevant per-feature flags are true, and should remain fail-soft.

6. `ReActAgent` is now a Planner-Executor graph despite the legacy class name. Do not assume a graph-bound ReAct tool loop or `clarify_question` tool exists.

7. Streaming chat does not run post-generation self-eval/Tavily fallback.

8. Root `README.md` may lag behind `PROJECT_MEMORY.md`, `MODULE.md`, and this file for current runtime behavior.

## 22. High-Level Mental Model

```text
Client asks question
  -> FastAPI resolves auth/session/user_context
  -> RAGPipeline.query_v3 smart-routes
     -> chitchat: direct local response
     -> simple: classic RAG
     -> complex: LangGraph Planner-Executor agent
        -> fallback to classic RAG when allowed and agent fails/disabled
  -> RetrievalService searches Qdrant + Elasticsearch
  -> BGE reranker selects grounded context
  -> validity/reference/parent-context post-processing
  -> DeepSeek classic RAG answer or agent synthesis answer
  -> Mongo/Redis persist logs, sessions, caches
  -> API maps response for web/mobile trace/debug UI
```
