"""End-to-end tests for Week 3 routing integration.

Requires Qdrant/Elasticsearch and LM Studio to be running locally.
Run:
    pytest tests/test_e2e.py -v -m e2e
"""

from __future__ import annotations

import unittest.mock as mock

import pytest

from config.settings import Settings
from pipeline.rag_pipeline import RAGPipeline


@pytest.fixture(scope="module")
def pipeline() -> RAGPipeline:
    try:
        return RAGPipeline(Settings())
    except Exception as exc:
        pytest.skip(f"E2E dependencies are unavailable: {exc}")


@pytest.mark.e2e
class TestRouting:
    def test_chitchat_routed_correctly(self, pipeline: RAGPipeline) -> None:
        result = pipeline.query_v3("xin chào")
        assert result["mode"] == "chitchat"
        assert result["answer"] is not None

    def test_simple_uses_rag_pipeline(self, pipeline: RAGPipeline) -> None:
        result = pipeline.query_v3("Điều kiện xét học bổng KKHT là gì?")
        assert result["mode"] in {"rag_v2", "rag_v2_fallback"}
        assert result["answer"] is not None

    def test_complex_uses_agent(self, pipeline: RAGPipeline) -> None:
        if pipeline.agent is None:
            pytest.skip("Agent is disabled in current settings")

        result = pipeline.query_v3("So sánh học bổng KKHT giữa K65 và K70")
        assert result["mode"] in {"agent", "rag_v2_fallback"}
        assert result["answer"] is not None
        if result["mode"] == "agent":
            assert len(result.get("tools_used", [])) > 0

    def test_graduation_uses_multi_rag(self, pipeline: RAGPipeline) -> None:
        if pipeline.agent is None:
            pytest.skip("Agent is disabled in current settings")

        result = pipeline.query_v3("Tôi đủ điều kiện tốt nghiệp chưa?")
        assert result["mode"] in {"agent", "rag_v2_fallback"}
        if result["mode"] == "agent":
            assert "multi_rag_search" in result.get("tools_used", [])

    def test_agent_fallback_on_failure(self, pipeline: RAGPipeline) -> None:
        if pipeline.agent is None:
            pytest.skip("Agent is disabled in current settings")

        with mock.patch.object(
            pipeline.agent,
            "run",
            side_effect=Exception("Connection refused"),
        ):
            result = pipeline.query_v3("So sánh K65 và K70")
            assert result["answer"] is not None
            assert result["mode"] == "rag_v2_fallback"


@pytest.mark.e2e
class TestAnswerQuality:
    def test_answer_not_empty(self, pipeline: RAGPipeline) -> None:
        result = pipeline.query_v3("Điều kiện xét học bổng KKHT?")
        assert len(result["answer"]) > 50

    def test_answer_in_vietnamese(self, pipeline: RAGPipeline) -> None:
        result = pipeline.query_v3("Lịch thi học kỳ 1 khi nào?")
        vietnamese_chars = set("àáâãèéêìíòóôõùúăđ")
        assert any(c in result["answer"].lower() for c in vietnamese_chars)

    def test_comparison_mentions_both_cohorts(self, pipeline: RAGPipeline) -> None:
        result = pipeline.query_v3("So sánh học bổng KKHT K65 và K70")
        answer_lower = result["answer"].lower()
        assert "k65" in answer_lower or "K65" in result["answer"]
        assert "k70" in answer_lower or "K70" in result["answer"]
