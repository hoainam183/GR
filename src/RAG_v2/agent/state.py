from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ToolResult:
    """Single tool execution record stored in the agent state."""

    tool_name: str
    args: dict[str, Any]
    result: str
    iteration: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool_name,
            "args": self.args,
            "result": self.result,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
        }

    def __getitem__(self, key: str) -> Any:
        # Backward compatibility: legacy code may access tool results as dict items.
        return self.to_dict()[key]


@dataclass
class AgentState:
    """Central agent state carried across ReAct iterations."""

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
    _tool_call_signatures: set[str] = field(default_factory=set, init=False, repr=False)

    def is_done(self) -> bool:
        return (
            self.final_answer is not None
            or self.iteration >= self.max_iterations
            or self.error is not None
        )

    def has_called_tool(self, tool_name: str, args: dict[str, Any] | None = None) -> bool:
        """Check whether a tool (optionally with the same args) was called before."""
        if args is None:
            return tool_name in self.tool_call_history
        return self._build_call_signature(tool_name, args) in self._tool_call_signatures

    def add_tool_result(
        self,
        tool_name: str,
        args: dict[str, Any] | str,
        result: str | None = None,
    ) -> None:
        """Append tool output.

        Supports both signatures for backward compatibility:
        - add_tool_result(tool_name, args_dict, result)
        - add_tool_result(tool_name, result)
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
        )
        self.tool_results.append(tr)
        self.tool_call_history.append(tool_name)
        self._tool_call_signatures.add(self._build_call_signature(tool_name, parsed_args))

        # Keep only the latest 3 tool results to avoid context bloat on small models.
        if len(self.tool_results) > 3:
            self.tool_results = self.tool_results[-3:]

    def get_context_summary(self) -> str:
        if not self.tool_results:
            return "Chua co ket qua tim kiem."
        parts: list[str] = []
        for tr in self.tool_results:
            parts.append(f"[Ket qua tu {tr.tool_name}]\n{tr.result}")
        return "\n\n---\n\n".join(parts)

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "session_id": self.session_id,
            "route": self.route,
            "iterations": self.iteration,
            "tool_calls": [tr.to_dict() for tr in self.tool_results],
            "tool_names_sequence": self.tool_call_history,
            "final_answer_length": len(self.final_answer) if self.final_answer else 0,
            "error": self.error,
        }

    @staticmethod
    def _build_call_signature(tool_name: str, args: dict[str, Any]) -> str:
        try:
            serialized_args = json.dumps(args, ensure_ascii=False, sort_keys=True)
        except TypeError:
            # Fallback for non-JSON-serializable tool args.
            serialized_args = repr(args)
        return f"{tool_name}:{serialized_args}"