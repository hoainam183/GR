# Module: `agent`

Source-verified: 2026-05-20 from `agent/*.py`, `pipeline/rag_pipeline.py`, and GitNexus symbol context.

## Purpose

`agent` is the agentic RAG layer used by `RAGPipeline.query_agent()` for complex questions. It does not expose HTTP routes directly. The public caller is the pipeline, which converts the final `AgentState` into API metadata, retrieved documents, Mongo traces, and UI debug payloads.

The module has two execution paths:

- Planner-executor path for `complexity_subtype in {"comparison", "multi_source"}`.
- ReAct tool loop path for general complex questions or planner fallback.

## File Map

```text
agent/
  __init__.py       Public exports for state, tools, adapters, and ReActAgent.
  graph_state.py    AgentGraphState TypedDict used by LangGraph.
  lc_tools.py       LangChain StructuredTool schemas and TOOL_MAP.
  prompts.py        System, synthesis, decomposition, and planner prompts.
  react_agent.py    ReActAgent graph nodes, routing, validation, synthesis.
  state.py          AgentState and ToolResult dataclasses for logging/API.
  tool_adapters.py  Tool dispatcher, retrieval/web adapters, cache, ContextVar docs.
```

## Public Contracts

`agent.__init__` exports:

- `ReActAgent`
- `AgentState`, `ToolResult`, `AgentGraphState`
- `LANGGRAPH_TOOLS`, `TOOL_MAP`
- `execute_tool()`, `execute_retrieval_plan()`, `web_search_for_executor()`
- `set_runtime()`, `cache_clear()`
- `init_agent_docs()`, `get_agent_docs()`

`tool_adapters.inject_from_retrieval_service()` is an important runtime hook even though it is not in `__all__`. `RAGPipeline.__init__()` calls it after building the shared `RetrievalService`.

## Runtime Flow

```text
RAGPipeline.query_agent()
  -> init_agent_docs()
  -> ReActAgent.run(query, history, user_context, complexity_subtype)
     -> planner path for comparison/multi_source
        -> decompose -> planner -> validate plan -> executor -> synthesize
     -> react path for general complex
        -> local tool-calling LLM -> tools -> loop/synthesize/extract
  -> get_agent_docs()
  -> API response mapper + Mongo agent trace
```

Planner path:

- `_decompose_node()` uses the synthesis LLM and `DECOMPOSE_SYSTEM_PROMPT`.
- `_planner_node()` asks for JSON retrieval steps.
- `_validate_plan()` requires valid `query` and `collection` fields.
- `_executor_node()` calls `execute_retrieval_plan()` and optionally `web_search_for_executor()` for `needs_web`.
- `_synthesize_node()` writes the final Vietnamese answer from tool results.

ReAct path:

- `_agent_node()` calls the local OpenAI-compatible LLM bound to `LANGGRAPH_TOOLS`.
- `_should_continue()` blocks direct answers before at least one tool result.
- `_tools_node()` dispatches through `TOOL_MAP`.
- `_after_tools()` stops for clarification, synthesizes on tool errors, otherwise loops.

## Tools

Tools bound to the ReAct LLM in `LANGGRAPH_TOOLS`:

| Tool | Input | Purpose |
| --- | --- | --- |
| `rag_search` | `query`, `collection` | Search one logical RAG collection. |
| `web_search` | `query` | Tavily search over HUST/education domains for fresh or missing data. |
| `clarify_question` | `message`, `options` | Ask the user to clarify and end the turn. |

Adapter-only tools still supported by `execute_tool()`:

- `multi_rag_search`
- `compare_cohorts`
- `compare_programs`

These adapter-only tools are for backward compatibility, tests, and direct callers. The local ReAct LLM is not schema-bound to them; comparisons should normally go through planner-executor.

Agent-facing collection aliases:

| Agent name | Internal collection |
| --- | --- |
| `chuong_trinh` | `ctdt` |
| `quy_dinh` | `quydinh` |
| `ke_hoach` | `kehoach` |
| `ho_tro_sv` | `stsv` |

## State And Logging

`AgentGraphState` is the mutable LangGraph state. Important fields:

- `messages`
- `tool_call_history`
- `tool_call_signatures`
- `iteration`, `max_iterations`
- `execution_path`
- `sub_questions`, `retrieval_plan`
- `final_answer`, `error`

`AgentState` is the persistence/API shape. It keeps:

- Recent context-window tool results in `tool_results`.
- Full, untrimmed log results in `_log_tool_results`.
- `tool_call_history`, `iterations`, `route`, `final_answer`, `error`.

## Runtime Injection And Thread Safety

`tool_adapters` owns an `_AdapterRuntime` with settings, BGE/E5 embedders, `MultiCollectionSearch`, optional reranker, and Tavily tool. Runtime should come from the shared `RetrievalService` to avoid loading heavy models twice.

Thread-safety rules:

- Use `_append_agent_docs()` and ContextVar helpers for per-request docs. Do not introduce global result lists.
- `_RAG_CACHE` is an in-process FIFO cache protected by `_CACHE_LOCK`.
- `_RERANKER_LOCK` serializes reranker access because tokenizer/runtime paths are not thread-safe.
- `execute_retrieval_plan()` runs plan steps in a thread pool and uses `contextvars.copy_context().run` per task.

## Settings

Main settings consumed by this module:

- `agent_enabled`
- `agent_model`
- `lm_studio_base_url` / `lm_studio_url`
- `agent_max_iterations`
- `agent_temperature`
- `agent_max_tokens`
- `agent_tool_result_limit`
- `agent_synthesis_provider`
- `agent_synthesis_model`
- `agent_synthesis_temperature`
- `agent_synthesis_max_tokens`

Supported synthesis providers in code: `gemini`, `ollama`, or an LM Studio/OpenAI-compatible fallback.

## Maintenance Notes

- Before changing graph topology, update the topology description here and tests in `tests/test_agent_langgraph.py`.
- When adding a ReAct-visible tool, update `lc_tools.py`, `TOOL_MAP`, `tool_adapters.py`, prompts, and tests.
- When adding adapter-only behavior, document whether it is included in `LANGGRAPH_TOOLS`.
- Keep `CLARIFY_SENTINEL` handling aligned with `schemas/constants.py`.
- If changing public trace fields, update `api/response_mapper.py`, `schemas/chat.py`, frontend trace components, and this file.

## Useful Checks

```bash
python -m py_compile agent/*.py
python -m pytest tests/test_adapters.py tests/test_agent_langgraph.py tests/test_constants.py -q -m "not integration"
```
