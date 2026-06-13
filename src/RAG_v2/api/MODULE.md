# Module: `api`

Source-verified: 2026-06-12 from `api/main.py`, `api/dependencies.py`, `api/response_mapper.py`, `api/schemas.py`, `api/__init__.py`, `api/middleware/rate_limit.py`, `api/services/notification_delivery.py`, and `api/routes/*.py` (chat, health, session, metrics, retrieval, upload, bookmark, feedback, lookup, notification, notification_admin, admin_stats).

## Purpose

`api` is the FastAPI interface layer. It owns app construction, lifespan startup/shutdown, public HTTP routes, streaming SSE, response normalization, request/session dependency helpers, and Redis-backed rate-limit middleware.

It calls into `pipeline`, `models`, `cache`, `retrieval`, `auth`, `scripts`, and `schemas`, but does not contain retrieval or generation logic itself.

## File Map

```text
api/
  __init__.py             Package marker.
  main.py                 FastAPI app factory, lifespan, CORS, router registration, RateLimitMiddleware.
  dependencies.py         Session resolution, history parsing, user-id/user-context helpers, Redis<-Mongo sync.
  response_mapper.py      ChatResponseMapper: pipeline result dict -> ChatResponse / normalized v3 shape.
  schemas.py              Backward-compat shim re-exporting schemas.chat models.
  middleware/
    __init__.py
    rate_limit.py         RateLimitMiddleware wrapping SlidingWindowRateLimiter (chat endpoints only).
  services/
    __init__.py
    notification_delivery.py  DB notification creation + best-effort Expo push delivery.
  routes/
    __init__.py
    chat.py               /chat, /chat/v3, /api/chat/v3, /chat/suggest, /chat/stream
    health.py             /health, /api/admin/reload-validity
    session.py            /session, /session/{id}, /sessions, /sessions/me (prefix /session)
    metrics.py            /metrics/usage, /metrics/eval
    retrieval.py          /retrieval/search diagnostic endpoint (prefix /retrieval)
    upload.py             /admin/documents* pipeline + /admin/converters, /admin/chunkers (prefix /admin)
    bookmark.py           /bookmarks*, /bookmark-folders*
    feedback.py           /feedback, /feedback/list, /feedback/stats
    lookup.py             /lookup/ctdt/{major_code}, /lookup/regulations, /lookup/calendar, /lookup/compare
    notification.py       /notifications* user inbox + subscribe/unsubscribe
    notification_admin.py /admin/notifications, /admin/notifications/broadcast (prefix /admin/notifications)
    admin_stats.py        /admin/stats/*, /admin/users/{id}/status, /admin/crawler/*, /admin/config* (prefix /admin)
```

Ignore `api/.agent/` if present locally; it is not part of the FastAPI runtime.

## App Lifecycle

Entrypoint:

```text
api.main.app = create_app() -> lifespan()
```

Startup in `lifespan()`:

1. Load `.env` from the RAG_v2 root.
2. Build `Settings`.
3. Merge persisted admin LLM overrides from Mongo `system_config` via `_load_persisted_llm_config()` when `mongodb_enabled`.
4. Raise if no `google_api_key` is resolved (env or DB).
5. Initialize `MongoLogger` if `mongodb_enabled`; record `mongo_status` on `app.state`.
6. If `redis_enabled` and ping succeeds: init Redis session store (dual-write), rate limiter, LLM response cache, and conversation history cache per their flags.
7. Store runtime singletons + `settings` on `app.state`.
8. Build one `RAGPipeline` (with `mongo_logger` and optional `llm_cache`) in a thread executor.
9. Create Mongo indexes through `models.database.create_indexes()` when Mongo is up.
10. Run `admin_stats.check_mongo_version()` to gate `$percentile` aggregation features.
11. Schedule a delayed `warmup_llm()` task that invokes the agent LLM with a "hello" (after a 2 s sleep).
12. Optionally schedule `scripts.auto_crawler.AutoCrawlPipeline` via APScheduler cron if `crawler_enabled`.

Shutdown stops the scheduler and closes Redis resources when present.

## Router Registration

