from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Maximum number of tool results kept in context for the LLM.
# Older results are still preserved in _log_tool_results for MongoDB logging.
_CONTEXT_WINDOW_TOOL_LIMIT = 3


@dataclass
class ToolResult:
    """Single tool execution record stored in the agent state."""

    tool_name: str
    args: dict[str, Any]
    result: str
    iteration: int
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool_name,
            "args": self.args,
            "result": self.result,
            "iteration": self.iteration,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
        }

    def __getitem__(self, key: str) -> Any:
        # Backward compatibility: legacy code may access tool results as dict items.
        return self.to_dict()[key]


@dataclass
class AgentState:
    """
    Central agent state carried across Planner-Executor execution.

    tool_results vs _log_tool_results
    -----------------------------------
    ``tool_results``     — latest _CONTEXT_WINDOW_TOOL_LIMIT results injected into
                           LLM context via get_context_summary().  Kept small to
                           avoid overwhelming Qwen 8B's context window.
    ``_log_tool_results`` — complete, untruncated list used by to_log_dict() for
                            MongoDB logging.  Never discards entries.
    """

    query: str
    session_id: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    tool_call_history: list[str] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 4
    final_answer: str | None = None
    route: str = "complex"  # simple | complex | chitchat
    error: str | None = None
    execution_path: str | None = None
    complexity_subtype: str | None = None
    sub_questions: list[str] | None = None
    retrieval_plan: dict[str, Any] | None = None
    decompose_trace: dict[str, Any] | None = None
    planner_trace: dict[str, Any] | None = None
    executor_results: list[dict[str, Any]] = field(default_factory=list)
    synthesis_trace: dict[str, Any] | None = None

    # Private: full log preserved for MongoDB — never truncated
    _log_tool_results: list[ToolResult] = field(
        default_factory=list, init=False, repr=False
    )

    def is_done(self) -> bool:
        return (
            self.final_answer is not None
            or self.iteration >= self.max_iterations
            or self.error is not None
        )

    def add_tool_result(
        self,
        tool_name: str,
        args: dict[str, Any] | str,
        result: str | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        """Append tool output.

        Supports both signatures for backward compatibility:
        - add_tool_result(tool_name, args_dict, result)
        - add_tool_result(tool_name, result_string)
        """
        if result is None:
            parsed_args: dict[str, Any] = {}
            parsed_result = str(args)
        else:
            if not isinstance(args, dict):
                raise TypeError("args must be a dict when result is provided")
            parsed_args = args
            parsed_result = result

        tr = ToolResult(
            tool_name=tool_name,
            args=parsed_args,
            result=parsed_result,
            iteration=self.iteration,
            latency_ms=latency_ms,
        )

        # Full log — never truncated (used by to_log_dict / MongoDB)
        self._log_tool_results.append(tr)

        # Context window — limited to last N results (used by get_context_summary / LLM)
        self.tool_results.append(tr)
        if len(self.tool_results) > _CONTEXT_WINDOW_TOOL_LIMIT:
            self.tool_results = self.tool_results[-_CONTEXT_WINDOW_TOOL_LIMIT:]

        self.tool_call_history.append(tool_name)


    def get_context_summary(self) -> str:
        """Return last N tool results formatted for LLM context injection."""
        if not self.tool_results:
            return "Chua co ket qua tim kiem."
        parts: list[str] = []
        for tr in self.tool_results:
            parts.append(f"[Ket qua tu {tr.tool_name}]\n{tr.result}")
        return "\n\n---\n\n".join(parts)

    def to_log_dict(self) -> dict[str, Any]:
        """Serialise to MongoDB-ready dict.  Uses the complete untruncated log."""
        all_results = self._log_tool_results or self.tool_results
        payload: dict[str, Any] = {
            "query": self.query,
            "session_id": self.session_id,
            "route": self.route,
            "iterations": self.iteration,
            "tool_calls": [tr.to_dict() for tr in all_results],
            "tool_names_sequence": self.tool_call_history,
            "final_answer_length": len(self.final_answer) if self.final_answer else 0,
            "error": self.error,
        }
        if self.execution_path is not None:
            payload["execution_path"] = self.execution_path
        if self.complexity_subtype is not None:
            payload["complexity_subtype"] = self.complexity_subtype
        if self.sub_questions is not None:
            payload["sub_questions"] = self.sub_questions
        if self.retrieval_plan is not None:
            payload["retrieval_plan"] = self.retrieval_plan
        if self.decompose_trace is not None:
            payload["decompose_trace"] = self.decompose_trace
        if self.planner_trace is not None:
            payload["planner_trace"] = self.planner_trace
        if self.executor_results:
            payload["executor_results"] = self.executor_results
        if self.synthesis_trace is not None:
            payload["synthesis_trace"] = self.synthesis_trace
        return payload
