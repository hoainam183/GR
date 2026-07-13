# RAG v2 Architecture

Source-verified: 2026-07-10 from source files (backend, frontend, mobile, shared package, ingestion scripts, and evaluation) plus four focused subagent reads of backend/API, frontend/mobile/shared, core RAG/retrieval/agent, and admin ingestion/crawler/eval. This pass reflects current HEAD `cf2b5fca`. Net behavioral deltas since the prior 2026-06-12 pass:

- `query()` is the classic RAG path and does not start with `ComplexityRouter`; smart routing lives in `query_v3()` and `query_stream()` with reflection + Tier-0/Tier-1/Tier-2 complexity decisions.
- `/chat/stream` always uses the smart streaming path (`query_stream()`) and does not honor `body.mode`; web and mobile primarily call `/chat/stream`, with `/chat/v3` as the non-streaming fallback/helper.
- The agent class is still named `ReActAgent`, but the runtime graph is `planner -> executor? -> synthesize`; there is no `_route_entry`, `_decompose_node`, graph-bound ReAct loop, or clarify tool in the active chat path. Valid agent collections now include `lich_thi`.
- Runtime retrieval defaults are RRF (`fusion_mode="rrf"`, `fusion_rrf_k=10`); linear max-normalized fusion remains available for overrides/experiments.
- `self_eval_enabled=True` and `tavily_fallback_enabled=True` by default, subject to valid API keys and runtime gates; streaming still skips post-generation self-eval/Tavily.
- Admin document ingestion supports PDF/DOCX conversion, markdown review, clean review, optional `llm-clean`, chunk review, and explicit index approval. `run_full_pipeline()` never auto-indexes.
- Structured exam schedule ingestion is a first-class path: `/admin/exam-schedules*` writes Mongo `exam_schedules` and Elasticsearch index `exam_schedules`; chat reaches it through agent collection `lich_thi`, not Qdrant vector retrieval.
- The web app no longer has `/trace` or `/retrieval` routes; trace details are embedded in chat/admin surfaces. Mobile adds SecureStore refresh flow, MMKV/memory offline cache, and Expo push subscription helpers.
- There is no active `src/RAG_v2/eval/` package; production evaluation lives under `evaluation/`, with `evaluation/evaluate.py` running the production `RAGPipeline.query_v3()` stack.

> Reading order: sections 2–22 are the reference (exact contracts, defaults, file owners). **Section 23 is the Uber/Airbnb-style system design** — requirements, scale, C4 diagrams, request lifecycles, data model, scaling/bottlenecks, and trade-offs. Read section 23 first for the big picture, then drop into the reference sections for detail.

## 1. System Goal

`RAG_v2` is a HUST academic assistant. It answers student questions over internal academic sources and can optionally use official web search for fresh plan/deadline questions.

Primary knowledge collections:

| Collection | Meaning |
| --- | --- |
| `ctdt` | Curriculum, majors, course plans, credits, prerequisites. |
| `quydinh` | Regulations, scholarships, graduation rules, foreign-language rules. |
| `kehoach` | Academic plans, registration schedules, notices, deadlines. |
| `stsv` | Student-support handbook, forms, procedures, support services. |
| `lich_thi` | Structured exam schedule rows in Mongo/Elasticsearch; agent-only lookup, not a Qdrant vector collection. |
| `test` | Upload/dev collection. |

The system includes:

- FastAPI backend.
- Smart RAG pipeline.
- LangGraph Planner-Executor agent for complex/multi-source questions.
- Qdrant + Elasticsearch hybrid retrieval plus structured Elasticsearch exam-schedule lookup.
- MongoDB persistence.
- Optional Redis session/cache/history/rate-limit layer.
- Admin document upload/review/LLM-clean/indexing pipeline.
- Admin crawler staging/review/indexing workflow.
- Admin exam-schedule upload/parse/index workflow.
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
  pipeline/          RAGPipeline, flow package, DocumentPipeline.
  query/             Complexity/domain routing, reflection, signals, structured-query and course-catalog helpers.
  retrieval/         Qdrant, ES, hybrid/multi-collection search, exam-schedule store, filters, resolver.
  embedding/         BGE-M3 and multilingual E5 embedders.
  reranking/         BGE cross-encoder reranker.
  llm/               DeepSeek/Gemini/LM Studio wrappers, prompts, self-eval.
  agent/             LangGraph Planner-Executor agent and retrieval/web adapters.
  models/            Mongo models, Motor client, MongoLogger, system config.
  cache/             Optional Redis sessions, history, LLM cache, rate limits.
  chunking/          Offline/admin chunkers and metadata enrichment.
  document_loader/   PDF/DOCX -> Markdown conversion, cleanup, LLM reformatter.
  services/          Structured exam-schedule parser/service helpers.
  scripts/           Crawlers, indexers, course catalog, metadata maintenance.
  data/              Local corpus, chunks, metadata, exam-schedule artifacts, lineage registry.
  tools/             Tavily web-search adapter.
  utils/             Storage, tracing, chunk indexing policy, helpers.
  evaluation/        Active eval/regression framework.
  frontend/          React/Vite web app.
  mobile/            Expo/React Native app.
  packages/          Shared TypeScript package `@rag/shared`.
  backend/           Thin legacy wrapper around `api.main.app`.
  tests/             Pytest regression/unit/contract tests.