`create_app()` includes these routers (CORS allows localhost/LAN dev origins for web/Expo/Android):

| Router file | Prefix | Public surface |
| --- | --- | --- |
| `chat.py` | none | `/chat`, `/chat/v3`, `/api/chat/v3`, `/chat/suggest`, `/chat/stream` |
| `health.py` | none | `/health`, `/api/admin/reload-validity` |
| `session.py` | `/session` | `/session`, `/session/{id}` (GET/DELETE/PATCH), `/sessions`, `/sessions/me` |
| `metrics.py` | none | `/metrics/usage`, `/metrics/eval` |
| `retrieval.py` | `/retrieval` | `/retrieval/search` |
| `upload.py` | `/admin` | `/admin/documents*`, `/admin/converters`, `/admin/chunkers` |
| `bookmark.py` | none | `/bookmarks*`, `/bookmark-folders*` |
| `feedback.py` | none | `/feedback`, `/feedback/list`, `/feedback/stats` |
| `lookup.py` | `/lookup` | `/lookup/ctdt/{major_code}`, `/lookup/regulations`, `/lookup/calendar`, `/lookup/compare` |
| `notification.py` | none | `/notifications*` user inbox + subscribe/unsubscribe |
| `notification_admin.py` | `/admin/notifications` | `POST /admin/notifications`, `POST /admin/notifications/broadcast` |
| `admin_stats.py` | `/admin` | `/admin/stats/*`, `/admin/users/{id}/status`, `/admin/crawler/*`, `/admin/config*` |
| `routers/auth.py` | `/auth` | auth/login/callback/register/refresh/me/logout/admin endpoints |

`create_app()` also defines `GET /` (service banner).

`RateLimitMiddleware` is registered unconditionally at build time (inside `create_app()`), before the app starts — Starlette forbids `add_middleware` after startup. The actual `SlidingWindowRateLimiter` instance is resolved lazily from `app.state` per request during lifespan; the middleware is a transparent pass-through until Redis is ready.

## Module Flow

```mermaid
flowchart TD
  Client["web/mobile/API client"] --> FastAPI["api/main.create_app"]
  FastAPI --> Lifespan["lifespan startup"]
  Lifespan --> Settings["config/Settings + Mongo LLM overrides"]
  Lifespan --> Mongo["models/MongoLogger + Motor indexes"]
  Lifespan --> Redis["cache Redis session/history/LLM/rate limit"]
  Lifespan --> Pipeline["pipeline/RAGPipeline singleton"]
  Lifespan --> Crawler["scripts/auto_crawler APScheduler (optional)"]
  FastAPI --> Routers["api/routes/* and routers/auth.py"]
  Routers --> Auth["auth jwt_handler / rbac"]
  Routers --> Schemas["schemas Pydantic contracts"]
  Routers --> Pipeline
  Routers --> Models["models database collections"]
  Routers --> Upload["pipeline/DocumentPipeline"]
  Routers --> Notify["api/services/notification_delivery"]
  Pipeline --> Mapper["api/response_mapper.ChatResponseMapper"]
  Mapper --> Response["ChatResponse / SSE metadata / JSON"]
  Response --> Client
```

External module boundaries:

- `api` resolves HTTP, auth/session/user context, request validation, and response mapping; it does not embed, retrieve, rerank, or generate directly.
- `pipeline` owns chat (`RAGPipeline`) and document (`DocumentPipeline`) orchestration; `models`/`cache` own persistence/cache.
- `auth.jwt_handler` (`get_current_user`, `get_optional_current_user`) and `auth.rbac.require_admin` own credentials and RBAC dependencies used by protected routes.
- `scripts.auto_crawler` owns crawl/stage/index work invoked by the scheduler and admin crawler endpoints.
- `schemas` (`chat`, `mobile`, `document`, `constants`) are the contract boundary with web/mobile/shared clients.

## Chat Routes

`routes/chat.py` is the main runtime API.

