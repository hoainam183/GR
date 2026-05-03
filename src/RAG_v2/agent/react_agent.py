from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from schemas.constants import CLARIFY_SENTINEL
from .graph_state import AgentGraphState
from .lc_tools import LANGGRAPH_TOOLS, TOOL_MAP
from .prompts import (
    AGENT_SYSTEM_PROMPT,
    DECOMPOSE_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    SYNTHESIS_PROMPT,
)
from .state import AgentState, ToolResult
from .tool_adapters import execute_retrieval_plan, web_search_for_executor

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

    The agent and synthesis LLMs can use different providers/models via
    ``settings.agent_synthesis_provider`` and ``settings.agent_synthesis_model``.
    When those are empty, the same LLM is used for both roles.
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
        self._tool_result_limit: int = int(getattr(settings, "agent_tool_result_limit", 1500))
        # Approximate token budget before trimming kicks in.
        # Qwen 3 8B loaded in LM Studio typically has 4096 ctx; reserve ~800 for generation.
        self._context_token_budget: int = int(getattr(settings, "agent_context_token_budget", 3200))

        # Agent LLM — bound with tools, deterministic temperature
        agent_temperature = float(getattr(settings, "agent_temperature", 0.0))
        agent_max_tokens = int(getattr(settings, "agent_max_tokens", 800))
        # LM Studio does not require a real API key; use a configurable placeholder.
        lm_studio_api_key: str = getattr(settings, "lm_studio_api_key", "lm-studio") or "lm-studio"

        self._llm = ChatOpenAI(
            base_url=lm_studio_url,
            api_key=lm_studio_api_key,
            model=self.model_name,
            temperature=agent_temperature,
            max_tokens=agent_max_tokens,
            timeout=180,
        )
        self._llm_with_tools = self._llm.bind_tools(LANGGRAPH_TOOLS)

        # Synthesis LLM — can use a different (stronger) provider/model
        self._synthesis_llm = self._build_synthesis_llm(settings, lm_studio_url)

        self._graph = self._build_graph()
        logger.info(
            "[Agent] LangGraph graph compiled with %d tools (model=%s, synth=%s)",
            len(LANGGRAPH_TOOLS),
            self.model_name,
            getattr(self._synthesis_llm, "model_name", self.model_name),
        )

    @staticmethod
    def _build_synthesis_llm(settings: Any, default_base_url: str) -> ChatOpenAI:
        """Build the synthesis LLM, optionally using a separate provider.

        When ``settings.agent_synthesis_provider`` is set, the synthesis LLM
        uses a different endpoint (e.g. Gemini for higher quality final answers)
        while the agent tool-calling LLM stays on the local model.
        """
        synth_provider = getattr(settings, "agent_synthesis_provider", "") or ""
        synth_model = getattr(settings, "agent_synthesis_model", "") or ""
        synth_temp = float(getattr(settings, "agent_synthesis_temperature", 0.2))
        synth_max_tokens = int(getattr(settings, "agent_synthesis_max_tokens", 2000))

        if synth_provider == "gemini":
            return ChatOpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=getattr(settings, "google_api_key", ""),
                model=synth_model or "gemini-3.1-flash-lite-preview",
                temperature=synth_temp,
                max_tokens=synth_max_tokens,
                timeout=180,
            )
        elif synth_provider == "ollama":
            ollama_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
            ollama_url = ollama_url if ollama_url.endswith("/v1") else f"{ollama_url}/v1"
            # Ollama does not require a real API key.
            ollama_api_key: str = getattr(settings, "ollama_api_key", "ollama") or "ollama"
            return ChatOpenAI(
                base_url=ollama_url,
                api_key=ollama_api_key,
                model=synth_model or getattr(settings, "agent_model", "qwen2.5-8b-instruct"),
                temperature=synth_temp,
                max_tokens=synth_max_tokens,
                timeout=180,
            )
        else:
            # Default: reuse the same LM Studio endpoint
            lm_studio_api_key_synth: str = (
                getattr(settings, "lm_studio_api_key", "lm-studio") or "lm-studio"
            )
            return ChatOpenAI(
                base_url=default_base_url,
                api_key=lm_studio_api_key_synth,
                model=synth_model or getattr(settings, "agent_model", "qwen2.5-8b-instruct"),
                temperature=synth_temp,
                max_tokens=synth_max_tokens,
                timeout=180,
            )

    # ─── Public API ───────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_base_url(raw_url: str) -> str:
        """Substitute 'localhost' with explicit IPv4 for LM Studio on macOS."""
        return raw_url.replace("://localhost", "://127.0.0.1")

    def run(
        self,
        query: str,
        session_id: str = "",
        history: list[dict[str, str]] | None = None,
        complexity_subtype: str | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> AgentState:
        """
        Execute the LangGraph ReAct graph and return a fully populated
        AgentState ready for MongoDB logging and pipeline consumption.

        Args:
            complexity_subtype: "comparison" | "multi_source" → planner path;
                                "general" | None → agent loop path.
            user_context: Student info dict (cohort, major_code, etc.) for
                          planner hint injection.
        """
        # Determine execution path based on complexity subtype
        execution_path = "agent"  # default: ReAct agent loop
        if complexity_subtype in ("comparison", "multi_source"):
            execution_path = "planner"

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
            # Planner-Executor path fields
            "execution_path": execution_path,
            "sub_questions": None,
            "retrieval_plan": None,
            "user_context": user_context,
            "empty_result_count": 0,
        }

        logger.info("[Agent] Starting query: '%s...' (path=%s)", query[:80], execution_path)
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
        history: list[dict[str, str]] | None,
    ) -> list[Any]:
        """Build the initial message list, optionally prepending recent history."""
        messages: list[Any] = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]

        if history:
            # Bounded to last 4 turns (2 user+assistant pairs) to stay within
            # Qwen 3 8B context budget. Each turn can be 200-400 tokens.
            for turn in history[-4:]:
                role = str(turn.get("role", "")).strip().lower()
                content = str(turn.get("content", "")).strip()
                if not content:
                    continue
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    # Truncate long assistant turns to avoid bloating context
                    messages.append(AIMessage(content=content[:600]))

        messages.append(HumanMessage(content=query))
        return messages

    @staticmethod
    def _estimate_tokens(messages: list[Any]) -> int:
        """Fast char-based token estimate (1 token ≈ 3.5 chars for Vietnamese/English mix)."""
        total_chars = sum(len(str(getattr(m, "content", "") or "")) for m in messages)
        return total_chars // 3

    def _trim_messages_for_context(self, messages: list[Any]) -> list[Any]:
        """
        Trim the message list to stay within _context_token_budget.

        Strategy (in order of priority):
        1. Keep SystemMessage (index 0) always.
        2. Keep the last HumanMessage (current query) always.
        3. If still over budget, truncate ToolMessage content (oldest first).
        4. If still over budget, drop oldest ToolMessage + paired AIMessage.
        """
        if self._estimate_tokens(messages) <= self._context_token_budget:
            return messages

        trimmed = list(messages)

        # Step 3: shorten tool message content starting from oldest
        MAX_TOOL_CHARS = 600
        for i, msg in enumerate(trimmed):
            if self._estimate_tokens(trimmed) <= self._context_token_budget:
                break
            if isinstance(msg, ToolMessage):
                content = str(msg.content or "")
                if len(content) > MAX_TOOL_CHARS:
                    trimmed[i] = ToolMessage(
                        content=content[:MAX_TOOL_CHARS] + "...[trunc]",
                        tool_call_id=msg.tool_call_id,
                        name=msg.name,
                    )

        # Step 4: drop oldest ToolMessage blocks (AIMessage + ToolMessages) to free space
        while self._estimate_tokens(trimmed) > self._context_token_budget and len(trimmed) > 3:
            # Find first ToolMessage and drop it with its preceding AIMessage
            for i, msg in enumerate(trimmed):
                if isinstance(msg, ToolMessage):
                    # Also drop the AIMessage that triggered this tool call
                    drop_from = max(1, i - 1)
                    trimmed = trimmed[:drop_from] + trimmed[i + 1 :]
                    break
            else:
                break  # no more ToolMessages to drop

        est = self._estimate_tokens(trimmed)
        logger.debug("[Agent] Context trimmed: ~%d tokens from %d messages", est, len(trimmed))
        return trimmed

    def _agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Call the model with bound tools to decide the next action."""
        new_iteration = state["iteration"] + 1
        logger.info("[Agent] Iteration %d/%d", new_iteration, state["max_iterations"])

        messages = self._trim_messages_for_context(state["messages"])
        if len(messages) < len(state["messages"]):
            logger.info(
                "[Agent] Trimmed %d → %d messages to fit context budget (~%d tokens)",
                len(state["messages"]),
                len(messages),
                self._estimate_tokens(messages),
            )

        # Retry logic for empty results
        empty_count = state.get("empty_result_count", 0)
        if messages and isinstance(messages[-1], ToolMessage):
            if str(messages[-1].content or "").startswith("[Khong tim thay"):
                empty_count += 1
                if empty_count >= 2:
                    logger.warning("[Agent] Empty result limit reached, forcing synthesize")
                    return {"error": "Không tìm thấy thông tin phù hợp."}
                
                logger.info("[Agent] Empty result detected, injecting retry hint (count=%d)", empty_count)
                hint = SystemMessage(
                    content="Kết quả tìm kiếm trống. Hãy thử lại với câu truy vấn ngắn gọn hơn, "
                            "chỉ giữ từ khóa cốt lõi, loại bỏ các thông tin cá nhân hoặc từ ngữ thừa."
                )
                # messages is a copy from _trim_messages_for_context or we can just append
                messages = messages + [hint]

        llm_t0 = time.perf_counter()
        try:
            response = self._llm_with_tools.invoke(messages)
        except Exception as exc:
            logger.error("[Agent] LLM call failed: %s", exc)
            return {
                "messages": [],
                "iteration": new_iteration,
                "error": str(exc),
            }
        llm_ms = (time.perf_counter() - llm_t0) * 1000
        has_tool_calls = bool(getattr(response, "tool_calls", None))
        logger.info(
            "[Agent] LLM call completed in %.0fms (has_tool_calls=%s)",
            llm_ms, has_tool_calls,
        )

        return {
            "messages": [response],
            "iteration": new_iteration,
            "empty_result_count": empty_count,
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
                    content=str(result_str)[:self._tool_result_limit],
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
                return str(msg.content).replace(f"{CLARIFY_SENTINEL}\n", "", 1)
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

    def _after_tools(self, state: AgentGraphState) -> Literal["agent", "synthesize", "end"]:
        """
        Route after tool execution.

        - clarify_question: stop immediately (wait for user follow-up)
        - tool returned error ([Loi...] prefix): synthesize early to save LLM calls
        - everything else: loop back to agent

        Note: compare_programs / compare_cohorts are no longer in the agent
        tool list (Phase 3 cleanup) — comparisons are handled by the
        planner-executor path.
        """
        history = state.get("tool_call_history", [])
        if not history:
            return "agent"

        last_tool = history[-1]

        if last_tool == "clarify_question":
            logger.info("[Agent] Clarify requested — stop current run and wait for user input")
            return "end"

        # Nếu tool trả về lỗi → synthesize ngay, tránh tiêu tốn thêm LLM call
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                content = str(msg.content or "")
                if content.startswith("[Loi"):
                    logger.warning(
                        "[Agent] Tool '%s' returned error — forcing early synthesize: %s",
                        last_tool, content[:80],
                    )
                    return "synthesize"
                break  # Chỉ check ToolMessage cuối cùng

        return "agent"

    # ─── Planner-Executor nodes (Phase 2 refactor) ─────────────────────────────

    def _decompose_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Decompose a complex query into standalone sub-questions using Gemini."""
        query = state["query"]

        # Inject user_context into the prompt when available
        user_ctx = state.get("user_context")
        ctx_parts: list[str] = []
        if user_ctx:
            if user_ctx.get("cohort"):
                ctx_parts.append(f"Khóa: {user_ctx['cohort']}")
            if user_ctx.get("major_code"):
                ctx_parts.append(f"Ngành: {user_ctx['major_code']}")
        ctx_str = f"\nThông tin sinh viên: {', '.join(ctx_parts)}" if ctx_parts else ""
        prompt = f"Query: {query}{ctx_str}"

        t0 = time.perf_counter()
        try:
            response = self._synthesis_llm.invoke([
                SystemMessage(content=DECOMPOSE_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            raw = response.content.strip().strip("```json").strip("```").strip()
            parsed = json.loads(raw)
            sub_questions = parsed.get("sub_questions", [query])[:4]
            if not sub_questions:
                sub_questions = [query]
            logger.info(
                "[Decompose] %d sub-questions in %.0fms: %s",
                len(sub_questions),
                (time.perf_counter() - t0) * 1000,
                parsed.get("reasoning", ""),
            )
        except Exception as exc:
            logger.warning("[Decompose] Failed (%s), using original query", exc)
            sub_questions = [query]

        return {"sub_questions": sub_questions}

    def _planner_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Generate a retrieval plan from sub-questions using Gemini.

        Returns retrieval_plan dict on success, or None to trigger agent fallback.
        Does NOT set 'error' to avoid triggering _should_continue's error path.
        """
        sub_questions = state.get("sub_questions") or [state["query"]]

        # Inject user_context into the prompt
        user_ctx = state.get("user_context")
        ctx_parts: list[str] = []
        if user_ctx:
            if user_ctx.get("cohort"):
                ctx_parts.append(f"Khóa sinh viên: {user_ctx['cohort']}")
            if user_ctx.get("major_code"):
                ctx_parts.append(f"Mã ngành: {user_ctx['major_code']}")
        ctx_str = f"\nThông tin sinh viên: {', '.join(ctx_parts)}" if ctx_parts else ""

        questions_str = "\n".join(f"- {q}" for q in sub_questions)
        prompt = (
            f"Câu hỏi gốc: {state['query']}\n\n"
            f"Câu hỏi con:\n{questions_str}{ctx_str}"
        )

        t0 = time.perf_counter()
        try:
            response = self._synthesis_llm.invoke([
                SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            raw = response.content.strip().strip("```json").strip("```").strip()
            plan = json.loads(raw)
            steps = plan.get("steps", [])[:4]
            plan["steps"] = steps
            if not steps:
                logger.warning("[Planner] Empty plan — will fallback to agent")
                return {"retrieval_plan": None}
            logger.info(
                "[Planner] %d steps in %.0fms: %s",
                len(steps),
                (time.perf_counter() - t0) * 1000,
                plan.get("reasoning", ""),
            )
            return {"retrieval_plan": plan}
        except Exception as exc:
            logger.error("[Planner] Failed (%s) — will fallback to agent", exc)
            return {"retrieval_plan": None}

    def _executor_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Execute retrieval plan steps in parallel. No LLM involved."""
        plan = state.get("retrieval_plan") or {}
        steps = plan.get("steps", [])

        if not steps:
            return {"final_answer": "Xin lỗi, không thể tạo kế hoạch tìm kiếm."}

        t0 = time.perf_counter()
        labeled_results = execute_retrieval_plan(steps)
        logger.info(
            "[Executor] %d/%d steps completed in %.0fms",
            len(labeled_results), len(steps),
            (time.perf_counter() - t0) * 1000,
        )

        tool_messages: list[ToolMessage] = [
            ToolMessage(
                content=f"### {label}\n{result}"[:self._tool_result_limit],
                tool_call_id=f"plan_{i}",
                name="rag_search",
            )
            for i, (label, result) in enumerate(labeled_results)
        ]

        new_history = [f"planned_rag_search:{lbl}" for lbl, _ in labeled_results]

        if plan.get("needs_web"):
            web_result = web_search_for_executor(query=state["query"])
            tool_messages.append(ToolMessage(
                content=web_result[:self._tool_result_limit],
                tool_call_id="plan_web",
                name="web_search",
            ))
            new_history.append("planned_web_search")

        return {
            "messages": tool_messages,
            "tool_call_history": new_history,
        }

    # ─── Planner-Executor routing ──────────────────────────────────────────────

    # Tập hợp collection hợp lệ mà planner được phép dùng.
    # Phải khớp với COLLECTION_MAP keys trong tool_adapters.py.
    _VALID_COLLECTIONS: frozenset[str] = frozenset({
        "quy_dinh", "chuong_trinh", "ke_hoach", "ho_tro_sv"
    })

    def _validate_plan(self, plan: dict[str, Any]) -> bool:
        """Kiểm tra chất lượng retrieval plan trước khi execute.

        Reject plan nếu hơn 50% steps có vấn đề:
        - query rỗng hoặc whitespace
        - collection không nằm trong _VALID_COLLECTIONS

        Returns:
            True nếu plan đủ chất lượng để execute.
        """
        steps = plan.get("steps", [])
        if not steps:
            return False

        valid_steps = [
            s for s in steps
            if str(s.get("query", "")).strip()
            and s.get("collection") in self._VALID_COLLECTIONS
        ]
        ratio = len(valid_steps) / len(steps)
        if ratio < 0.5:
            logger.warning(
                "[Planner] Low quality plan: %d/%d valid steps (%.0f%%) — collections=%s",
                len(valid_steps), len(steps), ratio * 100,
                [s.get("collection") for s in steps],
            )
            return False
        return True

    def _route_complex(self, state: AgentGraphState) -> str:
        """Entry routing: planner path (decompose) or agent loop."""
        if state.get("execution_path") == "planner":
            return "decompose"
        return "agent"

    def _after_planner(
        self, state: AgentGraphState
    ) -> Literal["executor", "agent"]:
        """Route after planner: execute plan if valid quality, else fallback to agent loop."""
        plan = state.get("retrieval_plan")
        if plan and self._validate_plan(plan):
            return "executor"
        logger.warning("[Planner] No valid/quality plan — falling back to agent loop")
        return "agent"

    # ─── Graph construction ───────────────────────────────────────────────────

    def _build_graph(self) -> Any:  # -> langgraph.graph.state.CompiledStateGraph
        """Compile and return the LangGraph StateGraph.

        Graph topology (Phase 2 refactor):

        START ─[_route_complex]─┬─► decompose → planner ─[_after_planner]─┬─► executor → synthesize → END
                                │                                         └─► agent (fallback)
                                └─► agent ─[_should_continue]─┬─► tools ─[_after_tools]─┬─► agent
                                                              ├─► synthesize → END      ├─► synthesize → END
                                                              └─► extract_answer → END  └─► extract_answer → END
        """
        graph = StateGraph(AgentGraphState)

        # ── Planner-Executor path nodes ───────────────────────────────────────
        graph.add_node("decompose", self._decompose_node)
        graph.add_node("planner", self._planner_node)
        graph.add_node("executor", self._executor_node)

        # ── Agent loop path nodes (unchanged) ─────────────────────────────────
        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tools_node)

        # ── Shared terminal nodes ─────────────────────────────────────────────
        graph.add_node("synthesize", self._synthesize_node)
        graph.add_node("extract_answer", self._extract_answer_node)

        # ── Entry: route based on execution_path ──────────────────────────────
        graph.add_conditional_edges(
            START, self._route_complex,
            {"decompose": "decompose", "agent": "agent"},
        )

        # ── Planner path edges ────────────────────────────────────────────────
        graph.add_edge("decompose", "planner")
        graph.add_conditional_edges(
            "planner", self._after_planner,
            {"executor": "executor", "agent": "agent"},
        )
        graph.add_edge("executor", "synthesize")

        # ── Agent loop edges (unchanged) ──────────────────────────────────────
        graph.add_conditional_edges(
            "agent", self._should_continue,
            {"tools": "tools", "synthesize": "synthesize", "end": "extract_answer"},
        )
        graph.add_conditional_edges(
            "tools", self._after_tools,
            {"agent": "agent", "synthesize": "synthesize", "end": "extract_answer"},
        )

        # ── Terminal edges ────────────────────────────────────────────────────
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