```

Most source directories above have a `MODULE.md` with module-specific contracts and checks. There is no root-level `src/RAG_v2/MODULE.md`, and several older module docs lag behind the source; this architecture file is source-verified against the current code.

## 3. Runtime Stack

| Layer | Technology / source |
| --- | --- |
| API | FastAPI in `api/main.py` |
| Chat orchestration | `pipeline/rag_pipeline.py`, `pipeline/flows/*.py` |
| Agent | LangGraph Planner-Executor in `agent/react_agent.py` |
| Query routing | `query/complexity_router.py`, `query/router.py`, `query/domain_classifier.py` |
| Query rewrite | `query/reflection.py` |
| Vector store | Qdrant named vectors `bge_m3` and `e5` |
| Keyword store | Elasticsearch indexes named by collection |
| Structured lookup | `services/exam_schedule_*`, `retrieval/exam_schedule_store.py` |
| Embeddings | BGE-M3; multilingual E5 is loaded when `embedding_provider == "ensemble"` |
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
| `chat_max_tokens` | `1500` |
| `agent_enabled` | `True` |
| `agent_model` | `qwen2.5-7b-instruct` |
| `agent_max_iterations` | `3` |
| `agent_temperature` | `0.0` |
| `agent_max_tokens` | `1200` |
| `agent_synthesis_provider` | `gemini` |
| `agent_synthesis_model` | `gemini-3.1-flash-lite` |
| `agent_synthesis_temperature` | `0.2` |
| `agent_synthesis_max_tokens` | `2500` |
| `reflection_enabled` | `True` |
| `reflection_provider` / `reflection_model` | `gemini` / `gemini-3.1-flash-lite` |
| `domain_routing_enabled` | `True` |
| `domain_confidence_threshold` | `0.65` |
| `router_mode` | `classifier` |
| `embedding_provider` | `ensemble` |
| `fusion_mode` / `fusion_rrf_k` | `rrf` / `10` |
| `vector_bge_weight` / `vector_e5_weight` | `0.5` / `0.5` |
| `self_eval_enabled` | `True` |
| `tavily_fallback_enabled` | `True` |
| `llm_clean_enabled` | `True` |
| `exam_schedule_es_index` / `exam_schedule_search_top_k` | `exam_schedules` / `500` |
| `rate_limit_enabled` / `rate_limit_rpm` / `rate_limit_rpd` | `True` / `20` / `200` |
| `redis_enabled` (+ `use_redis_session/cache/history`) | `True` |
| `crawler_enabled` | `True` |
| `post_index_eval_enabled` | `True` |

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
- note: `models.database.close_motor_client()` exists, but the current `api/main.py` shutdown path does not call it

Important singleton contract:

```text
RAGPipeline creates one RetrievalService.
Agent adapters receive that same service through inject_from_retrieval_service().
```

`RAGPipeline` stores the service as `_retrieval_service` and now exposes it through a public read-only `retrieval_service` property. Request handlers resolve it with `getattr(pipeline, "retrieval_service", None) or getattr(pipeline, "_retrieval_service", None)` (`api/routes/retrieval.py`, `lookup.py`, `admin_stats.py`) and the `api/main.py` auto-crawler reuse check (`hasattr(pipe, "retrieval_service")`) now succeeds, so they all share the singleton instead of cold-loading a second `RetrievalService`.

`RateLimitMiddleware` is created when the app is built and currently applies only to `POST /chat`, `/chat/v3`, `/api/chat/v3`, and `/chat/stream`. Its identity priority is JWT `sub`, then first `X-Forwarded-For`, then client IP. Runtime `PATCH /admin/config` changes `app.state.settings`, but it does not recreate the rate limiter or crawler scheduler in-place.

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
| `/admin/documents*` | `api/routes/upload.py` | Admin document upload/convert/clean/LLM-clean/chunk/review/index pipeline. |
| `/admin/converters`, `/admin/chunkers` | `api/routes/upload.py` | Admin upload UI options. |
| `/admin/exam-schedules*` | `api/routes/exam_schedules.py` | Structured exam schedule PDF/XLSX/XLSM ingestion, summary, deletion. |
| `/admin/stats/*` | `api/routes/admin_stats.py` | Admin overview/users/query/agent/feedback/system stats. |
| `/admin/users/{user_id}/status` | `api/routes/admin_stats.py` | Admin user activation toggle. |
| `/admin/crawler/*` | `api/routes/admin_stats.py` | Manual crawl, staged chunk review, crawler indexing. |
| `/admin/config*` | `api/routes/admin_stats.py` | Runtime toggles, LLM config, API key/env config. |
| `/admin/notifications*`, `/admin/notifications/broadcast` | `api/routes/notification_admin.py` | Admin notification creation/broadcast. |
| `/bookmarks*` | `api/routes/bookmark.py` | Saved answers/folders. |
| `/bookmark-folders*` | `api/routes/bookmark.py` | Bookmark folders. |
| `/feedback*` | `api/routes/feedback.py` | Answer ratings/comments/stats. |
| `/lookup/*` | `api/routes/lookup.py` | Mobile quick lookup. |
| `/notifications*` | `api/routes/notification.py` | User notification inbox, unread count, read/delete, push subscribe/unsubscribe. |

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
- `/chat/stream`: always calls `RAGPipeline.query_stream()` and ignores `body.mode`; it smart-routes chitchat/simple/complex on the streaming path.

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
{"type":"status","stage":"...","message":"..."}   # progress, mainly on the agent path
{"type":"token","delta":"..."}
{"type":"metadata", ...}
{"type":"error","error":"..."}
{"type":"done"}
: heartbeat                                        # SSE comment frame on idle, keeps proxies alive
```

`/chat/stream` serves all three tiers: chitchat streams through `chitchat_flow_stream()`, simple RAG streams tokens from `rag_flow_stream()` after retrieval, and the complex/agent tier emits `status` progress, runs `query_agent()` synchronously, then chunks the synthesized answer for token-style animation. It can do pre-generation web enrichment on the simple RAG streaming branch, but it skips post-generation self-eval/Tavily on every streaming path.

Client usage:

- Web `ChatContainer` primarily calls `/chat/stream` through `sendMessageStream()`.
- Mobile `useStreamChat()` opens `/chat/stream` through `react-native-sse`.
- `/chat/v3` remains the non-streaming fallback/helper; `POST /chat` remains a backend compatibility endpoint.

## 7. Query Processing

High-level flow for classic RAG (`RAGPipeline.query()`):

```text
raw question + history + profile
  -> _route_with_cache()
     -> QueryRouter / DomainClassifier
     -> optional cached Tier-3 LLM domain classification
  -> rag_flow()
     -> QueryReflector
     -> reflected reroute/select when needed
     -> CollectionSelector
     -> profile/entity helpers
     -> metadata filters + retrieval query
```

High-level flow for smart chat (`RAGPipeline.query_v3()` and `query_stream()`):

```text
raw question + history + profile
  -> QueryReflector once
  -> ComplexityRouter Tier-0 deterministic checks on reflected query
  -> if unknown: Tier-1 QueryRouter / DomainClassifier multi-label evidence
  -> if multi-domain/borderline: Tier-2 LLM complexity judge
  -> branch: chitchat | simple classic RAG | complex agent
```

`ComplexityRouter` returns:

- `chitchat`
- `simple`
- `complex`
- `unknown` internally when deterministic evidence is insufficient; public smart routing collapses unresolved cases to `simple`

Current complex subtypes:

- `comparison`
- `multi_source`
- `general`

The old `personal_check` subtype is intentionally removed. Personal-reference eligibility/graduation wording routes as `multi_source`, so it reaches the Planner-Executor when the agent is enabled.

Concrete exam-schedule questions (`lich thi`, `phong thi`, `ma lop thi`, subject/date/group/cohort clues) route as `complex/general` so the agent can use the structured `lich_thi` collection. Generic "lịch thi cuối kỳ khi nào" planning questions remain `kehoach` schedule queries.

`DomainClassifier` is two-stage:

1. intent: `blocked`, `chitchat`, `rag`, `tool_search`
2. RAG domains: `ctdt`, `quydinh`, `kehoach`, `stsv`

`blocked` is a non-RAG guard intent for sensitive/OOD requests (adult/18+, illegal/harmful, and generic non-HUST tasks such as weather, movies, stocks, restaurants, or broad web searches). It returns the fixed safe answer, skips reflection, routing, hybrid search, rerank, agent, and Tavily, and is not persisted to MongoDB.

`tool_search` is reserved for HUST/ĐHBK-related fresh or official web queries. Generic fresh/web requests without university context route to `blocked`.

`QueryRouter` does a second pass with history only for short, low-confidence follow-up queries (classifier logic uses the low-confidence threshold and roughly `< 8` words; the context helper also catches very short/demonstrative follow-ups). Long self-contained queries should not be biased by old session domains, and a raw `blocked` prediction is never overridden by history.

Tier-3 LLM domain fallback (`DOMAIN_CLASSIFICATION_PROMPT`) fires when classifier confidence is below the low-confidence ceiling (`< 0.55`) **and** the top-two domain margin is narrow (`< 0.25`). It now runs **inside `_route_with_cache()`** (before the route is cached), so a repeated low-confidence query reuses the enriched routing instead of paying the ~12 s LLM call again. `_should_trigger_tier3()` distinguishes "no confidence reported" (`None`) from a genuine high score so it does not silently disable itself when the router returns `confidence=None`, and `_llm_domain_classify()` extracts the first `{...}` JSON object via regex (the old `strip("```json")` stripped character sets, mangling valid JSON). The prompt is Vietnamese with few-shot WHEN/CONTENT/CONDITION/PROCEDURE disambiguation examples and can override the predicted domains only when valid `RAG_LABELS` are returned.

`QuerySignals` (`query/signals.py`) is a frozen dataclass of 11 boolean intent signals that feed both complexity routing and collection augmentation: `personal_reference`, `eligibility_check`, `exact_policy_lookup`, `table_lookup`, `procedural_support`, `multi_domain` (derived), `freshness`, `schedule_intent`, `deadline_intent`, `announcement_intent`, and `curriculum_semester_intent` (asks which semester a course sits in, distinct from when registration opens). Recent tuning broadened program-code coverage (e.g. `IT-E6`, `ME-GU`, `CH-LUH`, `…-NUT` in both `complexity_router` comparison patterns and `structured_query` major-code extraction), tightened the personal-reference regex (possessive `của tôi/mình/em` forms), and made the `cho … và …` repeated-request complex trigger require an explicit `và` connector.

Query helpers support deterministic, profile-aware retrieval:

- `query/course_catalog.py` loads the prebuilt `query/models/course_catalog.json` (produced by `scripts/build_course_catalog.py`) and resolves a course **name → code** scoped to a major's curriculum, because the same course name maps to different codes across programs (e.g. `IT3080` in `IT-E6` vs `IT3080E` in `IT-E7`). Reflection guardrails use it to inject the correct course code in place.
- `pipeline/flows/profile.py`, `QueryReflector`, and `agent/planning.py` decide when profile attributes (`major`, `cohort`) matter for reflection, retrieval filters, and agent planning; there is no active `query/profile_dependency.py` module.

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
- `ComplexityRouter`
- chat LLM through `llm.create_llm()`
- optional `SelfEvaluator`
- optional `ReActAgent`
- `ValidityFilter`
- `ReferenceResolver`
- runtime LLM reload lock/cache state

Smart entrypoint (`query_v3()` first runs the cheap blocked guard, then runs `QueryReflector` once up front, complexity-routes on the reflected question, and reuses that reflection across the simple/agent branches):

```text
query_v3()
  -> blocked guard: safe fixed answer, no persistence/retrieval/tools
  -> reflect once
  -> decide complexity through Tier-0/Tier-1/Tier-2
  -> chitchat: local canned handler, no retrieval
  -> simple or agent disabled: classic query(pre_ref_result=...)
  -> complex: query_agent()
     -> planner -> executor? -> synthesize
     -> fallback to classic RAG when agent is disabled/errors unless require_agent=True
```

Typical returned modes:

- `blocked`
- `chitchat`
- `rag_v2`
- `agent`
- `rag_v2_fallback`

There is no separate decomposition bypass in the current chat path; complex questions go through the Planner-Executor agent when the agent is available.

Classic RAG flow in `pipeline/flows/coordinators.py:rag_flow()`:

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

- Blocked queries exit before history loading, reflection, routing, retrieval, rerank, generation, Tavily, agent tools, and Mongo turn logging.
- List/enumeration queries can request larger context.
- Kehoach freshness/dynamic routing can lock to `kehoach`.
- Course-like queries bias retrieval fusion toward keyword matching.
- Reranker calls receive configured thresholds and `reranker_min_top_k`.
- Context-size errors can trigger reduced-context retry.
- Cache writes are restricted to stable local answers: answered status, no no-info/no-source/self-eval-failed markers, no dynamic/stale-risk signal, and no web fallback.
- Answer-cache keys (both the query-only `get_by_query`/`put_by_query` cache and the doc-id `get`/`put` cache) are scoped by a normalized `major|cohort` profile (`_build_cache_profile`). Without this scope a profile-dependent answer (e.g. "điều kiện tốt nghiệp của tôi") generated for one student could be served verbatim to another — a cross-student data leak. Anonymous/no-profile requests use an empty scope (legacy key space).
- Streaming (`query_stream()`) runs the blocked guard first; blocked streams the fixed safe answer immediately, then the caller emits metadata with `route="blocked"` and `done`. Otherwise it reflects and complexity-routes once, then branches like `query_v3`: chitchat uses the LLM streaming flow, simple RAG runs retrieval (with optional pre-generation web enrichment) and streams tokens, and complex emits `status` progress, runs the agent synchronously, and chunk-animates the synthesized answer. Every streaming path intentionally avoids post-generation self-eval/Tavily.
- Streaming per-request state lives in a request-local `SimpleNamespace` (`_st`) rather than `self.last_*`, because `RAGPipeline` is a singleton driven concurrently for many users; writing to `self.last_*` would let concurrent streams clobber each other's Mongo log and `metadata` SSE payload. The local state is snapshotted into the caller-owned `metadata_out` dict as the generator's final step, and only mirrored onto `self.last_*` afterward for single-request tests/debugging (not authoritative under concurrency).

Runtime LLM reload:

- `prepare_llm_config_reload()` builds replacement chat LLM, reflector, self-evaluator, agent, and Tavily references before Mongo persistence.
- `commit_llm_config_reload()` hot-swaps the prepared runtime under a lock, clears route cache, updates the shared retrieval service settings/Tavily, and reinjects the service into agent adapters.
- Admin LLM-clean uses the document pipeline/reformatter path and reloads persisted LLM settings before reformatting; it is not part of the chat hot-swap object graph.

## 9. Retrieval

Runtime wrapper: `retrieval/service.py:RetrievalService`.

`RetrievalService.from_settings()` builds:

- BGE-M3 embedder
- E5 embedder when `embedding_provider == "ensemble"`; otherwise a dummy zero-vector path keeps the interface stable
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
  -> RRF fusion by default, or max-normalized linear fusion when configured
  -> kehoach recency bonus
  -> text-level dedup
  -> top-k candidates
```

Default retrieval settings in source:

| Setting | Default | Meaning |
| --- | --- | --- |
| `collections` | `["stsv", "quydinh", "kehoach", "ctdt"]` | Active domains. |
| `top_k` | `7` | Final docs after rerank. |
| `embedding_provider` | `ensemble` | Load BGE-M3 and E5 real embedders; non-ensemble uses BGE plus dummy E5. |
| `fusion_mode` / `fusion_rrf_k` | `rrf` / `10` | Runtime hybrid fusion default. |
| `vector_bge_weight` / `vector_e5_weight` | `0.5` / `0.5` | Named-vector blend weights inside Qdrant dual-vector fusion. |
| `vector_top_k` | `50` | Per-collection vector pool. |
| `keyword_top_k` | `50` | Per-collection keyword pool. |
| `vector_pool_k` | `40` | Global vector pool after collection merge. |
| `keyword_pool_k` | `40` | Global keyword pool after collection merge. |
| `raw_candidate_multiplier` | `4.0` | Candidate fan-out factor. |
| `raw_candidate_min` | `20` | Candidate floor. |
| `vector_weight` | `0.8` | Fusion weight for dense. |
| `keyword_weight` | `0.2` | Fusion weight for keyword. |
| `reranker_top_k` / `reranker_min_top_k` | `7` / `3` | Rerank output / min floor. |
| `reranker_score_threshold` | `0.0` | General-doc rerank cutoff (calibrated for full recall). |
| `reranker_table_score_threshold` | `-1.0` | Relaxed cutoff for table chunks. |
| `context_doc_char_limit` | `2000` | Per-doc context cap. |
| `context_total_char_budget` | `12000` | Default total context budget. |
| `context_total_char_budget_with_expansion` | `16000` | Budget when parent/sibling expansion is active. |
| `context_list_total_char_budget` | `24000` | Larger budget for list/enumeration queries. |
| `parent_context_enabled` | `True` | C5 parent-child expansion (`parent_max_chars` 1500, `parent_max_chars_agent` 500). |
| `hyde_enabled` | `True` | HyDE post-rerank fallback. Triggers when no docs survive rerank, the best explicit rerank score is negative, **or** fewer than `hyde_min_results` (3) docs survive. The mean-score `hyde_confidence_threshold` (0.3) path is reserved/unused because raw cross-encoder logits are unnormalized. `RetrievalService.search_with_hyde()` sizes its candidate pool from `raw_candidate_multiplier` (with a 40 floor). |
| `score_cliff_enabled` | `False` | B1 per-collection score-cliff pruning. |
| `sibling_expansion_enabled` | `False` | C1 sibling-chunk expansion before rerank. |

Fusion default: runtime settings use `fusion_mode="rrf"` with `fusion_rrf_k=10`; `rag_flow()` also falls back to RRF if the setting is absent. RRF combines vector and keyword rank evidence using the configured dense/keyword weights, rescales the `kehoach` recency bonus by `1/(rrf_k+1)`, then normalizes final scores back to a 0-1 range. Linear fusion is still available and **max-normalizes** each pool independently (`norm = score / pool_max`, with a doc absent from a pool contributing `0` for that pool) before combining `vector_weight × norm_vec + keyword_weight × norm_kw + kehoach_recency_bonus`. This replaced the older min-max normalization, which forced the lowest-scoring doc in each pool to `0` and silently dropped relevant docs that were merely last in a pool or present in only one pool. The same max-normalization (per model) is applied to the in-Qdrant BGE/E5 dual-vector fusion in `qdrant_store.py`. Elasticsearch uses a custom Vietnamese analyzer (CocCoc `vi_tokenizer` with ASCII-folding/synonym/stopword filters, BM25 `k1=1.5`, `b=0.5`).

Metadata filter behavior:

| Collection | Filter logic |
| --- | --- |
| `ctdt` | Major code/name with generic fallback. |
| `quydinh` | Cohort/applicability with null fallback; no major metadata prefilter in the current source. |
| `kehoach` | Month/year/freshness filters or date-desc strategy. |
| `stsv` | No default prefilter. |

Exam schedule lookup:

- `lich_thi` is not searched through Qdrant/MultiCollectionSearch.
- `/admin/exam-schedules` parses PDF/XLSX/XLSM into Mongo `exam_schedules` and Elasticsearch index `exam_schedules`.
- The agent planner can emit collection `lich_thi`; `agent/tool_adapters.py` dispatches that step to structured exam-schedule search.
- Generic academic-calendar exam planning stays in `kehoach`; concrete subject/date/room/group exam queries use `lich_thi`.
- Cohort filtering in the exam adapter is literal-query based (`Kxx` in the question), not automatically inferred from the user profile.

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
  -> reflect when no pre-reflected query is provided
  -> init_agent_docs()
  -> ReActAgent.run(query, session_id, history, complexity_subtype, user_context, top_k)
     -> planner
     -> validate plan
     -> executor when plan is valid and has steps
        -> planned RAG searches or structured lich_thi lookup
        -> optional Tavily only when plan.needs_web and local retrieval is not usable
     -> synthesize
  -> get_agent_docs()
  -> fallback to classic RAG on planner/agent failure unless require_agent=True
  -> API response mapper + Mongo agent trace
```

LangGraph topology (`react_agent.py`): `START -> _planner_node -> _after_planner -> (_executor_node?) -> _synthesize_node -> END`. `_after_planner` skips the executor and jumps to synthesis when the planner set an error or produced no steps. There is no standalone web-search node, no graph-bound LangChain tool loop, no clarify tool path, and no separate decompose node in the current chat graph.

Planner-Executor behavior:

- `ReActAgent.run(query, session_id, history, complexity_subtype, user_context, top_k)` is the entrypoint. `history` is consumed by the planner/synthesis prompts, and `complexity_subtype` is a planning hint rather than a graph branch.
- `_planner_node()` asks for JSON retrieval steps; `_validate_plan()` requires a non-empty `steps` list where every step has a non-empty `query` and a `collection` in `{quy_dinh, chuong_trinh, ke_hoach, ho_tro_sv, lich_thi}`.
- `_executor_node()` calls `execute_retrieval_plan()` with the effective `top_k`; steps run in a `ThreadPoolExecutor` (`max_workers=min(4, len(steps))`, 45 s per-step timeout) over copied contextvars.
- `execute_retrieval_plan()` is the main runtime adapter path. RAG steps search one agent-facing collection with optional `major_hint` and `cohort_hint`; `lich_thi` steps call the structured exam-schedule Elasticsearch adapter.
- If `plan.needs_web` is true and no usable local RAG messages exist, `_executor_node()` calls `web_search_for_executor()`. That wrapper strips personal identifiers before calling Tavily and only succeeds when a valid Tavily key exists and `tavily_fallback_enabled` is true.
- If all local retrieval steps are empty, the agent can retry once with major/cohort filters relaxed (`agent_retry_on_empty`, default true). If no `ToolMessage` is produced after retry/web handling, it returns a deterministic no-information answer instead of triggering another agent loop.
- The planner sets `state.error` to `planner_invalid_json`, `planner_empty_steps`, or `planner_invalid_plan`; `RAGPipeline.query_agent()` handles the fallback policy.

Runtime adapter surface:

- Planner emits JSON retrieval steps; executor calls `execute_retrieval_plan()`.
- Each retrieval step runs one planned RAG search against an agent-facing collection, or a structured exam-schedule lookup for `lich_thi`, with optional `major_hint` and `cohort_hint`.
- Optional web search is not a graph tool. `_executor_node()` calls `web_search_for_executor()` directly when `plan.needs_web` is true.
- Legacy direct tool adapter entrypoints remain for tests/backward compatibility with older direct callers; they are not part of the main chat graph.

Agent collection aliases:

| Agent key | Internal collection |
| --- | --- |
| `chuong_trinh` | `ctdt` |
| `quy_dinh` | `quydinh` |
| `ke_hoach` | `kehoach` |
| `ho_tro_sv` | `stsv` |
| `lich_thi` | structured `exam_schedules` Elasticsearch index / Mongo rows |

Thread-safety:

- per-request docs are stored in a ContextVar
- agent RAG cache is lock-protected
- reranker calls are serialized inside `BGEReranker.rerank` via instance-level `self._lock` (protects every call path)
- retrieval plan steps run in a thread pool with copied contextvars

## 11. Admin Document And Crawler Pipelines

Document HTTP owner: `api/routes/upload.py`.

Document pipeline owner: `pipeline/document_pipeline.py:DocumentPipeline`.

Document upload flow:

```text
admin upload PDF/DOCX
  -> LocalStorage original file
  -> Mongo documents status=uploaded, review flags false
  -> convert_document()
  -> markdown
  -> markdown review
  -> clean()
  -> cleaned markdown
  -> cleaned review
  -> optional llm_clean()
  -> llm_cleaned markdown + warnings
  -> llm-clean review
  -> chunk()
  -> Mongo document_chunks
  -> edit/delete/select/approve chunks
  -> embed_and_index()
  -> Qdrant + Elasticsearch + Mongo indexed counts
```

Status lifecycle:

```text
uploaded -> converting -> converted -> cleaning -> cleaned
-> llm_cleaning -> llm_cleaned -> chunking -> chunked
-> embedding -> indexed
```

Any processing stage can move to `failed`; chunk edits/deletes are allowed only while a document is `chunked` or `failed` after chunking.

Rollback can step back from indexed/chunked/cleaned/converted states and delete indexed Qdrant/ES data by `document_id`.

Indexing policy:

```text
utils.chunk_indexing.is_indexable_chunk()
  rejects parent/header chunks
```

Qdrant stores parent and child chunks that pass `is_qdrant_storable()`. Elasticsearch indexes only chunks that pass `is_indexable_chunk()`, so parent/header chunks can remain in Mongo/Qdrant for review/context expansion but should not consume direct search slots.

Crawler review owner: `scripts/auto_crawler.py` plus `api/routes/admin_stats.py`.

Current crawler flow:

```text
crawl official sources
  -> clean/extract content
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

Supported crawler targets in source:

- `kehoach` (two sources: `DisplayListBaiViet` and `DisplayListKeHoach`; ~6-month retention).
- `quydinh` (`DisplayQuyChe`; long retention, ~96 months).

Default manual/scheduled/CLI `all` crawler runs stage data for review; direct auto-indexing is disabled in favor of admin review/index endpoints. Runtime crawler statuses are `pending_review`, `indexing`, `indexed`, and `index_failed`.

`DocumentPipeline` exposes conversion, `clean()`, optional LLM reformat/clean, `chunk()`, `embed_and_index()`, `rollback()`, and `run_full_pipeline()`. PDF conversion supports `pymupdf4llm` (default), `docling`, and `pdfplumber`; DOCX uses Docling. The `pymupdf4llm` path can fall back to Docling when extraction is too short. Chunking prefers `llm_cleaned_path`, then `cleaned_path`, then `markdown_path`.

Review gate is now enforced in code:

- `chunk()` (re)stages chunks and resets `chunks_reviewed=False`.
- Admins can edit a staged chunk (`PATCH /admin/documents/{doc_id}/chunks/{chunk_id}`, body `ChunkUpdateRequest`) or remove one (`DELETE /admin/documents/{doc_id}/chunks/{chunk_id}` → `ChunkDeleteResponse`); approval sets `chunks_reviewed=True`.
- `embed_and_index()` raises `ValueError("Chunks must be approved before indexing")` unless `chunks_reviewed` is true.
- `run_full_pipeline()` never auto-indexes: it runs convert → clean, then stops after LLM-clean when LLM-clean is requested, otherwise continues to chunk and stops. Indexing always waits for the admin approval gate.
- The chunk debug dump writes to a **project-relative** path (`RAG_v2/data/quydinh/admin_upload`) instead of a hardcoded per-developer absolute path (failure is caught and non-fatal).

Structured exam schedule owner: `api/routes/exam_schedules.py`, `services/exam_schedule_*`, `retrieval/exam_schedule_store.py`.

Exam schedule ingestion:

```text
admin upload PDF/XLSX/XLSM (+ optional exam_type=giua_ky|cuoi_ky)
  -> uploads/exam_schedules
  -> parse HUST 13-column schedule rows
  -> validate subject_code/exam_date
  -> Mongo exam_schedules (source of truth)
  -> Elasticsearch index exam_schedules when ES is available
  -> summary/delete endpoints for admin UI
```

If Elasticsearch is unavailable, ingestion still writes Mongo rows and reports the indexing limitation. Runtime chat lookup for concrete exam schedule questions goes through the agent `lich_thi` structured adapter, not through vector RAG sources.

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
- `exam_schedules`
- `eval_runs`
- `eval_case_results`

(19 practical collections total. `query_logs`, `agent_traces`, `eval_runs`, `eval_case_results` are written by `models/mongo_logger.py`; the rest are managed by the async Motor models and route handlers.)

`system_config` currently stores runtime LLM/config records such as `_id="llm_config"` plus the active API key registry (`deepseek`, `google`, `tavily`). `/admin/config/env` persists `_id="env_config"`, but the startup merge path currently reads `llm_config`/API keys rather than applying all `env_config` values as process environment.

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
- `llm_cache:{sha}` (the `sha` folds in the asking student's `major|cohort` profile so personal answers are not shared across profiles)
- `llm_cache:q:{sha}` (pre-retrieval query-only cache; profile is part of the `sha` too)
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

1. Microsoft OAuth under `/auth/login` and `/auth/callback`, gated to `@sis.hust.edu.vn`.
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

For chat requests, authenticated DB identity wins over request-body identity. Optional-auth dependencies return anonymous only when the authorization header is absent; a malformed/invalid Bearer token still produces 401.

## 14. Data And Ingestion

Curated data lives under `data/`:

```text
data/
  document_lineage.json
  ctdt/
  kehoach/
  lichthi/
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
- `scripts/build_course_catalog.py` (parses curriculum tables into `query/models/course_catalog.json`)
- `scripts/download_models.py`, `scripts/setup_mongo_indexes.py`, `scripts/metadata_audit.py`, `scripts/search_multi.py` (utilities)
- exam schedule ingestion through `/admin/exam-schedules` rather than standalone vector indexers

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

Tavily is optional and created once in `RetrievalService` when key validation passes. `tavily_fallback_enabled` defaults to `True`, but calls still require a valid active `tavily_api_key` and a query path that elects web fallback.

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

Both stages now forward the configured `tavily_web_result_count` and `tavily_web_content_char_limit` into the search, and the pre-generation search derives a `query_year` (the latest `20XX` mentioned in the query, via `_extract_query_year`) so Tavily's freshness filter drops stale official pages from older academic years. Searches are restricted to `HUST_OFFICIAL_DOMAINS`.

Agent web search uses the agent adapter path and is only invoked when the planner requests it and local retrieval did not produce usable RAG messages.

## 16. Web App

Path: `frontend/chat-companion`.

Stack:

- React `18.3.1`
- Vite `5.4.x`
- React Router `6.x`
- TanStack Query `5.x`
- shadcn/Radix UI
- Axios for REST; native Fetch + `ReadableStream` for SSE streaming (no `react-native-sse` here)
- Tailwind CSS `3.4.x`
- local service/type modules plus available `@rag/shared`
- base API URL from `VITE_API_URL || http://localhost:8000`

Routes:

- `/`
- `/chat`
- `/chat/:sessionId`
- `/login`
- `/register`
- `/complete-profile`
- `/eval`
- `/admin`
- `/admin/documents/:id`
- `/bookmarks`
- `/notifications`

Protected route behavior:

- `RequireAuth`: chat/profile/bookmarks/notifications.
- `RequireNonAdmin`: chat routes redirect admin users to `/admin`.
- `RequireAdmin`: eval/admin/document review routes; current web guard checks role `"admin"` and backend enforces protected admin actions.
- Unauthenticated direct navigation redirects to `/login?next=<path>`.
- Non-admin users reaching admin routes redirect to `/chat`.

Important web files:

- `src/App.tsx`
- `src/services/chatApi.ts`
- `src/services/authSession.ts`
- `src/services/adminApi.ts`
- `src/components/chat/ChatContainer.tsx`
- `src/components/sidebar/ConversationSidebar.tsx`
- `src/pages/DocumentReview.tsx`
- `src/pages/AdminPage.tsx`

Web auth behavior:

- Access tokens are kept in memory only.
- Legacy `localStorage.token` / `localStorage.access_token` are read once for migration and removed.
- User cache remains in localStorage.
- Refresh tokens are HttpOnly cookies set by the backend.
- Axios and streaming fetch helpers refresh once on 401 and retry the original request once.
- Chat UI primarily streams via `/chat/stream`; `chatApi.sendMessageV3()` is the non-streaming helper/fallback.
- Admin UI uses `adminApi.ts` for document upload/review, crawler/config/stat endpoints, API-key/env config, and exam-schedule upload/summary/delete.

## 17. Mobile App

Path: `mobile`.

Stack:

- Expo SDK `~54.0.35`
- React Native `0.81.5`
- React `19.1.0`
- React Navigation bottom tabs/native stacks (`@react-navigation/*` v7)
- TanStack Query
- Zustand
- SecureStore
- MMKV (`react-native-mmkv`) when native runtime supports it
- `react-native-sse`
- React Native `StyleSheet` + a custom theme context (`src/theme/theme.tsx`) — **not** NativeWind; the inert `mobile/tailwind.config.ts` has been deleted
- `@rag/shared`
- base API URL from `EXPO_PUBLIC_API_BASE_URL || http://localhost:8000`; Android emulator rewrites `localhost` to `10.0.2.2`

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
- `offlineCache.ts` uses MMKV when available and falls back to an in-memory cache for bookmarks, sessions, and suggestions.
- `pushNotifications.ts` lazy-loads Expo Notifications, registers push tokens through `/notifications/subscribe`, and handles unsupported Android Expo Go cases.

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

Keep these paths synchronized with FastAPI route paths. The shared `/lookup/ctdt` constant is the base segment; helpers append `{major_code}`. Admin-only document/exam-schedule helpers live in the web app service layer rather than the shared package.

## 19. Evaluation

Current evaluation framework: `evaluation/`.

Main suites:

- `evaluation/evaluate.py`: runs the production `RAGPipeline.query_v3()` stack, computes self-eval/judge-vs-gold/retrieval metrics, and writes `query_results.csv`, `summary.json`, and `report.md`.
- `evaluation/run_all.py`: orchestrates configured benchmark runs.
- Routing evals and repair utilities: `evaluate_routing.py`, `retry_failed_eval.py`, `rejudge_eval.py`, `recompute_metrics.py`.
- Post-index eval hooks after crawler/admin indexing.

Important commands:

```bash
python -m evaluation.evaluate
python -m evaluation.evaluate --dataset evaluation/data/hbkkht_rag_dataset.json
python -m evaluation.evaluate --fusion-mode rrf --vector-model dual --retrieval-mode hybrid
python -m evaluation.run_all
```

Common result directories include `evaluation/results`, `evaluation/result_RRF`, `evaluation/result_bge_RRF`, `evaluation/result_e5_RRF`, and `evaluation/result_dual_RRF_*`. There is no active `src/RAG_v2/eval/` package in the current tree; older docs that reference it are stale.

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
- agent model/synthesis/iterations/temperatures/token caps
- Qdrant/Elasticsearch/Mongo/Redis hosts
- collections
- chat model and `chat_max_tokens`
- retrieval top-k/pools/weights/context budgets (incl. `context_total_char_budget_with_expansion`)
- embedding/fusion (`embedding_provider`, `fusion_mode`, `fusion_rrf_k`, BGE/E5 weights)
- reranker thresholds (`reranker_score_threshold`, `reranker_table_score_threshold`)
- expansion flags (parent/sibling/HyDE/score-cliff)
- reflection (`reflection_enabled`/provider/model/temperature)
- domain routing (`domain_routing_enabled`, `domain_confidence_threshold`, `router_mode`)
- self-eval (`self_eval_enabled`, default on)
- Tavily fallback/cache
- LLM-clean defaults and token caps
- structured exam schedule Elasticsearch/index/search settings
- crawler schedule/retention
- rate limiting (`rate_limit_enabled`/`rate_limit_rpm`/`rate_limit_rpd`)
- post-index eval (`post_index_eval_enabled`/command/max-cases)
- Redis/session/cache/history flags
- auth/admin/upload/CORS/API host and port

Do not hard-code provider/model/host values when a setting exists.

Admin LLM config:

- `GET /admin/config/llm` returns effective runtime LLM settings with keys masked.
- `PUT /admin/config/llm` prepares a pipeline reload, persists whitelisted overrides in Mongo, commits the prepared runtime, and invalidates Redis LLM answers when generation tuning changes.
- Startup merges non-empty persisted LLM values and active API keys over `.env`/defaults.
- `/admin/config/api-keys*` manages the active API key registry inside `system_config/llm_config`.
- `/admin/config/env` persists `_id="env_config"`, but startup currently does not apply every stored env key as a process environment override.

## 21. Known Cautions

1. `RAGPipeline` now exposes a public `retrieval_service` property, and `/retrieval/search`, `lookup.py`, `admin_stats.py`, plus the `api/main.py` auto-crawler reuse check all resolve it via `retrieval_service`/`_retrieval_service`, so the shared singleton is reused (no per-request cold-load). Note: `api/MODULE.md` still describes the old `getattr(pipeline, "service", None)` behavior and is stale on this point.

2. `api/routes/session.py` intends `/sessions` and `/sessions/me` by combining router prefix `/session` with route paths `"s"` and `"s/me"`. Keep route behavior covered by tests because this shape is easy to break.

3. `DocumentPipeline.chunk()` still writes a debug chunk dump, but now to a project-relative `data/quydinh/admin_upload` path (no hardcoded absolute path); the dump failure is caught and non-fatal.

4. Redis features are inactive unless both `redis_enabled` and the relevant per-feature flags are true, and should remain fail-soft.

5. `ReActAgent` is now a Planner-Executor graph despite the legacy class name. Do not assume `_route_entry`, `_decompose_node`, a graph-bound ReAct tool loop, or `clarify_question` exists. Valid agent collections include `lich_thi`.

6. Streaming chat ignores `body.mode`, smart-routes internally, and does not run post-generation self-eval/Tavily fallback. Streaming per-request state lives in a request-local namespace; `self.last_*` is mirrored only for single-request debugging and is not authoritative under concurrency.

7. Answer caches are profile-scoped (`major|cohort`). When debugging cache behavior, remember an anonymous request and a profiled request use different keys for the same question.

8. Runtime fusion defaults to RRF. Linear/dual-vector fusion uses max-normalization (not min-max). When changing scoring, re-run the retrieval/eval benchmarks because magnitude is now preserved.

9. `PATCH /admin/config` mutates `app.state.settings`, but does not recreate the rate limiter or crawler scheduler. `/admin/config/env` persists `env_config`, but startup does not apply every env key.

10. Web routes no longer include `/trace` or `/retrieval`; route-level trace/retrieval diagnostics in older docs are stale.

11. There is no active `src/RAG_v2/eval/` package. Use `evaluation/`; `evaluation/MODULE.md` and some eval helper docs may lag the current scripts.

12. Root `README.md`, some `MODULE.md` files, and a few code docstrings may lag behind source and this file for current runtime behavior.

## 22. High-Level Mental Model

```text
Client asks question
  -> FastAPI resolves auth/session/user_context
  -> RAGPipeline.query_v3/query_stream smart-routes
     -> chitchat: direct local response
     -> simple: classic RAG
     -> complex: LangGraph Planner-Executor agent
        -> maybe structured lich_thi exam-schedule lookup
        -> fallback to classic RAG when allowed and agent fails/disabled
  -> RetrievalService searches Qdrant + Elasticsearch, or exam ES for lich_thi
  -> BGE reranker selects grounded context
  -> validity/reference/parent-context post-processing
  -> DeepSeek classic RAG answer or agent synthesis answer
  -> Mongo/Redis persist logs, sessions, caches
  -> API maps response for web/mobile debug surfaces
```

---

# 23. System Design (Uber/Airbnb-style)

This section presents `RAG_v2` the way a system-design write-up frames Uber or Airbnb: start from requirements and scale, draw the architecture top-down, walk the critical request paths, then reason about data, latency, scaling, failure, and trade-offs. Everything here is grounded in the source sections above.

## 23.1 Problem Statement

> Build a HUST academic assistant that answers a student's question over the university's own curriculum, regulations, schedules, student-handbook corpora, and structured exam schedules — accurately, with citations, in Vietnamese — across web and mobile, while letting admins keep the knowledge base fresh through document upload, exam-schedule upload, and automated crawling.

The hard parts are the same shape as a marketplace: **a read-heavy, latency-sensitive query path** (the rider requesting a trip / a student asking a question) sitting on top of **a slower write/ingestion path** (driver onboarding / listing creation = admin document, exam schedule, and crawler ingestion), with a **matching/ranking core** (dispatch / search ranking = hybrid retrieval + rerank) and **strict trust constraints** (don't hallucinate; cite official sources only).

## 23.2 Requirements

### Functional

| # | Requirement | Where it lives |
| --- | --- | --- |
| F1 | Answer NL questions grounded in official vector corpora (`ctdt`, `quydinh`, `kehoach`, `stsv`) with citations. | `RAGPipeline.query_v3` → classic RAG flow |
| F2 | Handle complex/multi-source/comparison questions with planning + parallel execution. | LangGraph Planner-Executor agent |
| F3 | Stream answers token-by-token for responsiveness. | `/chat/stream` SSE |
| F4 | Personalize using authenticated student profile (major, cohort, semester). | `UserContext` → `QueryReflector` |
| F5 | Optionally fall back to official web search for fresh/dynamic questions. | Tavily pre/post-generation |
| F6 | Admin upload → convert → clean → chunk → review → index lifecycle. | `DocumentPipeline` |
| F7 | Automated crawl → stage → human review → index of official sources. | `scripts/auto_crawler.py` |
| F8 | Auth (Microsoft OAuth + manual), sessions, history, bookmarks, feedback, notifications. | `auth/*`, route handlers |
| F9 | Admin observability: usage/query/agent/feedback/eval dashboards + per-request trace/debug payloads. | `/admin/stats/*`, `/metrics/*`, chat/admin debug surfaces |
| F10 | Structured exam-schedule upload/search for concrete subject/date/room questions. | `/admin/exam-schedules*`, agent `lich_thi` |

### Non-functional

| Goal | Target / behavior |
| --- | --- |
| **Latency** | Chitchat near-instant; simple RAG p50 ≈ 2–4 s; complex/agent p50 ≈ 6–15 s; first streamed token < 3 s. |
| **Accuracy / trust** | No ungrounded claims; cite official docs; supersession-aware (drop outdated regulations). |
| **Availability** | Fail-soft: Redis/Tavily/agent degrade gracefully to classic RAG + Mongo. |
| **Freshness** | Daily crawl; admin can hot-reload validity registry and LLM config without restart. |
| **Cost** | Local embed/rerank/agent models; paid LLM (DeepSeek/Gemini) only on the generation/synthesis hop; answer cache to suppress repeats. |
| **Security** | JWT access tokens (in-memory web / SecureStore mobile), rotating refresh tokens, RBAC admin guards, HUST-email gating. |

## 23.3 Scale & Capacity (back-of-envelope)

HUST ≈ 35k students. The load is **extremely peaky** — flat most of the year, then spikes hard during course-registration windows and exam/graduation periods (the academic analogue of Uber's Friday-night surge).

| Quantity | Estimate | Reasoning |
| --- | --- | --- |
| Registered users | ~35k | student body |
| Peak DAU | ~8k | registration week |
| Peak QPS (chat) | ~5–15 req/s | 8k users × ~5 questions over a few busy hours, bursty |
| Read:write ratio | ~1000:1 | queries vastly outnumber admin ingestion / crawls |
| Corpus size | thousands of chunks across 4 domains | `data/*/chunks/*.json` |
| Vector index | chunks × 2 named vectors × 1024-dim float | Qdrant `bge_m3` + `e5` |
| Tokens / answer | input ~3–12k chars context, output ≤ 1500 tok | `context_total_char_budget`, `chat_max_tokens` |
| Storage hot set | Mongo (sessions/turns/logs) + Qdrant + ES | all comfortably single-node at this scale |

**Implication:** this is a *single-region, single-digit-QPS, read-heavy* system. The dominant cost is **not** request throughput — it's **per-request compute latency** (embedding + ANN search + cross-encoder rerank + LLM generation). So the design optimizes the *depth* of one request (caching, routing cheap paths away from expensive ones, pooling/serializing the GPU-bound reranker) rather than horizontal sharding.

## 23.4 Architecture — C4 Context View

```text
                         ┌──────────────────────────────────────────────┐
        Students         │                  CLIENTS                       │
     ───────────────▶    │  Web SPA (React/Vite)   Mobile (Expo/RN)        │
                         │      └──────────── @rag/shared ────────────┘   │
                         └───────────────────────┬────────────────────────┘
                                                 │ HTTPS / SSE  (JWT bearer)
                                                 ▼
                         ┌──────────────────────────────────────────────┐
        Admins           │              FastAPI BACKEND (api/main.py)     │
     ───────────────▶    │  auth · chat · session · admin · metrics       │
                         │  RAGPipeline (singleton) · Planner-Executor     │
                         └───┬───────┬───────┬───────┬───────┬────────────┘
                             │       │       │       │       │
              ┌──────────────┘   ┌───┘   ┌───┘   ┌───┘   └────────────┐
              ▼                  ▼       ▼       ▼                     ▼
        ┌──────────┐      ┌──────────┐ ┌──────┐ ┌───────┐      ┌──────────────┐
        │  Qdrant  │      │Elastic-  │ │MongoDB│ │ Redis │      │  External    │
        │ (vectors)│      │ search   │ │(state)│ │(cache)│      │  LLM / Web   │
        │ bge_m3,e5│      │BM25+exam │ │       │ │opt.   │      │ DeepSeek ·   │
        └──────────┘      └──────────┘ └───────┘ └───────┘      │ Gemini ·     │
                                                                 │ Tavily · MS  │
        Local GPU/CPU models: BGE-M3, E5, BGE-reranker,          │ OAuth        │
        local agent LLM (Qwen via LM Studio/Ollama)              └──────────────┘
```

## 23.5 Architecture — Container / Component View

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ FastAPI app (one process, models loaded once into app.state)                  │
│                                                                               │
│  HTTP layer        api/routes/* ── response_mapper ── schemas (Pydantic)      │
│  Auth              routers/auth + auth/{jwt,microsoft,password,refresh,rbac}  │
│                                                                               │
│  ┌─────────────────────── RAGPipeline (singleton) ────────────────────────┐  │
│  │                                                                         │  │
│  │  query_v3 (smart router)                                                │  │
│  │     │                                                                   │  │
│  │     ├─ chitchat ─▶ canned local handler (no retrieval)                  │  │
│  │     │                                                                   │  │
│  │     ├─ simple  ─▶ rag_flow() ──────────────┐                            │  │
│  │     │                                       │                           │  │
│  │     └─ complex ─▶ query_agent()             │                           │  │
│  │                     │ ReActAgent            │                           │  │
│  │                     │ (Planner-Executor)    │                           │  │
│  │                     │  plan▸execute?▸       │                           │  │
│  │                     │  (lich_thi/web?)▸     │                           │  │
│  │                     │  synthesize           │                           │  │
│  │                     └──────────┬────────────┘                           │  │
│  │  Query layer:                  │                                        │  │
│  │   ComplexityRouter · QueryRouter · DomainClassifier · QuerySignals      │  │
│  │   CollectionSelector · QueryReflector · Structured query/course catalog  │  │
│  │                                │                                        │  │
│  │                                ▼                                        │  │
│  │  RetrievalService ──▶ MultiCollectionSearch                             │  │
│  │     BGE-M3 + E5 embed ─▶ per-collection {Qdrant ANN ∥ ES BM25}          │  │
│  │     ─▶ fusion (RRF default / max-norm linear) ─▶ BGE rerank             │  │
│  │     Structured exam lookup: lich_thi ─▶ ES exam_schedules               │  │
│  │     ─▶ ValidityFilter ─▶ ReferenceResolver ─▶ parent-context expand     │  │
│  │                                │                                        │  │
│  │                                ▼                                        │  │
│  │  LLM (DeepSeek classic / Gemini synthesis) ─▶ optional SelfEvaluator    │  │
│  │                                                                         │  │
│  └─────────────────────────────────────────────────────────────────────────┘
│                                                                               │
│  Ingestion (write path, off the hot path):                                    │
│    DocumentPipeline   upload▸convert▸clean▸llm-clean?▸chunk▸review▸index      │
│    auto_crawler       crawl▸stage▸admin-review▸index_staged_crawler_run       │
│    exam_schedules     upload▸parse▸Mongo+ES structured index                  │
│                                                                               │
│  Persistence/cache adapters: MongoLogger (sync) · Motor (async) · RedisMgr    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key structural decision:** one heavyweight `RAGPipeline` is built at startup (it loads embedders, reranker, agent LLM client) and shared across all requests. It owns exactly one `RetrievalService`, which the agent adapters reuse via `inject_from_retrieval_service()` — no per-request model loading, no duplicate vector clients. This is the system's "stateful worker" equivalent of keeping the dispatch engine warm.

## 23.6 The Hot Path — Chat Request Lifecycle

```mermaid
sequenceDiagram
    participant C as Client (web/mobile)
    participant API as FastAPI /chat(.v3)
    participant CR as ComplexityRouter
    participant P as RAGPipeline
    participant R as RetrievalService
    participant Q as Qdrant
    participant E as Elasticsearch
    participant RR as BGE Reranker
    participant L as LLM (DeepSeek)
    participant M as Mongo / Redis

    C->>API: POST /chat/v3 (question, JWT, session_id)
    API->>API: resolve identity (JWT) + UserContext + history
    API->>P: query_v3(question, profile, history)
    P->>P: reflect question once
    P->>CR: route(reflected question)
    alt chitchat
        CR-->>P: tier=chitchat
        P-->>API: canned answer (no retrieval)
    else simple
        CR-->>P: tier=simple
        P->>P: classic RAG route ▸ reflect/select ▸ entities ▸ filters
        P->>R: hybrid search (BGE-M3 + E5 query)
        par per collection
            R->>Q: vector ANN (named vectors)
            R->>E: BM25 keyword
        end
        R->>R: fuse (RRF default / max-norm linear) + kehoach recency
        R->>RR: rerank candidates (serialized by lock)
        R-->>P: validity ▸ reference ▸ parent-context
        P->>L: generate (grounded context)
        opt self-eval / web fallback enabled
            P->>L: self-evaluate; maybe Tavily enrich
        end
        P-->>API: answer + trace
    else complex
        CR-->>P: tier=complex
        P->>P: query_agent() → Planner-Executor
        Note over P,R: plan ▸ execute (parallel retrieval or lich_thi) ▸ synthesize
        P-->>API: synthesized answer + agent_trace
    end
    API->>M: persist turn, query_log, agent_trace; cache stable answers
    API-->>C: ChatResponse (answer, sources, route, timings, trace)
```

**Streaming variant (`/chat/stream`)** reflects and complexity-routes once, then serves whichever tier matches: chitchat uses the LLM streaming flow, simple RAG runs retrieval (with optional *pre*-generation web enrichment) and streams tokens, and complex emits `status` progress while the agent runs synchronously and its synthesized answer is chunk-animated. The frame sequence is `session → (status*) → token* → metadata → done`, with `: heartbeat` comments on idle. It deliberately skips post-generation self-eval/Tavily on every path so the token stream is never blocked.

## 23.7 Latency Budget (simple RAG, warm process)

```text
  identity/session resolve         ~5–20 ms   (Mongo/Redis lookups)
  Tier-1 route + complexity        ~10–50 ms  (regex + calibrated classifier, cached)
  query reflection                 ~1–3 s     (LLM rewrite to a standalone query; skippable)
  reflected reroute (domain)       ~10–50 ms, +1–3 s if Tier-3 LLM escalates on low confidence
                                              (canonical domain decision; raw-query Tier-3 removed)
  embed query (BGE-M3 + E5)        ~20–80 ms  (GPU) / higher on CPU
  Qdrant ANN ∥ ES BM25             ~30–120 ms (parallel per collection)
  fusion + dedup                   ~5–20 ms
  BGE cross-encoder rerank         ~100–500 ms (GPU-bound, SERIALIZED via BGEReranker.rerank self._lock)
  validity/reference/parent expand ~10–60 ms  (extra Qdrant fetch for parents)
  LLM generation (DeepSeek)        ~1–3 s     (dominant; network + decode)
  ─────────────────────────────────────────
  persist/cache (async/after)      off critical path where possible
```

The two structural hot spots are the **reranker** (GPU-bound and serialized inside `BGEReranker.rerank` via `self._lock`) and the **LLM generation hop** (external, network-bound). Everything in the query layer is engineered to *avoid reaching the expensive hops unnecessarily*: chitchat short-circuits before retrieval; the answer cache short-circuits before the LLM; routing keeps simple questions out of the multi-LLM agent.

## 23.8 Data Model & Storage Choices

Polyglot persistence, each store chosen for a distinct access pattern — the same instinct as Uber splitting trip state, geo-index, and analytics across different engines.

| Store | Holds | Why this engine | Access pattern |
| --- | --- | --- | --- |
| **Qdrant** | chunk embeddings, 2 named vectors (`bge_m3`,`e5`) × 1024-dim, cosine; one collection per domain; payload metadata | purpose-built ANN with named vectors + payload filtering (`HasIdCondition`) | semantic recall per query |
| **Elasticsearch** | per-collection BM25 indexes plus structured `exam_schedules`, Vietnamese analyzer (folding, stopwords, synonyms), field boosts | lexical/keyword recall + metadata-only filtering + structured exam lookup | keyword recall + ID prefilter + exam rows |
| **MongoDB** | 19 practical collections: users, sessions, turns, query_logs, agent_traces, documents, document_chunks, feedback, notifications, crawler_runs/chunks, exam_schedules, system_config, refresh_tokens, eval_runs/case_results, bookmarks, … | flexible document state, durable system-of-record, analytics aggregations | OLTP + dashboard aggregation |
| **Redis** (optional, fail-soft) | sessions, conversation history, LLM answer cache (+doc tag reverse-index), sliding-window rate limits | low-latency ephemeral cache & counters | hot reads + invalidation |
| **LocalStorage (disk)** | uploaded PDF/DOCX files, exam schedules, converted markdown, `data/*` corpora, `document_lineage.json` | large blobs / curated corpus & lineage | ingestion-time |

**Source-of-truth split:** Mongo is durable truth for state; Redis is a fail-soft accelerator (if Redis dies, sessions/history fall back to Mongo and caching/rate-limit is bypassed — never a hard failure). `data/document_lineage.json` is truth for supersession (the `ValidityFilter` drops outdated regulations so a 2023 rule never shadows its 2025 replacement).

## 23.9 The Write/Ingestion Path (the "supply side")

Two human-gated pipelines keep the knowledge base trustworthy. Both end at the same indexing primitive (embed → Qdrant + ES) but require **admin review before anything becomes retrievable** — the trust analogue of listing verification before a property goes live.

```text
ADMIN DOCUMENT UPLOAD                 AUTO-CRAWLER
  PDF/DOCX                              crawl ctt.hust.edu.vn (kehoach/quydinh/baiviet)
   ▼ convert (pymupdf4llm/docling/...)   ▼ clean/extract/chunk
  markdown → review                     stage → Mongo crawler_runs/crawler_chunks (PENDING)
   ▼ clean → review                      ▼ admin review/edit  ◀── human gate
  cleaned md                            index_staged_crawler_run()
   ▼ optional LLM-clean → review         ▼ embed (BGE-M3+E5) → Qdrant + ES
   ▼ chunk                               ▼ append archive · invalidate LLM cache
  Mongo document_chunks                  ▼ post-index eval · notify users
   ▼ approve/select  ◀── human gate
  embed_and_index() → Qdrant + ES
  status: uploaded→…→indexed (rollback-capable)

EXAM SCHEDULE UPLOAD
  PDF/XLSX/XLSM
   ▼ parse HUST 13-column rows
  Mongo exam_schedules
   ▼ index when ES available
  Elasticsearch exam_schedules
```

Direct crawler auto-indexing is intentionally disabled; everything routes through the admin review/index endpoints. `is_indexable_chunk()` keeps parent/header chunks out of retrieval slots while still storing parents in Qdrant for post-rerank context expansion. Exam schedule rows are structured search data, not vector chunks.

## 23.10 Scaling Strategy & Bottlenecks

Because load is single-digit QPS but compute-heavy, scaling is mostly **vertical + careful concurrency**, with clear horizontal seams when the peak arrives.

| Bottleneck | Symptom at peak | Mitigation in code today | Next step to scale 10× |
| --- | --- | --- | --- |
| **Cross-encoder reranker** (GPU, serialized via `BGEReranker.rerank` `self._lock`) | rerank queue grows; tail latency spikes | single warm model, instance lock serializes GPU access, `reranker_min_top_k` floor | dedicate a rerank micro-service with a request queue + batching; multiple GPU replicas behind it |
| **LLM generation hop** (external) | p95 dominated by DeepSeek/Gemini RTT | answer cache (`use_redis_cache`), streaming hides latency, temperature 0 for determinism/cacheability | provider failover, request hedging, semantic cache |
| **Single FastAPI process holding the pipeline** | one process = one warm model set | models in `app.state`, heavy load in executor at startup | run N stateless API replicas, each with its own warm pipeline, behind a load balancer; externalize sessions to Redis (already supported) |
| **Embedding throughput** (GPU/CPU) | embed latency on CPU-only hosts | query-embedding LRU cache (512), batch embed in ingestion | GPU host or batched embedding service |
| **Qdrant / ES** | comfortable at this corpus size | per-collection isolation, parallel search | Qdrant replication/sharding, ES replicas — only needed at much larger corpora |
| **Mongo aggregation for dashboards** | admin stats heavy queries | `$percentile` gated by server-version check; indexed fields | read replica / pre-aggregated metrics rollups |

**Statelessness:** the API tier is *almost* stateless — the only per-process state is the warm model set (acceptable, replicate it) and the in-process retrieval/search caches (best-effort). Sessions, history, and rate limits already have a Redis-backed mode, so horizontal API scale-out mainly needs Redis turned on and sticky-less routing.

## 23.11 Resilience & Failure Modes (fail-soft everywhere)

| Dependency fails | System behavior |
| --- | --- |
| Redis down | Sessions/history → Mongo; LLM cache + rate limit bypassed. No hard failure. |
| Tavily / web | Enabled by default only when a valid key and trigger are present; when failing, skipped — answer proceeds from internal corpus. |
| Agent / local agent LLM | Complex path falls back to classic RAG (unless `require_agent=True`); `/chat` returns 503 only when agent explicitly forced and disabled, `/chat/v3` returns RAG fallback with `agent_error`. |
| LLM provider error | Retries with backoff; context-size errors trigger reduced-context retry. |
| Mongo down | Logging/persistence degrades; chat can still answer (state not durably saved). |
| Reranker low recall | HyDE fallback re-queries with a hypothetical answer; fusion fallback to original/raw question. |
| Stale/superseded docs | `ValidityFilter` + `document_lineage.json` exclude them. |

Hot-reconfiguration without downtime: `prepare_llm_config_reload()` builds replacement runtime components, then `commit_llm_config_reload()` hot-swaps them under a lock and re-injects the shared retrieval service into agent adapters — admins retune models live.

## 23.12 Security & Trust Design

- **Identity:** Microsoft OAuth gated to `@sis.hust.edu.vn`, plus manual register/login. Authenticated identity always overrides body-supplied `user_id`/`user_context` (legacy/dev inputs).
- **Tokens:** short-lived JWT access tokens — **in-memory only on web**, **SecureStore on mobile**; rotating refresh tokens hashed in Mongo with reuse/revocation family detection. Web gets the refresh token as an **HttpOnly cookie**; mobile gets it in **JSON** via `client_type="mobile"`. Both clients single-flight a refresh on 401 and retry once.
- **Authorization:** `require_admin`/superadmin guards on admin upload/stats/config/crawler; superadmin set by `SUPERADMIN_USER_IDS`, not a DB role alone.
- **Answer trust:** grounded-only generation, citations required, supersession filtering, and an optional self-eval quality gate — the product's core promise is "don't make things up about university rules."
- **Data isolation:** answer caches are keyed with the asking student's `major|cohort` profile so a personalized answer is never served to a different student; `LocalStorage.read_text()` resolves and rejects path-traversal inputs that escape its base directory; admin document ingestion cannot index chunks until `chunks_reviewed=True`.

## 23.13 Key Trade-offs

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Routing | Tiered complexity router (chitchat/simple/complex) gating an agent | Always-agent | Most questions are simple; routing keeps p50 low and cost down, reserving the multi-LLM agent for genuinely hard questions. |
| Retrieval | Hybrid dense+lexical with RRF/default fusion + cross-encoder rerank; structured exam lookup for `lich_thi` | Pure vector search | Vietnamese keyword/code matching and exam rows need BM25/structured search; rerank fixes fusion ordering for grounded prose answers. |
| Models | Local embed/rerank/agent + paid LLM only for final generation/synthesis | All-hosted-API | Cost control; the expensive paid hop is also the most cacheable. |
| Ingestion | Human-in-the-loop review before indexing (documents + crawler) and structured exam-schedule parsing | Auto-index crawled data | Trust: official rules must not be silently wrong; review gate is the safety valve. |
| Caching/sessions | Optional, fail-soft Redis over a durable Mongo source-of-truth | Redis-as-primary | Single-node simplicity with no hard dependency; correctness survives cache loss. |
| Streaming | Retrieval-then-stream, no post-gen self-eval on stream | Full pipeline on stream | First-token latency matters more than post-hoc checks on the interactive path. |

## 23.14 Mapping to the Uber/Airbnb mental model

| Uber / Airbnb concept | This system |
| --- | --- |
| Rider request / guest search (read, latency-critical) | Student chat query (`/chat`, `/chat/stream`) |
| Dispatch / search ranking core | Hybrid retrieval + cross-encoder rerank + fusion |
| Surge pricing / demand spikes | Registration/exam-week query spikes (peaky, bursty) |
| Driver onboarding / listing creation (write, verified) | Admin document pipeline + crawler review→index + exam schedule upload |
| Trust & safety (verification, fraud) | Citation grounding, supersession filter, HUST-email gating, RBAC |
| Trip state store / geo-index / analytics split | Mongo (state) + Qdrant/ES (index) + Redis (cache) + eval/stats |
| Real-time updates | SSE token streaming + push notifications |
| Multi-platform clients sharing logic | Web + mobile over the shared `@rag/shared` TS package |
