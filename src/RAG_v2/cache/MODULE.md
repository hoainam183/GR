# Module: `cache`

Source-verified: 2026-05-20 from `cache/*.py` and `api/main.py`.

## Purpose

`cache` contains optional Redis infrastructure for sessions, short chat history, LLM response cache, and sliding-window rate limiting. The module is fail-soft: when Redis is disabled or unavailable, the backend should continue through MongoDB or bypass caching.

Redis is controlled by `Settings.redis_enabled` plus per-feature flags.

## File Map

```text
cache/
  redis_client.py    RedisManager connection wrapper and health checks.
  session_store.py   RedisSessionStore for session metadata/list with Mongo dual-write.
  history_cache.py   ConversationHistoryCache for recent chat messages.
  llm_cache.py       LLMResponseCache for pre-retrieval and post-retrieval answer cache.
  rate_limiter.py    SlidingWindowRateLimiter using Redis sorted sets.
```

## Runtime Ownership

`api/main.py:lifespan()` creates Redis resources and stores them on `app.state`:

- `app.state.redis_session`
- `app.state.llm_cache`
- `app.state.history_cache`
- `app.state.rate_limiter`
- `app.state.redis_status`

`MongoLogger.history_cache` can be set so turns written to Mongo also warm Redis history.

## Redis Key Contracts

| Key pattern | Type | Purpose |
| --- | --- | --- |
| `session:{sid}` | Hash | Session metadata. |
| `user_sessions:{uid}` | ZSet | User session list, score is updated timestamp. |
| `history:{sid}` | List | Recent user/assistant messages. |
| `llm_cache:{sha}` | Hash | Post-retrieval answer cache keyed by query/docs/model. |
| `llm_cache:q:{sha}` | Hash | Query-only pre-retrieval cache. |
| `llm_cache:stats` | Hash | Cache hit/miss counters. |
| `doc_cache_tag:{did}` | Set | Reverse index from document id to cache keys. |
| `rate:min:{id}` | ZSet | Requests-per-minute sliding window. |
| `rate:day:{id}` | ZSet | Requests-per-day sliding window. |

## Session Store

`RedisSessionStore`:

- Creates `session_id` and writes session metadata to Redis.
- Dual-writes the same session to Mongo through `MongoLogger` when available.
- Lists sessions by `user_sessions:{uid}` sorted set.
- Cleans stale sorted-set members when the session hash expired.
- `sync_from_mongo(session_id)` refreshes Redis metadata after Mongo writes turns.
- `update_session_title()` updates Mongo and Redis without changing `updated_at`.
- `delete_session()` removes Redis metadata/history/list entry and delegates durable delete to Mongo.

## History Cache

`ConversationHistoryCache` stores a small recent context window per session. It is for latency, not durable storage.

Expected behavior:

- Keep a bounded number of recent messages.
- Expire idle history.
- Warm from Mongo when needed.
- Avoid replacing durable Mongo turns.

## LLM Cache

`LLMResponseCache` has two layers:

- P0/query-only cache, short TTL, used before retrieval for repeat simple queries.
- P2/post-retrieval cache, keyed by query plus retrieved document ids/model.

Document-tag reverse index is used for invalidation after document updates.

## Rate Limiter

`SlidingWindowRateLimiter` uses Redis sorted sets for continuous windows:

- RPM: `rate:min:{id}`
- RPD: `rate:day:{id}`

`api/middleware/rate_limit.py` wraps it as FastAPI middleware. If Redis fails, requests are allowed and warnings are logged.

## Settings

Main flags:

- `redis_enabled`
- `redis_url`
- `use_redis_session`
- `use_redis_cache`
- `use_redis_history`
- `rate_limit_enabled`
- `rate_limit_rpm`
- `rate_limit_rpd`
- `rate_limit_alert_threshold`

## Useful Checks

```bash
python -m py_compile cache/*.py
python -m pytest tests/test_phase1_redis.py tests/test_phase2_redis.py -q -m "not integration"
```
