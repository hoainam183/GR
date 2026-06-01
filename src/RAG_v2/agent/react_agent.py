from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from .graph_state import AgentGraphState
from .prompts import DECOMPOSE_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT, SYNTHESIS_PROMPT
from .state import AgentState, ToolResult
from .tool_adapters import execute_retrieval_plan, web_search_for_executor

logger = logging.getLogger(__name__)

_PLANNER_ERROR_ANSWER = (
    "Xin loi, toi khong the lap ke hoach tim kiem phu hop cho cau hoi nay."
)
_NO_INFO_ANSWER = (
    "Xin loi, toi khong tim thay thong tin phu hop trong co so du lieu de tra loi cau hoi nay."
)


def _make_call_sig(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Legacy compact signature helper kept for compatibility with old checks."""
    try:
        args_hash = hashlib.md5(
            json.dumps(tool_args, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:8]
    except Exception:
        args_hash = str(abs(hash(str(tool_args))))[:8]
    return f"{tool_name}:{args_hash}"


def _content_to_text(content: Any) -> str:
    if isinstance(content, list):
        return "".join(str(item) for item in content)
    return str(content or "")


def _parse_json_object(content: Any) -> dict[str, Any]:
    """Parse strict JSON object content, accepting optional markdown fences."""
    raw = _content_to_text(content).strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("planner response must be a JSON object")
    return parsed


def _is_empty_result_text(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    return (
        not normalized
        or normalized.startswith("[khong tim thay")
        or normalized.startswith("khong tim thay")
    )


class ReActAgent:
    """
    Planner-Executor agent with the legacy ReActAgent public name.

    The ReAct tool loop has been removed. The graph is now:

    START -> route_entry -> decompose? -> planner -> executor? -> synthesize -> END
    """

    _VALID_COLLECTIONS: frozenset[str] = frozenset(
        {"quy_dinh", "chuong_trinh", "ke_hoach", "ho_tro_sv"}
    )

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
        self._tool_result_limit: int = int(
            getattr(settings, "agent_tool_result_limit", 1500)
        )
        self._synthesis_llm = self._build_synthesis_llm(settings, lm_studio_url)

        self._graph = self._build_graph()
        logger.info(
            "[Agent] Planner-Executor graph compiled (model=%s, synth=%s)",
            self.model_name,
            getattr(self._synthesis_llm, "model_name", self.model_name),
        )

    @staticmethod
    def _normalize_base_url(raw_url: str) -> str:
        """Substitute 'localhost' with explicit IPv4 for LM Studio on macOS."""
        return raw_url.replace("://localhost", "://127.0.0.1")

    @staticmethod
    def _build_synthesis_llm(settings: Any, default_base_url: str) -> ChatOpenAI:
        """Build the LLM used for decomposition, planning, and synthesis."""
        synth_provider = getattr(settings, "agent_synthesis_provider", "") or ""
        synth_model = getattr(settings, "agent_synthesis_model", "") or ""
        synth_temp = float(getattr(settings, "agent_synthesis_temperature", 0.2))
        synth_max_tokens = int(getattr(settings, "agent_synthesis_max_tokens", 2000))

        if synth_provider == "gemini":
            return ChatOpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=getattr(settings, "google_api_key", ""),
                model=synth_model or "gemini-3.1-flash-lite",
                temperature=synth_temp,
                max_tokens=synth_max_tokens,  # type: ignore
                timeout=180,
            )
        if synth_provider == "ollama":
            ollama_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
            ollama_url = ollama_url if ollama_url.endswith("/v1") else f"{ollama_url}/v1"
            ollama_api_key: str = getattr(settings, "ollama_api_key", "ollama") or "ollama"
            return ChatOpenAI(
                base_url=ollama_url,
                api_key=ollama_api_key,
                model=synth_model or getattr(settings, "agent_model", "qwen2.5-8b-instruct"),
                temperature=synth_temp,
                max_tokens=synth_max_tokens,  # type: ignore
                timeout=180,
            )

        lm_studio_api_key: str = (
            getattr(settings, "lm_studio_api_key", "lm-studio") or "lm-studio"
        )
        return ChatOpenAI(
            base_url=default_base_url,
            api_key=lm_studio_api_key,
            model=synth_model or getattr(settings, "agent_model", "qwen2.5-8b-instruct"),
            temperature=synth_temp,
            max_tokens=synth_max_tokens,  # type: ignore
            timeout=180,
        )

    def run(
        self,
        query: str,
        session_id: str = "",
        history: list[dict[str, str]] | None = None,
        complexity_subtype: str | None = None,
        user_context: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> AgentState:
        """Execute Planner-Executor and return an AgentState for pipeline logging."""
        execution_path = (
            "decompose"
            if complexity_subtype in {"comparison", "multi_source"}
            else "planner"
        )

        initial_state: AgentGraphState = {
            "messages": [],
            "query": query,
            "session_id": session_id,
            "tool_call_history": [],
            "tool_call_signatures": [],
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "final_answer": None,
            "error": None,
            "execution_path": execution_path,
            "sub_questions": None,
            "retrieval_plan": None,
            "user_context": user_context,
            "empty_result_count": 0,
            "top_k": top_k,
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
            "[Agent] Finished in %.2fs | tools=%s | error=%s",
            elapsed,
            result.get("tool_call_history", []),
            result.get("error"),
        )

        if not result.get("final_answer") and not result.get("error"):
            result["final_answer"] = _NO_INFO_ANSWER

        return self._to_agent_state(result, query, session_id)

    def _user_context_hint(self, query: str, user_context: dict[str, Any] | None) -> str:
        if not user_context:
            return ""

        ctx_parts: list[str] = []
        if user_context.get("cohort"):
            ctx_parts.append(f"Khoa sinh vien: {user_context['cohort']}")

        if user_context.get("major_code"):
            from retrieval.metadata_filters import extract_major_codes  # noqa: PLC0415

            query_lower = query.lower()
            has_comparison_keywords = any(
                kw in query_lower
                for kw in [
                    "so sánh",
                    "khác gì",
                    "khác nhau",
                    "với",
                    "so sanh",
                    "khac gi",
                    "khac nhau",
                ]
            )
            if len(extract_major_codes(query)) < 2 and not has_comparison_keywords:
                ctx_parts.append(f"Ma nganh: {user_context['major_code']}")

        return f"\nThong tin sinh vien: {', '.join(ctx_parts)}" if ctx_parts else ""

    def _decompose_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Decompose comparison/multi-source queries before planning."""
        query = state["query"]
        prompt = f"Query: {query}{self._user_context_hint(query, state.get('user_context'))}"

        t0 = time.perf_counter()
        try:
            response = self._synthesis_llm.invoke(
                [
                    SystemMessage(content=DECOMPOSE_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
            parsed = _parse_json_object(response.content)
            raw_sub_questions = parsed.get("sub_questions", [query])
            if not isinstance(raw_sub_questions, list):
                raw_sub_questions = [query]
            sub_questions = [
                str(item).strip()
                for item in raw_sub_questions[:4]
                if str(item).strip()
            ] or [query]
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
        """Generate and validate a retrieval plan."""
        sub_questions = state.get("sub_questions") or [state["query"]]
        questions_str = "\n".join(f"- {q}" for q in sub_questions)
        prompt = (
            f"Cau hoi goc: {state['query']}\n\n"
            f"Cau hoi con:\n{questions_str}"
            f"{self._user_context_hint(state['query'], state.get('user_context'))}"
        )

        t0 = time.perf_counter()
        try:
            response = self._synthesis_llm.invoke(
                [
                    SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
            plan = _parse_json_object(response.content)
        except Exception as exc:
            logger.error("[Planner] Invalid JSON (%s)", exc)
            return {"retrieval_plan": None, "error": f"planner_invalid_json: {exc}"}

        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            steps = []
        plan["steps"] = steps[:4]

        if not plan["steps"]:
            logger.warning("[Planner] Empty plan")
            return {"retrieval_plan": plan, "error": "planner_empty_steps"}

        if not self._validate_plan(plan):
            return {"retrieval_plan": plan, "error": "planner_invalid_plan"}

        logger.info(
            "[Planner] %d steps in %.0fms: %s",
            len(plan["steps"]),
            (time.perf_counter() - t0) * 1000,
            plan.get("reasoning", ""),
        )
        return {"retrieval_plan": plan}

    def _executor_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Execute a validated retrieval plan in parallel."""
        plan = state.get("retrieval_plan") or {}
        steps = self._valid_plan_steps(plan.get("steps", []))
        if not steps:
            return {"final_answer": _PLANNER_ERROR_ANSWER, "error": "planner_empty_steps"}

        t0 = time.perf_counter()
        labeled_results = execute_retrieval_plan(steps, top_k=state.get("top_k"))
        logger.info(
            "[Executor] %d/%d steps completed in %.0fms",
            len(labeled_results),
            len(steps),
            (time.perf_counter() - t0) * 1000,
        )

        new_history = [f"planned_rag_search:{label}" for label, _ in labeled_results]
        non_empty_results = [
            (i, label, result)
            for i, (label, result) in enumerate(labeled_results)
            if not _is_empty_result_text(result)
        ]

        tool_messages: list[ToolMessage] = [
            ToolMessage(
                content=f"### {label}\n{result}"[: self._tool_result_limit],
                tool_call_id=f"plan_{step_index}",
                name="rag_search",
            )
            for step_index, label, result in non_empty_results
        ]

        if plan.get("needs_web"):
            web_result = web_search_for_executor(query=state["query"])
            new_history.append("planned_web_search")
            if not _is_empty_result_text(web_result):
                tool_messages.append(
                    ToolMessage(
                        content=web_result[: self._tool_result_limit],
                        tool_call_id="plan_web",
                        name="web_search",
                    )
                )

        if not tool_messages:
            return {
                "final_answer": _NO_INFO_ANSWER,
                "tool_call_history": new_history,
            }

        return {"messages": tool_messages, "tool_call_history": new_history}

    def _valid_plan_steps(self, steps: Any) -> list[dict[str, Any]]:
        """Return planner steps that are safe to execute."""
        if not isinstance(steps, list):
            return []

        valid_steps: list[dict[str, Any]] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            if not str(step.get("query", "")).strip():
                continue
            if step.get("collection") not in self._VALID_COLLECTIONS:
                continue
            valid_steps.append(step)
        return valid_steps

    def _validate_plan(self, plan: dict[str, Any]) -> bool:
        steps = plan.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return False
        valid_steps = self._valid_plan_steps(steps)
        if len(valid_steps) != len(steps):
            logger.warning(
                "[Planner] Invalid plan: %d/%d executable steps; collections=%s",
                len(valid_steps),
                len(steps),
                [s.get("collection") if isinstance(s, dict) else None for s in steps],
            )
            return False
        return True

    def _route_entry(self, state: AgentGraphState) -> Literal["decompose", "planner"]:
        return "decompose" if state.get("execution_path") == "decompose" else "planner"

    def _after_planner(self, state: AgentGraphState) -> Literal["executor", "synthesize"]:
        if state.get("error"):
            return "synthesize"
        plan = state.get("retrieval_plan")
        return "executor" if plan and self._validate_plan(plan) else "synthesize"

    def _synthesize_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Synthesize final answer from non-empty executor results."""
        if state.get("final_answer"):
            return {"final_answer": state["final_answer"]}

        tool_contents: list[str] = []
        for msg in state.get("messages", []):
            if isinstance(msg, ToolMessage) and msg.content:
                content = str(msg.content)
                if _is_empty_result_text(content):
                    continue
                label = f"[{msg.name}]" if msg.name else "[tool]"
                tool_contents.append(f"{label}\n{content}")

        if not tool_contents:
            return {"final_answer": _PLANNER_ERROR_ANSWER if state.get("error") else _NO_INFO_ANSWER}

        context = "\n\n---\n\n".join(tool_contents)
        try:
            response = self._synthesis_llm.invoke(
                [
                    SystemMessage(content=SYNTHESIS_PROMPT),
                    HumanMessage(
                        content=(
                            f"Cau hoi: {state['query']}\n\n"
                            f"Thong tin tim duoc:\n{context}"
                        )
                    ),
                ]
            )
            answer = _content_to_text(response.content).strip() or _NO_INFO_ANSWER
        except Exception as exc:
            logger.error("[Agent] Synthesis LLM failed: %s", exc)
            answer = f"Thong tin tim duoc:\n{tool_contents[0][:500]}"

        return {"final_answer": answer}

    def _build_graph(self) -> Any:
        graph = StateGraph(AgentGraphState)  # type: ignore

        graph.add_node("decompose", self._decompose_node)
        graph.add_node("planner", self._planner_node)
        graph.add_node("executor", self._executor_node)
        graph.add_node("synthesize", self._synthesize_node)

        graph.add_conditional_edges(
            START,
            self._route_entry,
            {"decompose": "decompose", "planner": "planner"},
        )
        graph.add_edge("decompose", "planner")
        graph.add_conditional_edges(
            "planner",
            self._after_planner,
            {"executor": "executor", "synthesize": "synthesize"},
        )
        graph.add_edge("executor", "synthesize")
        graph.add_edge("synthesize", END)

        return graph.compile()

    def _to_agent_state(
        self,
        graph_result: AgentGraphState,
        query: str,
        session_id: str,
    ) -> AgentState:
        state = AgentState(query=query, session_id=session_id)
        state.tool_call_history = list(graph_result.get("tool_call_history", []))
        state.final_answer = graph_result.get("final_answer")
        state.error = graph_result.get("error")

        plan_steps = []
        plan = graph_result.get("retrieval_plan")
        if isinstance(plan, dict) and isinstance(plan.get("steps"), list):
            plan_steps = [step for step in plan["steps"] if isinstance(step, dict)]

        iter_counter = 0
        for msg in graph_result.get("messages", []):
            if not isinstance(msg, ToolMessage):
                continue

            if (msg.name or "") == "rag_search":
                step_index = -1
                if str(msg.tool_call_id or "").startswith("plan_"):
                    try:
                        step_index = int(str(msg.tool_call_id).split("_", 1)[1])
                    except ValueError:
                        step_index = -1
                step = plan_steps[step_index] if 0 <= step_index < len(plan_steps) else {}
                args = {
                    key: step.get(key)
                    for key in ("query", "collection", "major_hint", "cohort_hint")
                    if step.get(key) is not None
                }
                if graph_result.get("top_k") is not None:
                    args["top_k"] = graph_result.get("top_k")
            elif (msg.name or "") == "web_search":
                args = {"query": query}
            else:
                args = {}

            tr = ToolResult(
                tool_name=str(msg.name or "unknown"),
                args=args,
                result=str(msg.content),
                iteration=iter_counter,
            )
            state.tool_results.append(tr)
            state._log_tool_results.append(tr)
            iter_counter += 1

        state.iteration = len(state.tool_call_history)
        return state

    def _make_error_state(self, query: str, session_id: str, error_msg: str) -> AgentState:
        state = AgentState(query=query, session_id=session_id)
        state.error = error_msg
        state.final_answer = (
            "Xin loi, co loi xay ra trong qua trinh xu ly. "
            "Vui long thu lai hoac lien he Phong Dao tao de duoc ho tro."
        )
        return state
