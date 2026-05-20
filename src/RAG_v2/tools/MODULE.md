# Module: `tools`

Source-verified: 2026-05-20 from `tools/tavily_search.py`, `retrieval/service.py`, `pipeline/flows.py`, and `agent/tool_adapters.py`.

## Purpose

`tools` currently contains the Tavily web-search adapter. It is optional infrastructure for fresh or missing information, especially dynamic HUST notices, deadlines, schedules, and external official education sources.

The module does not call an LLM by itself. LLM usage happens in callers after web context is returned.

## File Map

```text
tools/
  __init__.py        Public exports.
  tavily_search.py   TavilySearchTool, domain allowlists, API key validation, TTL cache.
```

## TavilySearchTool

Main responsibilities:

- Lazy import the `tavily` package only when a tool instance is created.
- Validate API keys with `is_valid_tavily_api_key()`.
- Normalize `include_domains` and `exclude_domains` to bare domains.
- Search Tavily with configured depth/max result count.
- Filter and format result content.
- Maintain an instance-level TTL cache.
- Retry transient network/5xx errors with backoff.
- Fail fast on invalid API key errors.

## Domain Constants

Current domain groups:

- `HUST_OFFICIAL_DOMAINS`
- `HUST_EXTENDED_DOMAINS`
- `EDU_AUTHORITATIVE_DOMAINS`

Backward-compatible aliases:

- `HUST_DOMAINS = HUST_OFFICIAL_DOMAINS + HUST_EXTENDED_DOMAINS`
- `EDU_DOMAINS = EDU_AUTHORITATIVE_DOMAINS`

News/general domains are not in the default education web scope.

## Integration Points

`RetrievalService.from_settings()` creates one Tavily tool when:

- `settings.tavily_api_key` is valid.
- the key is not empty or a placeholder.

That tool is shared by:

- `RAGPipeline._tavily`
- classic RAG pre-generation web enrichment
- classic RAG post-generation Tavily regeneration
- agent `web_search` tool
- planner-executor `web_search_for_executor()`

## RAG Fallback Semantics

`pipeline/flows.py` has two non-streaming web stages:

1. Pre-generation enrichment:
   - no local sources
   - dynamic/freshness query
   - low retrieval confidence

2. Post-generation quality gate:
   - answer says no information
   - no sources
   - self-eval requests web search with `answer_status` of `insufficient` or `stale_risk`

Both stages require `tavily_fallback_enabled=True`.

Streaming path does not run Tavily fallback to preserve streaming UX.

## Agent Web Search

The agent tool adapter calls Tavily when the local ReAct/planner path needs fresh data or local retrieval is insufficient. Agent web search uses HUST official/extended domains plus authoritative education domains.

Tool output is formatted as a text ToolMessage and also appended to per-request agent docs for API/UI trace.

## Settings

Main settings:

- `tavily_api_key`
- `tavily_fallback_enabled`
- `tavily_search_depth`
- `tavily_max_results`
- `tavily_web_result_count`
- `tavily_web_content_char_limit`
- `tavily_cache_ttl_seconds`
- `tavily_cache_maxsize`
- `web_fallback_on_dynamic`
- `web_fallback_on_no_info`

## Maintenance Notes

- Keep domain lists tight; answers should favor official HUST and authoritative education sources.
- Do not import Tavily at module import time.
- Domain filters accept domains, not full URLs or paths.
- Web fallback must degrade gracefully to local RAG answer on errors.

## Useful Checks

```bash
python -m py_compile tools/*.py
python -m pytest tests/test_phase7.py tests/test_phase8.py -q -m "not integration"
```