- `POST /chat` (`response_model=ChatResponse`): routes by `mode` — `agent` → `pipeline.query_agent(require_agent=True)`, `rag` → `pipeline.query`, else (`auto`) → `pipeline.query_v3`. Maps via `ChatResponseMapper.to_chat_response`.
- `POST /chat/v3` and `POST /api/chat/v3`: same mode control, returns the normalized v3 dict (`normalize_v3_result`). When `mode=agent` but the agent is disabled, returns a RAG fallback with `agent_error="Agent is disabled"` — no 503 raised.
- `GET /chat/suggest`: lightweight suggested questions personalized by `cohort`/`major` query params or the authenticated profile.
- `POST /chat/stream`: SSE streaming via `pipeline.query_stream`.

`_log_legacy_turn_for_agent_response()` backfills legacy turn/query logs for agent answers so `/chat` history stays consistent with classic RAG logging.

Authenticated requests use `get_optional_current_user`. When a Bearer JWT is valid, `user_id` and `user_context` derive from the DB user (`user_id_from_user`, `user_context_from_user`); body-supplied identity fields are legacy fallbacks.

SSE event contract (`POST /chat/stream`):

```text
{"type":"session","session_id":"..."}           # first frame; sent before pipeline work starts
{"type":"status","stage":"...","message":"..."}  # progress events (agent retrieval/synthesis stages)
{"type":"token","delta":"..."}                   # one per answer token chunk (str)
{"type":"error","error":"..."}                   # on producer failure; does not close stream
{"type":"metadata", ...}                         # built from per-request metadata_out dict (NOT pipeline singletons)
{"type":"done"}                                  # always last
```

Metadata is collected from the `request_metadata` dict passed to `pipeline.query_stream` as `metadata_out=`. This is per-request, not from `pipeline.last_*` attributes — the design avoids a data race when concurrent streams run against the same pipeline singleton.

`: heartbeat` SSE comment frames are emitted every ~15 s of idle to keep proxies from closing long agent runs.

Pipeline work is sync/heavy, so routes use `anyio.to_thread.run_sync()` (or a thread executor producing into an `asyncio.Queue` for streaming) to avoid blocking the event loop.

## Response Mapping

`response_mapper.py` exposes `ChatResponseMapper` (all `@staticmethod`) to normalize heterogeneous pipeline outputs:

- `to_chat_response` / `normalize_v3_result` — build the `ChatResponse` model / stable v3 dict.
- `_to_retrieved_documents` + per-doc mapping → `RetrievedDocument`.
- `to_filter_models` → `FilterInfo`; `to_collection_result_models` → `CollectionResult`.
- `to_tool_call_models` → `AgentToolCall`; `to_agent_trace_model` → `AgentTracePayload`.
- `_safe_float`/`_optional_float`/`_optional_int`/`_to_string_list`/`_optional_dict(_list)` parse loosely shaped metadata.
- Backfills `tools_used`/`tool_calls` from `agent_trace` when top-level fields are empty.

When changing pipeline output fields, update mapper tests and frontend/mobile normalizers.

## Admin Document Routes (`routes/upload.py`)

Admin-only (`require_admin`), wraps a module-level `DocumentPipeline` singleton (`_get_pipeline()`, lazy-init). Background steps return **202 Accepted** and update `DocumentRecord.status` asynchronously.

- `POST /admin/documents` (201) upload PDFs; `GET /admin/documents` list; `GET /admin/documents/{id}` detail; `DELETE /admin/documents/{id}` delete + cleanup.
- `POST /admin/documents/{id}/rollback` revert to previous state (not allowed when status is `uploaded`).
- `POST /admin/documents/{id}/convert` (PDF→Markdown, `converter` query param: `pymupdf4llm`|`docling`, default `pymupdf4llm`), `clean`, `chunk`, `index`, `pipeline` — background 202.
- `GET/PUT /admin/documents/{id}/markdown` and `/cleaned` review+approve.
- `GET /admin/documents/{id}/chunks` (paginated, filterable by `strategy`), `PATCH/DELETE .../chunks/{chunk_id}` staged chunk content/delete review (only when status in `{chunked, failed}`), `GET .../chunk-strategies`, `POST .../chunks/select` (finalize strategy, deletes others), `PUT .../chunks` (approve chunks). `POST .../index` requires `chunks_reviewed=True`.
- `GET /admin/converters`, `GET /admin/chunkers` discovery.

