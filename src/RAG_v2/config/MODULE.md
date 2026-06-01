# Module: `config`

Source-verified: 2026-05-31 from `config/settings.py`.

## Purpose

`config` defines the process-wide runtime settings model. Most modules should read configuration through `Settings`, not hard-coded environment variables or constants.

## File Map

```text
config/
  __init__.py
  settings.py  Pydantic BaseSettings model and defaults.
```

## Settings Groups

Main setting families in `Settings`:

- Providers: `llm_provider`, `embedding_provider`, `reranker_provider`
- API keys: `google_api_key`, `openai_api_key`, `tavily_api_key`, `llm_api_key`
- Agent: `agent_enabled`, model, max iterations, synthesis provider/model/tokens
- Store hosts: Qdrant, Elasticsearch, MongoDB, Redis
- Collections: `collections`
- Chat LLM: `chat_model`, temperature, token limit
- Retrieval: top-k, vector/keyword pools, fusion weights, raw candidate pool,
  context budgets
- Reranker: model, top-k, thresholds, minimum returned top-k
- Tavily/web fallback: fallback gates, depth, max results, cache settings
- Reflection/routing: reflection provider/model, domain routing thresholds
- Crawler: schedule and retention
- Redis/cache/rate limit: flags and quotas
- Auth/admin/upload: superadmin ids, upload size/batch, CORS, API host/port

## Runtime Contract

Settings load from:

```text
src/RAG_v2/.env
environment variables
defaults in settings.py
```

Do not hard-code provider/model/host values in application code when a setting exists.

RAG retrieval tuning settings are consumed through `RAGPipeline._cfg` and
`pipeline.flows`, including `raw_candidate_multiplier`, `raw_candidate_min`,
`reranker_score_threshold`, `reranker_table_score_threshold`, and
`reranker_min_top_k`. Keep these in sync with `.env.example` and evaluation CLI
overrides.

## Maintenance Notes

- Adding a setting requires updating `.env.example`, docs, and any deployment config.
- Keep defaults safe for local development.
- For new feature flags, document whether disabled state is fail-soft or fail-closed.

## Useful Checks

```bash
python -m py_compile config/*.py
```
