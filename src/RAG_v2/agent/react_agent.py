from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from .graph_state import AgentGraphState
from .lc_tools import LANGGRAPH_TOOLS, TOOL_MAP
from .prompts import AGENT_SYSTEM_PROMPT, SYNTHESIS_PROMPT
from .state import AgentState, ToolResult

logger = logging.getLogger(__name__)


def _make_call_sig(tool_name: str, tool_args: dict[str, Any]) -> str:
    """
    Build a compact signature for a tool call.

    Used to detect exact duplicates (same name + same args).
    Using an 8-char MD5 prefix is sufficient for collision avoidance in
    the small number of calls that occur within a single agent run.
    """
    try:
        args_hash = hashlib.md5(
            json.dumps(tool_args, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:8]
    except Exception:
        args_hash = str(abs(hash(str(tool_args))))[:8]
    return f"{tool_name}:{args_hash}"


class ReActAgent:
    """
    LangGraph-based ReAct Agent with backward-compatible public API.

    Graph topology
    --------------
    START → agent ─┬→ tools → agent (loop)
                   ├→ synthesize → END
                   └→ extract_answer → END
    """

    def __init__(self, settings: Any) -> None:
        lm_studio_url = (
            getattr(settings, "lm_studio_url", None)
            or getattr(settings, "lm_studio_base_url", "http://localhost:1234/v1")
        )
        lm_studio_url = self._normalize_base_url(str(lm_studio_url))

        self.model_name: str = getattr(
            settings,
            "agent_model",
            getattr(settings, "chat_model", "qwen2.5-8b-instruct"),
        )
        self.max_iterations: int = int(getattr(settings, "agent_max_iterations", 4))

        # Agent LLM — bound with tools, low temperature for deterministic tool choice
        self._llm = ChatOpenAI(
            base_url=lm_studio_url,
            api_key="lm-studio",
            model=self.model_name,
            temperature=0.1,
            max_tokens=800,
            timeout=30,
        )
        self._llm_with_tools = self._llm.bind_tools(LANGGRAPH_TOOLS)

        # Synthesis LLM — no tools, higher max_tokens for complete answers
        self._synthesis_llm = ChatOpenAI(
            base_url=lm_studio_url,
            api_key="lm-studio",
            model=self.model_name,
            temperature=0.2,
            max_tokens=1200,  # raised: synthesis must produce complete answers
            timeout=30,
        )

        self._graph = self._build_graph()
        logger.info("[Agent] LangGraph graph compiled with %d tools", len(LANGGRAPH_TOOLS))

    # ─── Public API ───────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_base_url(raw_url: str) -> str:
        """Substitute 'localhost' with explicit IPv4 for LM Studio on macOS."""
        return raw_url.replace("://localhost", "://127.0.0.1")

    def run(
        self,
        query: str,
        session_id: str = "",
        history: Optional[list[dict[str, str]]] = None,
    ) -> AgentState:
        """
        Execute the LangGraph ReAct graph and return a fully populated
        AgentState ready for MongoDB logging and pipeline consumption.

        The interface is identical to the previous custom ReAct implementation —
        callers do not need to change.
        """
        initial_state: AgentGraphState = {
            "messages": self._build_initial_messages(query=query, history=history),
            "query": query,
            "session_id": session_id,
            "tool_call_history": [],
            "tool_call_signatures": [],
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "final_answer": None,
            "error": None,
        }

        logger.info("[Agent] Starting query: '%s...'", query[:80])
        run_start = time.perf_counter()

        try:
            result = self._graph.invoke(initial_state)
        except Exception as exc:
            logger.error("[Agent] Graph execution failed: %s", exc, exc_info=True)
            return self._make_error_state(query, session_id, str(exc))

        elapsed = time.perf_counter() - run_start
        logger.info(
            "[Agent] Finished in %.2fs | iterations=%d | tools=%s",
            elapsed,
            result.get("iteration", 0),
            result.get("tool_call_history", []),
        )

        # Edge case: extract_answer_node found no AIMessage content.
        # This can happen if Qwen returns a bare tool-call AIMessage with no
        # text, and _should_continue routes "end" incorrectly.
        if not result.get("final_answer") and not result.get("error"):
            has_tool_msgs = any(
                isinstance(m, ToolMessage) for m in result.get("messages", [])
            )
            if has_tool_msgs:
                logger.warning("[Agent] Empty final answer with tool results — synthesizing")
                recovery = self._synthesize_node(result)
                result["final_answer"] = recovery.get("final_answer")
            if not result.get("final_answer"):
                result["final_answer"] = (
                    "Xin lỗi, không thể xử lý câu hỏi này. Vui lòng thử lại."
                )

        return self._to_agent_state(result, query, session_id)

    # ─── Graph nodes ──────────────────────────────────────────────────────────

    def _build_initial_messages(
        self,
        *,
        query: str,
        history: Optional[list[dict[str, str]]],
    ) -> list[Any]:
        """Build the initial message list, optionally prepending recent history."""
        messages: list[Any] = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]

        if history:
            for turn in history[-8:]:  # bounded to last 8 turns
                role = str(turn.get("role", "")).strip().lower()
                content = str(turn.get("content", "")).strip()
                if not content:
                    continue
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=query))
        return messages

    def _agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Call the model with bound tools to decide the next action."""
        new_iteration = state["iteration"] + 1
        logger.info("[Agent] Iteration %d/%d", new_iteration, state["max_iterations"])

        try:
            response = self._llm_with_tools.invoke(state["messages"])
        except Exception as exc:
            logger.error("[Agent] LLM call failed: %s", exc)
            return {
                "messages": [],
                "iteration": new_iteration,
                "error": str(exc),
            }

        return {
            "messages": [response],
            "iteration": new_iteration,
        }

    def _tools_node(self, state: AgentGraphState) -> dict[str, Any]:
        """
        Execute all tool calls in the latest AIMessage.

        Changes from original
        ----------------------
        - Builds ``tool_call_signatures`` for exact-duplicate detection.
        - Records per-tool latency in milliseconds.
        - Safely handles the case where the last message is not an AIMessage.
        """
        messages = state["messages"]
        last_ai = messages[-1] if messages else None

        if not isinstance(last_ai, AIMessage) or not getattr(last_ai, "tool_calls", None):
            return {}

        tool_messages: list[ToolMessage] = []
        new_history = list(state.get("tool_call_history", []))
        new_sigs = list(state.get("tool_call_signatures", []))

        for tool_call in last_ai.tool_calls:
            tool_name = str(tool_call.get("name") or "")
            tool_args = tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {}

            logger.info("[Agent] → %s(%s)", tool_name, str(tool_args)[:120])
            t0 = time.perf_counter()

            lc_tool = TOOL_MAP.get(tool_name)
            if lc_tool is None:
                result_str = f"[Loi he thong: Tool '{tool_name}' khong ton tai]"
            else:
                try:
                    result_str = lc_tool.invoke(tool_args)
                except Exception as exc:
                    logger.error("[Agent] Tool %s failed: %s", tool_name, exc)
                    result_str = f"[Loi khi tim kiem: {exc}]"

            latency_ms = (time.perf_counter() - t0) * 1000
            logger.info("[Agent] ← %s completed in %.0fms (chars=%d)", tool_name, latency_ms, len(str(result_str)))

            tool_messages.append(
                ToolMessage(
                    content=str(result_str)[:2000],  # guard Qwen 8B context window
                    tool_call_id=str(tool_call.get("id") or ""),
                    name=tool_name,
                )
            )
            new_history.append(tool_name)
            new_sigs.append(_make_call_sig(tool_name, tool_args))

        return {
            "messages": tool_messages,
            "tool_call_history": new_history,
            "tool_call_signatures": new_sigs,
        }

    @staticmethod
    def _relay_last_clarify_output(state: AgentGraphState) -> str | None:
        """Return the last clarify tool output (without sentinel tag) when present."""
        history = state.get("tool_call_history", [])
        if not history or history[-1] != "clarify_question":
            return None

        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, ToolMessage) and (msg.name or "") == "clarify_question":
                return str(msg.content).replace("[CLARIFY]\n", "", 1)
        return None

    def _synthesize_node(self, state: AgentGraphState) -> dict[str, Any]:
        """
        Fallback synthesis — invoked when the agent hits iteration / loop limits
        or when an LLM / tool error occurs but partial results are available.

        Uses a separate synthesis LLM (no tools, higher max_tokens).
        """
        logger.warning("[Agent] Forced synthesis after %d iterations", state.get("iteration", 0))

        # Special case: last tool was clarify_question → relay its output directly
        clarify_output = self._relay_last_clarify_output(state)
        if clarify_output:
            return {"final_answer": clarify_output}

        # Collect all tool results from message history
        tool_contents: list[str] = []
        for msg in state.get("messages", []):
            if isinstance(msg, ToolMessage) and msg.content:
                label = f"[{msg.name}]" if msg.name else "[tool]"
                tool_contents.append(f"{label}\n{msg.content}")

        if not tool_contents:
            return {
                "final_answer": (
                    "Xin lỗi, tôi không tìm thấy thông tin phù hợp với câu hỏi của bạn. "
                    "Vui lòng liên hệ Phòng Đào tạo để được hỗ trợ."
                )
            }

        context = "\n\n---\n\n".join(tool_contents)
        try:
            response = self._synthesis_llm.invoke([
                SystemMessage(content=SYNTHESIS_PROMPT),
                HumanMessage(
                    content=(
                        f"Câu hỏi: {state['query']}\n\n"
                        f"Thông tin tìm được:\n{context}"
                    )
                ),
            ])
            answer = response.content or "Tôi không tìm thấy thông tin về vấn đề này."
        except Exception as exc:
            logger.error("[Agent] Synthesis LLM failed: %s", exc)
            # Hard fallback: surface first tool result verbatim
            answer = f"Thong tin tim duoc:\n{tool_contents[0][:500]}"

        return {"final_answer": str(answer)}

    def _extract_answer_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Extract a direct final answer when the model replies without tool calls."""
        clarify_output = self._relay_last_clarify_output(state)
        if clarify_output:
            return {"final_answer": clarify_output}

        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                return {"final_answer": str(msg.content)}
        return {"final_answer": None}

    # ─── Conditional routing ──────────────────────────────────────────────────

    def _should_continue(
        self, state: AgentGraphState
    ) -> Literal["tools", "synthesize", "end"]:
        """
        Determine graph edge after each agent_node execution.

        Decision tree
        -------------
        1. Error flag set          → synthesize  (graceful recovery)
        2. Last message has no tool_calls → end  (direct answer)
        3. Max iterations reached  → synthesize
        4. Exact duplicate call (same name + same args) → synthesize
        5. Same tool name repeated for tools other than rag_search/clarify_question → synthesize
        6. Otherwise               → tools
        """
        if state.get("error"):
            return "synthesize"

        messages = state.get("messages", [])
        last = messages[-1] if messages else None

        # No tool calls → LLM gave a direct text answer
        if not isinstance(last, AIMessage) or not getattr(last, "tool_calls", None):
            return "end"

        if state["iteration"] >= state["max_iterations"]:
            logger.warning("[Agent] Max iterations %d reached", state["max_iterations"])
            return "synthesize"

        existing_sigs = set(state.get("tool_call_signatures", []))
        history = state.get("tool_call_history", [])

        for tc in last.tool_calls:
            tool_name = str(tc.get("name") or "")
            tool_args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
            sig = _make_call_sig(tool_name, tool_args)

            # Exact duplicate (same name AND same args) → definite loop
            if sig in existing_sigs:
                logger.warning(
                    "[Agent] Exact duplicate call blocked: %s(%s)", tool_name, str(tool_args)[:80]
                )
                return "synthesize"

            # Same tool name, different args:
            #   - rag_search: ALLOWED — different collections are legitimate
            #   - clarify_question: ALLOWED — handled by 1-per-session elsewhere
            #   - all others: treat as loop for conservative Qwen 8B behaviour
            if tool_name in history and tool_name not in {"rag_search", "clarify_question"}:
                logger.warning("[Agent] Tool '%s' called again with new args — loop suspected", tool_name)
                return "synthesize"

        return "tools"

    def _after_tools(self, state: AgentGraphState) -> Literal["agent", "end"]:
        """
        Route immediately to answer extraction after clarify_question.

        clarify_question is a user-interaction stop point. Once triggered,
        the agent should wait for the user's follow-up turn instead of
        continuing with speculative tool calls in the same run.
        """
        history = state.get("tool_call_history", [])
        if history and history[-1] == "clarify_question":
            logger.info("[Agent] Clarify requested — stop current run and wait for user input")
            return "end"
        return "agent"

    # ─── Graph construction ───────────────────────────────────────────────────

    def _build_graph(self):
        graph = StateGraph(AgentGraphState)

        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tools_node)
        graph.add_node("synthesize", self._synthesize_node)
        graph.add_node("extract_answer", self._extract_answer_node)

        graph.add_edge(START, "agent")
        graph.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "tools": "tools",
                "synthesize": "synthesize",
                "end": "extract_answer",
            },
        )
        graph.add_conditional_edges(
            "tools",
            self._after_tools,
            {
                "agent": "agent",
                "end": "extract_answer",
            },
        )
        graph.add_edge("synthesize", END)
        graph.add_edge("extract_answer", END)

        return graph.compile()

    # ─── State conversion ─────────────────────────────────────────────────────

    def _to_agent_state(
        self,
        graph_result: AgentGraphState,
        query: str,
        session_id: str,
    ) -> AgentState:
        """
        Convert the LangGraph runtime state into an AgentState dataclass.

        Rebuilds ToolResult entries from the message history rather than
        relying on in-graph tracking, so the log is always complete.
        """
        state = AgentState(query=query, session_id=session_id)
        state.iteration = int(graph_result.get("iteration", 0) or 0)
        state.tool_call_history = list(graph_result.get("tool_call_history", []))
        state.final_answer = graph_result.get("final_answer")
        state.error = graph_result.get("error")

        messages = graph_result.get("messages", [])

        # Build tool_call_id → (name, args) index from AIMessages
        call_meta: dict[str, dict[str, Any]] = {}
        for msg in messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    call_id = str(tc.get("id") or "")
                    call_meta[call_id] = {
                        "name": tc.get("name"),
                        "args": tc.get("args") if isinstance(tc.get("args"), dict) else {},
                    }

        # Reconstruct ToolResult list from ToolMessages
        iter_counter = 0
        for msg in messages:
            if isinstance(msg, ToolMessage):
                meta = call_meta.get(str(msg.tool_call_id or ""), {})
                tr = ToolResult(
                    tool_name=str(meta.get("name") or msg.name or "unknown"),
                    args=meta.get("args") if isinstance(meta.get("args"), dict) else {},
                    result=str(msg.content),
                    iteration=iter_counter,
                )
                # Append directly to bypass context-window truncation in add_tool_result
                state.tool_results.append(tr)
                state._log_tool_results.append(tr)
                iter_counter += 1

        return state

    def _make_error_state(self, query: str, session_id: str, error_msg: str) -> AgentState:
        state = AgentState(query=query, session_id=session_id)
        state.error = error_msg
        state.final_answer = (
            "Xin lỗi, có lỗi xảy ra trong quá trình xử lý. "
            "Vui lòng thử lại hoặc liên hệ Phòng Đào tạo để được hỗ trợ."
        )
        return state