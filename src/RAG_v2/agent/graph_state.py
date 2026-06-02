from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class AgentGraphState(TypedDict):
    """
    LangGraph runtime state — used exclusively inside graph node execution.

    Intentionally separate from AgentState (dataclass) which is used for
    MongoDB logging. Keeping the two decoupled prevents the LangGraph
    execution layer from depending on the persistence layer.

    Fields
    ------
    messages
        Full conversation + tool call history accumulated by add_messages reducer.
        The reducer appends / merges instead of overwriting, so nodes only need
        to return the *new* messages they produce.
    tool_call_history
        Ordered list of executor tool names, preserved for trace/log output.
    tool_call_signatures
        Legacy compatibility list for callers that still inspect exact tool
        signatures. The Planner-Executor graph does not use it for routing.
    """

    messages: Annotated[list, add_messages]
    query: str
    session_id: str
    tool_call_history: list[str]
    tool_call_signatures: list[str]
    iteration: int
    max_iterations: int
    final_answer: str | None
    error: str | None

    # Planner-Executor path
    execution_path: str | None          # "planner" for current graph topology
    sub_questions: list[str] | None     # Decomposed sub-questions from complex query
    retrieval_plan: dict | None         # Planner output: {steps, needs_web, reasoning}
    complexity_subtype: str | None      # Router subtype used to select execution path
    decompose_trace: dict | None        # Trace-only decomposition metadata
    planner_trace: dict | None          # Trace-only planner prompt/response metadata
    executor_results: list[dict] | None # Trace-only executor per-step summaries
    synthesis_trace: dict | None        # Trace-only synthesis prompt/context metadata
    user_context: dict | None           # {student_id, cohort, major, major_code, full_name}
    empty_result_count: int             # Tracks consecutive empty tool returns for retry logic
    top_k: int | None                   # Effective retrieval top_k supplied by the pipeline
