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
from .planning import (
    ResolvedScope,
    _content_to_text,
    _hash_text,
    _is_empty_result_text,
    _normalise_plan_steps_for_entities as _normalise_plan_steps_impl,
    _parse_json_object as _parse_json_object_impl,
    _preview_text,
    _trace_plan_step,
    resolve_entity_scope,
)
from .prompts import PLANNER_SYSTEM_PROMPT, SYNTHESIS_PROMPT
from .state import AgentState, ToolResult, _CONTEXT_WINDOW_TOOL_LIMIT
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


def _normalise_plan_steps_for_entities(
    steps: list[Any],
    source_query: str,
    user_context: dict[str, Any] | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Ground major/cohort scope to the resolved entity scope (query-first,
    profile-fallback when ``user_context`` is supplied)."""
    return _normalise_plan_steps_impl(steps, source_query, user_context)

def _parse_json_object(content: Any) -> dict[str, Any]:
    """Parse strict JSON object content, accepting optional markdown fences."""
    return _parse_json_object_impl(content)


def _non_empty_labeled_results(
    labeled_results: list[tuple[str, str]],
) -> list[tuple[int, str, str]]:
    return [
        (index, label, result)
        for index, (label, result) in enumerate(labeled_results)
        if not _is_empty_result_text(result)
    ]


class ReActAgent:
    """
    Planner-Executor agent with the legacy ReActAgent public name.

    The ReAct tool loop and the separate decompose node have been removed. The
    planner now handles both query break-down (comparison / multi-aspect) and
    collection routing in a single LLM call; ``complexity_subtype`` is passed as
    a prompt hint instead of gating a decompose pre-step. The graph is now:

    START -> planner -> executor? -> synthesize -> END
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
        # When every plan step returns empty, retry once with major/cohort filters
        # dropped before falling back to "không tìm thấy" — recovers complex
        # questions whose filter was too narrow (e.g. wrong/missing cohort).
        self._retry_on_empty: bool = bool(
            getattr(settings, "agent_retry_on_empty", True)
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
            "execution_path": "planner",
            "sub_questions": None,
            "retrieval_plan": None,
            "complexity_subtype": complexity_subtype,
            "decompose_trace": None,
            "planner_trace": None,
            "executor_results": None,
            "synthesis_trace": None,
            "user_context": user_context,
            "empty_result_count": 0,
            "top_k": top_k,
        }

        logger.info(
            "[Agent] Starting query: '%s...' (subtype=%s)", query[:80], complexity_subtype
        )
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

    @staticmethod
    def _scope_prompt_hint(scope: "ResolvedScope") -> str:
        """Advisory prompt hint stating the resolved entity scope.

        Only advisory: the resolved major/cohort is enforced deterministically by
        the step grounding in ``_normalise_plan_steps_for_entities``, so this hint
        merely steers the LLM toward producing aligned query text. In comparison
        (multi-major) mode ``scope.major`` is ``None`` and no major is forced.
        """
        ctx_parts: list[str] = []
        if scope.major:
            ctx_parts.append(f"Ma nganh: {scope.major}")
        if scope.cohort:
            ctx_parts.append(f"Khoa sinh vien: {scope.cohort}")
        if not ctx_parts:
            return ""
        return (
            "\nThong tin ap dung cho moi step (dung dung ma nay, KHONG doi sang "
            f"ma khac): {', '.join(ctx_parts)}"
        )

    @staticmethod
    def _subtype_hint(complexity_subtype: str | None) -> str:
        """Steer the single planner call by the router-provided complexity subtype.

        Replaces the old decompose pre-step: instead of a separate LLM call to
        split the query, the planner is told what shape to expect so it emits the
        right multi-step plan in one pass.
        """
        if complexity_subtype == "comparison":
            return (
                "\n[Goi y] Day la cau SO SANH — tach thanh cac step rieng cho tung "
                "doi tuong (nganh/khoa), cung collection, khac major_hint/cohort_hint."
            )
        if complexity_subtype == "multi_source":
            return (
                "\n[Goi y] Cau nay can thong tin tu NHIEU nguon — sinh step cho tung "
                "khia canh va collection lien quan."
            )
        return ""

    def _planner_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Generate and validate a retrieval plan (break-down + routing in one call)."""
        from retrieval.metadata_filters import enrich_major_references_for_query  # noqa: PLC0415

        enriched_query = enrich_major_references_for_query(state["query"])
        user_context = state.get("user_context")
        # Resolve the authoritative entity scope ONCE (query-first, profile
        # fallback). It drives both the planner prompt (advisory) and the
        # deterministic step grounding below — so correctness no longer depends
        # on the LLM copying the right major from the prompt.
        scope = resolve_entity_scope(enriched_query, user_context)
        prompt = (
            f"Cau hoi: {enriched_query}"
            f"{self._subtype_hint(state.get('complexity_subtype'))}"
            f"{self._scope_prompt_hint(scope)}"
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
            return {
                "retrieval_plan": None,
                "planner_trace": {
                    "prompt_hash": _hash_text(prompt),
                    "prompt_preview": _preview_text(prompt, 1500),
                    "error": str(exc),
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                },
                "error": f"planner_invalid_json: {exc}",
            }

        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            steps = []
        plan["steps"], entity_hint_trace = _normalise_plan_steps_for_entities(
            steps[:4],
            enriched_query,
            user_context,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        planner_trace = {
            "prompt_hash": _hash_text(prompt),
            "prompt_preview": _preview_text(prompt, 1500),
            "raw_response_preview": _preview_text(response.content, 2000),
            "latency_ms": round(elapsed_ms, 2),
            "reasoning": _preview_text(plan.get("reasoning", ""), 1000),
            "needs_web": bool(plan.get("needs_web")),
            "steps": [
                _trace_plan_step(step, state.get("top_k"))
                for step in plan["steps"]
                if isinstance(step, dict)
            ],
        }
        if entity_hint_trace.get("major_hint") or entity_hint_trace.get("cohort_hint"):
            planner_trace["entity_hint_normalization"] = entity_hint_trace

        if not plan["steps"]:
            logger.warning("[Planner] Empty plan")
            return {
                "retrieval_plan": plan,
                "planner_trace": planner_trace,
                "error": "planner_empty_steps",
            }

        if not self._validate_plan(plan):
            return {
                "retrieval_plan": plan,
                "planner_trace": planner_trace,
                "error": "planner_invalid_plan",
            }

        logger.info(
            "[Planner] %d steps in %.0fms: %s",
            len(plan["steps"]),
            elapsed_ms,
            plan.get("reasoning", ""),
        )
        return {"retrieval_plan": plan, "planner_trace": planner_trace}

    def _executor_node(self, state: AgentGraphState) -> dict[str, Any]:
        """Execute a validated retrieval plan in parallel."""
        plan = state.get("retrieval_plan") or {}
        steps = self._valid_plan_steps(plan.get("steps", []))
        if not steps:
            return {
                "final_answer": _PLANNER_ERROR_ANSWER,
                "error": "planner_empty_steps",
                "executor_results": [],
            }

        steps, labeled_results, elapsed_ms, retried_relaxed = (
            self._execute_steps_with_optional_relaxation(steps, state.get("top_k"))
        )
        self._log_executor_completion(
            labeled_results,
            steps,
            elapsed_ms,
            retried_relaxed,
        )
        executor_results = self._executor_result_trace(
            steps,
            labeled_results,
            state.get("top_k"),
            elapsed_ms,
        )
        new_history = [f"planned_rag_search:{label}" for label, _ in labeled_results]
        tool_messages = self._rag_tool_messages(labeled_results)

        # Web is a fallback, not an always-on companion: only reach out when the
        # RAG steps produced nothing usable, so a planner-set needs_web does not
        # waste a Tavily call (and dilute synthesis) when the DB already answered.
        if plan.get("needs_web") and not tool_messages:
            self._append_web_executor_result(
                state["query"],
                new_history,
                executor_results,
                tool_messages,
            )

        if not tool_messages:
            # A valid plan that returns nothing (even after relax-retry + web)
            # signals the pipeline to fall back to classic RAG, which has other
            # recall paths (HyDE/expansion). final_answer stays as a safety-net
            # for callers that suppress the fallback.
            return {
                "final_answer": _NO_INFO_ANSWER,
                "error": "agent_no_results",
                "tool_call_history": new_history,
                "executor_results": executor_results,
            }

        return {
            "messages": tool_messages,
            "tool_call_history": new_history,
            "executor_results": executor_results,
        }

    def _execute_steps_with_optional_relaxation(
        self,
        steps: list[dict[str, Any]],
        top_k: int | None,
    ) -> tuple[list[dict[str, Any]], list[tuple[str, str]], float, bool]:
        t0 = time.perf_counter()
        labeled_results = execute_retrieval_plan(steps, top_k=top_k)
        retried_relaxed = False
        if self._should_retry_relaxed(labeled_results):
            relaxed_steps = self._relaxed_steps(steps)
            if relaxed_steps is not None:
                relaxed_results = self._execute_relaxed_steps(relaxed_steps, top_k)
                if any(
                    not _is_empty_result_text(result) for _, result in relaxed_results
                ):
                    labeled_results = relaxed_results
                    steps = relaxed_steps
                    retried_relaxed = True

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return steps, labeled_results, elapsed_ms, retried_relaxed

    def _should_retry_relaxed(self, labeled_results: list[tuple[str, str]]) -> bool:
        return (
            self._retry_on_empty
            and bool(labeled_results)
            and all(_is_empty_result_text(result) for _, result in labeled_results)
        )

    @staticmethod
    def _execute_relaxed_steps(
        relaxed_steps: list[dict[str, Any]],
        top_k: int | None,
    ) -> list[tuple[str, str]]:
        logger.info(
            "[Executor] All %d step(s) empty; retrying without major/cohort filters",
            len(relaxed_steps),
        )
        return execute_retrieval_plan(relaxed_steps, top_k=top_k)

    @staticmethod
    def _log_executor_completion(
        labeled_results: list[tuple[str, str]],
        steps: list[dict[str, Any]],
        elapsed_ms: float,
        retried_relaxed: bool,
    ) -> None:
        logger.info(
            "[Executor] %d/%d steps completed in %.0fms%s",
            len(labeled_results),
            len(steps),
            elapsed_ms,
            " (relaxed retry)" if retried_relaxed else "",
        )

    @staticmethod
    def _executor_result_trace(
        steps: list[dict[str, Any]],
        labeled_results: list[tuple[str, str]],
        top_k: int | None,
        elapsed_ms: float,
    ) -> list[dict[str, Any]]:
        return [
            {
                **_trace_plan_step(steps[index] if index < len(steps) else {}, top_k),
                "label": label,
                "result_chars": len(str(result or "")),
                "empty_result": _is_empty_result_text(result),
                "latency_ms": round(elapsed_ms / max(len(labeled_results), 1), 2),
            }
            for index, (label, result) in enumerate(labeled_results)
        ]

    def _rag_tool_messages(
        self,
        labeled_results: list[tuple[str, str]],
    ) -> list[ToolMessage]:
        return [
            ToolMessage(
                content=f"### {label}\n{result}"[: self._tool_result_limit],
                tool_call_id=f"plan_{step_index}",
                name="rag_search",
            )
            for step_index, label, result in _non_empty_labeled_results(labeled_results)
        ]

    def _append_web_executor_result(
        self,
        query: str,
        new_history: list[str],
        executor_results: list[dict[str, Any]],
        tool_messages: list[ToolMessage],
    ) -> None:
        web_result = web_search_for_executor(query=query)
        new_history.append("planned_web_search")
        executor_results.append(
            {
                "label": "web_search",
                "query": query,
                "collection": "web",
                "result_chars": len(str(web_result or "")),
                "empty_result": _is_empty_result_text(web_result),
            }
        )
        if not _is_empty_result_text(web_result):
            tool_messages.append(
                ToolMessage(
                    content=web_result[: self._tool_result_limit],
                    tool_call_id="plan_web",
                    name="web_search",
                )
            )

    @staticmethod
    def _relaxed_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Return steps with major/cohort filters dropped, or ``None`` to skip.

        Returns ``None`` when no step carried a major/cohort hint — there is
        nothing to relax, so retrying would just repeat the identical search.
        """
        relaxed: list[dict[str, Any]] = []
        changed = False
        for step in steps:
            new_step = dict(step)
            if new_step.get("major_hint") or new_step.get("cohort_hint"):
                new_step["major_hint"] = None
                new_step["cohort_hint"] = None
                changed = True
            relaxed.append(new_step)
        return relaxed if changed else None

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
        prompt = f"Cau hoi: {state['query']}\n\nThong tin tim duoc:\n{context}"
        t0 = time.perf_counter()
        try:
            response = self._synthesis_llm.invoke(
                [
                    SystemMessage(content=SYNTHESIS_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
            answer = _content_to_text(response.content).strip() or _NO_INFO_ANSWER
        except Exception as exc:
            logger.error("[Agent] Synthesis LLM failed: %s", exc)
            answer = f"Thong tin tim duoc:\n{tool_contents[0][:500]}"

        return {
            "final_answer": answer,
            "synthesis_trace": {
                "context_chars": len(context),
                "prompt_hash": _hash_text(prompt),
                "prompt_preview": _preview_text(prompt, 1500),
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "answer_chars": len(answer),
            },
        }

    def _build_graph(self) -> Any:
        graph = StateGraph(AgentGraphState)  # type: ignore

        graph.add_node("planner", self._planner_node)
        graph.add_node("executor", self._executor_node)
        graph.add_node("synthesize", self._synthesize_node)

        graph.add_edge(START, "planner")
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
        state.execution_path = graph_result.get("execution_path")
        state.complexity_subtype = graph_result.get("complexity_subtype")
        state.sub_questions = graph_result.get("sub_questions")
        state.decompose_trace = graph_result.get("decompose_trace")
        state.planner_trace = graph_result.get("planner_trace")
        state.synthesis_trace = graph_result.get("synthesis_trace")

        plan_steps = []
        plan = graph_result.get("retrieval_plan")
        if isinstance(plan, dict) and isinstance(plan.get("steps"), list):
            state.retrieval_plan = plan
            plan_steps = [step for step in plan["steps"] if isinstance(step, dict)]
        executor_results = graph_result.get("executor_results")
        if isinstance(executor_results, list):
            state.executor_results = [
                result for result in executor_results if isinstance(result, dict)
            ]

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

        # Enforce the same context-window cap as AgentState.add_tool_result so the
        # LLM-facing tool_results list cannot grow unbounded; _log_tool_results
        # keeps the full, untruncated history for logging.
        if len(state.tool_results) > _CONTEXT_WINDOW_TOOL_LIMIT:
            state.tool_results = state.tool_results[-_CONTEXT_WINDOW_TOOL_LIMIT:]
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