After indexing or deletion, `_invalidate_search_caches()` clears both the agent's in-memory RAG cache (`agent.tool_adapters.cache_clear`) and the Redis LLM response cache (`llm_cache.invalidate_all`) to prevent stale answers.

## Admin Stats & Config (`routes/admin_stats.py`)

Admin-only (`require_admin`), prefix `/admin`. Owns the observability dashboard, user management, crawler review, and LLM/runtime config surfaces.

- Stats: `GET /admin/stats/overview`, `/admin/stats/users`, `/admin/stats/users/breakdown`, `/admin/stats/queries`, `/admin/stats/agent`, `/admin/stats/feedback/topics`, `/admin/stats/system`. `$percentile` latency is gated by `_MONGO_SUPPORTS_PERCENTILE` (set at startup by `check_mongo_version`; requires MongoDB ≥ 7).
- Users: `PATCH /admin/users/{user_id}/status` activate/deactivate (blocks self-deactivation, writes audit log).
- Crawler review: `POST /admin/crawler/trigger` (cooldown 60 s + single-run lock via `_crawl_lock`/`_crawl_executor`; target `all|kehoach|quydinh`), `GET /admin/crawler/status` (running state + pending/indexed runs + last result), `GET /admin/crawler/runs/{run_id}/chunks`, `PATCH /admin/crawler/runs/{run_id}/chunks/{chunk_id}` (editable when status in `CRAWLER_EDITABLE_STATUSES`), `POST /admin/crawler/runs/{run_id}/index` (transitions to `indexing`, calls `scripts.auto_crawler.index_staged_crawler_run` in thread). Completed crawls broadcast a notification via `notification_delivery.broadcast_user_notification` only when new article data or article links are present.
- Runtime toggles: `PATCH /admin/config` toggles whitelisted boolean settings on `app.state.settings` in-process only — **not persisted to DB**. Allowed keys: `agent_enabled`, `self_eval_enabled`, `tavily_fallback_enabled`, `crawler_enabled`, `reflection_enabled`, `domain_routing_enabled`, `rate_limit_enabled`.
- LLM config: `GET /admin/config/llm` (API keys masked `key[:4]***key[-4:]`); `PUT /admin/config/llm` prepares a pipeline LLM reload (`pipeline.prepare_llm_config_reload`), persists overrides to `system_config` and API key rows to Mongo, commits the prepared runtime (`pipeline.commit_llm_config_reload`), and invalidates the Redis LLM cache when chat-generation fields (`llm_provider`, `chat_model`, `chat_temperature`, `chat_max_tokens`) change.
- API keys: `GET /admin/config/api-keys`, `POST /admin/config/api-keys`, `POST /admin/config/api-keys/{key_id}/activate` manage secret-free DeepSeek/Google/Tavily key rows with hot-swap of runtime LLM clients (prepare + commit two-phase pattern).
- Env config: `GET /admin/config/env` and `PUT /admin/config/env` edit a whitelist of retrieval/crawler/rate-limit/chat/self-eval/Tavily settings at runtime; changes are applied to `app.state.settings` and persisted to `system_config` collection (`_id="env_config"`).

## Retrieval Diagnostic (`routes/retrieval.py`)

`POST /retrieval/search` (`RetrievalRequest` → `RetrievalResponse`), admin-only (`require_admin`). Runs embed (`service.embed_query`) → hybrid search (`service.searcher.search`) → optional rerank (`service.reranker.rerank`) directly against the pipeline's shared retrieval service (accessed via `pipeline.retrieval_service` / `pipeline._retrieval_service`), returning mapped docs, applied filters, collection counts, fusion weights, and latency. The endpoint explicitly prohibits constructing a new `RetrievalService` per request.

## Notifications

User notification routes (`routes/notification.py`) require a valid access token (`get_current_user`). Inbox: list (paginated, optional `unread_only`), unread-count, mark-read, mark-all-read, delete. Subscribe: `POST /notifications/subscribe` stores an Expo push token + topic list (upsert). Unsubscribe: `POST /notifications/unsubscribe` removes topics or deletes the subscription entirely.

