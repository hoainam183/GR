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
