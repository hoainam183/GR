"""Shared constants for the RAG v2 system.

Centralises magic strings that previously appeared scattered across
api/routes/chat.py, agent/react_agent.py, and agent/tool_adapters.py.
"""

from __future__ import annotations


# Legacy clarify sentinel retained only for backward-compatible consumers.
# Current Planner-Executor code does not emit clarify tool output.

CLARIFY_SENTINEL: str = "[CLARIFY]"


# ─── Route / mode identifiers ─────────────────────────────────────────────────


class RouteMode:
    """Values accepted by the ``mode`` field of ``ChatRequest``."""

    AUTO: str = "auto"
    RAG: str = "rag"
    AGENT: str = "agent"


class PipelineMode:
    """Values set on the ``mode`` field of pipeline result dicts."""

    RAG_V2: str = "rag_v2"
    RAG_V2_FALLBACK: str = "rag_v2_fallback"
    AGENT: str = "agent"


class AgentRoute:
    """Values used for the ``route`` / ``intent`` fields in agent results."""

    AGENT_FORCED: str = "agent_forced"
    COMPLEX: str = "complex"
    SIMPLE: str = "simple"
    CHITCHAT: str = "chitchat"
