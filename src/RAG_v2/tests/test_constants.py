"""Tests for schemas/constants — RouteMode, PipelineMode, and CLARIFY_SENTINEL.

Run:
    pytest tests/test_constants.py -v
"""

from __future__ import annotations

import pytest


class TestClarifySentinel:
    def test_sentinel_is_string(self) -> None:
        from schemas.constants import CLARIFY_SENTINEL

        assert isinstance(CLARIFY_SENTINEL, str)

    def test_sentinel_value(self) -> None:
        from schemas.constants import CLARIFY_SENTINEL

        assert CLARIFY_SENTINEL == "[CLARIFY]"

    def test_clarify_tool_uses_sentinel(self) -> None:
        """_clarify_question output must start with the sentinel constant."""
        from schemas.constants import CLARIFY_SENTINEL
        from agent.tool_adapters import _clarify_question

        result = _clarify_question(
            message="Test message",
            options=["Option A", "Option B"],
        )
        assert result.startswith(CLARIFY_SENTINEL)

    def test_react_agent_strips_sentinel_correctly(self) -> None:
        """_relay_last_clarify_output must strip sentinel using the constant."""
        from schemas.constants import CLARIFY_SENTINEL
        from langchain_core.messages import ToolMessage

        fake_state = {
            "tool_call_history": ["clarify_question"],
            "messages": [
                ToolMessage(
                    content=f"{CLARIFY_SENTINEL}\nWhat do you want?",
                    tool_call_id="tc-1",
                    name="clarify_question",
                )
            ],
        }
        from agent.react_agent import ReActAgent

        result = ReActAgent._relay_last_clarify_output(fake_state)
        assert result == "What do you want?"
        assert CLARIFY_SENTINEL not in result


class TestRouteModeConstants:
    def test_route_modes_exist(self) -> None:
        from schemas.constants import RouteMode

        assert RouteMode.AUTO == "auto"
        assert RouteMode.RAG == "rag"
        assert RouteMode.AGENT == "agent"

    def test_pipeline_modes_exist(self) -> None:
        from schemas.constants import PipelineMode

        assert PipelineMode.RAG_V2 == "rag_v2"
        assert PipelineMode.RAG_V2_FALLBACK == "rag_v2_fallback"
        assert PipelineMode.AGENT == "agent"

    def test_agent_routes_exist(self) -> None:
        from schemas.constants import AgentRoute

        assert AgentRoute.AGENT_FORCED == "agent_forced"
        assert AgentRoute.COMPLEX == "complex"
        assert AgentRoute.SIMPLE == "simple"
        assert AgentRoute.CHITCHAT == "chitchat"