`api/services/notification_delivery.py` is the shared delivery boundary for admin/system-created notifications. `broadcast_user_notification` resolves target users (by topic subscription or all users when topics are empty), inserts Mongo notification rows, then calls `send_expo_push_notifications` which batches Expo push messages (`https://exp.host/--/api/v2/push/send`, 100 per batch, 5 s timeout) and prunes `DeviceNotRegistered` tokens via `delete_many` without failing DB creation. Push is controlled by `PUSH_NOTIFICATIONS_ENABLED` env var (default `true`).

Admin notification routes (`routes/notification_admin.py`) require `require_admin` and create topic-scoped or broadcast notifications by delegating to `broadcast_user_notification`.

## Session Routes (`routes/session.py`)

Reads Redis first, then Mongo. Preserves legacy owner aliases — canonical Mongo `_id`, `email`, `username`, `student_id` — so old sessions remain readable/owned. Endpoints:

- `POST /session` create (auth optional; body `{"user_id": ...}` legacy fallback).
- `GET /session/{id}` get with turns (turns always fetched from Mongo; readable by sessions without an owner).
- `GET /sessions?user_id=` list for a user (auth required; `user_id` must match caller's aliases — IDOR protection).
- `GET /sessions/me` list for authenticated user (merges across all owner aliases, deduplicates by `session_id`, sorts by `updated_at`).
- `PATCH /session/{id}` update title (auth required; ownership enforced; title truncated to 120 chars).
- `DELETE /session/{id}` delete (auth required; ownership enforced).

## Rate Limiting (`middleware/rate_limit.py`)

`RateLimitMiddleware` applies only to `POST /chat`, `/chat/v3`, `/api/chat/v3`, `/chat/stream`.

Identity is resolved in priority order:
1. `sub` claim from a valid Bearer JWT (cannot be spoofed by the caller).
2. First hop of `X-Forwarded-For` (reverse proxy).
3. Direct client IP.

The request body is **not** read for identity — doing so in `BaseHTTPMiddleware` can deadlock the downstream handler, and a body-supplied `user_id` is trivially spoofable.

Returns 429 with `Retry-After` header when exceeded. On success, injects `X-RateLimit-Limit-Minute`, `X-RateLimit-Remaining-Minute`, `X-RateLimit-Limit-Day`, `X-RateLimit-Remaining-Day` headers. When the limiter is unavailable (Redis down) the middleware is a transparent pass-through.

## Maintenance Notes

- `api/schemas.py` is a shim only — all real schema definitions live in `schemas/chat.py`. Do not add new schemas here.
- `_get_pipeline()` in `upload.py` and `_get_storage()` are module-level singletons that lazily build a separate `DocumentPipeline` from a fresh `Settings()`. They share embedders with the RAG pipeline only via `app.state.pipeline` in the `_bg_index` background task (passed as `app` argument).
- `admin_stats.py` holds module-level mutable state for crawler concurrency control: `_crawl_running`, `_last_trigger_time`, `_last_manual_crawl`, `_crawl_lock`, `_crawl_executor`. These are in-process only; a multi-process deployment would need an external lock.
- `_MONGO_SUPPORTS_PERCENTILE` is a module-level bool set at startup in `admin_stats.py`. If the startup `check_mongo_version` call fails, it defaults to `False` and `$percentile` aggregation is silently skipped in latency analytics.
- The `CORS` allowlist is hardcoded in `create_app()`: `localhost:5173`, `8080`, `19006`, `8081`, `10.0.2.2:8000`, plus a regex covering `localhost`, `127.0.0.1`, `10.0.2.2`, and `192.168.*.*` origins. Update there when adding new dev/staging origins.

## Useful Checks

```bash
python -m py_compile api/*.py api/routes/*.py api/middleware/*.py api/services/*.py
python -m pytest tests/test_chat_route_mode.py tests/test_response_mapper.py tests/test_upload_api.py tests/test_dependencies.py -q -m "not integration"
```
