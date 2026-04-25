from __future__ import annotations

from typing import Annotated, TypedDict

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
        Ordered list of tool names that have been executed.  Used for
        coarse-grained loop detection (same name called twice).
    tool_call_signatures
        List of "toolname:arghash" strings.  Used for exact-duplicate detection
        (same name AND same arguments) so the agent is not penalised for
        legitimately calling rag_search with different collections.
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