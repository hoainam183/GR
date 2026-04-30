"""Tests for Week 1 tool adapters.

Run unit-only checks:
    pytest src/RAG_v2/tests/test_adapters.py -v -m "not integration"
"""

from __future__ import annotations

import pytest

from agent import tool_adapters
from agent.tool_adapters import _clarify_question, execute_tool


class TestExecuteToolRouter:
    """Router-only behavior that does not require retrieval services."""

    def test_unknown_tool_returns_error_string(self) -> None:
        result = execute_tool("nonexistent_tool", {})
        assert "[Loi he thong:" in result
        assert "nonexistent_tool" in result

    def test_wrong_args_returns_error_string(self) -> None:
        # rag_search missing required "collection" arg
        result = execute_tool("rag_search", {"query": "test"})
        assert "[Loi:" in result
        assert "Tham so" in result

    def test_clarify_question_no_api_needed(self) -> None:
        result = _clarify_question(
            message="Ban muon hoi ve hoc bong nao?",
            options=["Hoc bong KKHT", "Hoc bong tai tro", "Hoc bong toan phan"],
        )
        assert "[CLARIFY]" in result
        assert "KKHT" in result
        assert "1." in result

    def test_clarify_question_fills_default_options_when_missing(self) -> None:
        result = _clarify_question(
            message="Ban muon so sanh theo cach nao?",
            options=[],
        )
        assert "[CLARIFY]" in result
        assert "1." in result
        assert "2." in result
        assert "3." in result

    def test_clarify_question_compare_uses_generic_non_mixed_options(self) -> None:
        result = _clarify_question(
            message="Ban muon so sanh mon lap trinh mang giua hai nganh/khoa nao?",
            options=[
                "So sanh IT-E6 vs IT-E7",
                "So sanh K65 vs K70",
                "So sanh IT-E6 va K65",
            ],
        )
        assert "[CLARIFY]" in result
        assert "hai ma nganh hay hai ma khoa" in result
        assert "IT-E6 va K65" not in result
        assert "1." in result
        assert "2." in result
        assert "3." in result

    def test_compare_programs_major_codes_dispatches_per_major(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """compare_programs (not compare_cohorts) is the correct tool for major codes."""
        calls: list[dict[str, str | None]] = []

        def _fake_rag_search(
            query: str,
            collection: str,
            top_k: int | None = None,
            resolved_cohort: str | None = None,
            resolved_major: str | None = None,
        ) -> str:
            calls.append(
                {
                    "query": query,
                    "collection": collection,
                    "resolved_cohort": resolved_cohort,
                    "resolved_major": resolved_major,
                }
            )
            return f"OK:{resolved_major or resolved_cohort or 'none'}"

        monkeypatch.setattr(tool_adapters, "_rag_search", _fake_rag_search)

        result = execute_tool(
            "compare_programs",
            {
                "topic": "môn mạng máy tính",
                "major_a": "IT-E7",
                "major_b": "IT-E6",
                "collection": "chuong_trinh",
            },
        )

        assert len(calls) == 2
        assert calls[0]["resolved_major"] == "IT-E7"
        assert calls[1]["resolved_major"] == "IT-E6"
        assert calls[0]["collection"] == "chuong_trinh"
        assert calls[1]["collection"] == "chuong_trinh"
        assert "IT-E7" in result
        assert "IT-E6" in result

    def test_compare_programs_course_keyword_focuses_major_queries(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """compare_programs with course_keyword dispatches per major and includes the keyword."""
        calls: list[dict[str, str | None]] = []

        def _fake_rag_search(
            query: str,
            collection: str,
            top_k: int | None = None,
            resolved_cohort: str | None = None,
            resolved_major: str | None = None,
        ) -> str:
            calls.append(
                {
                    "query": query,
                    "collection": collection,
                    "resolved_cohort": resolved_cohort,
                    "resolved_major": resolved_major,
                }
            )
            return f"OK:{resolved_major or resolved_cohort or 'none'}"

        monkeypatch.setattr(tool_adapters, "_rag_search", _fake_rag_search)

        result = execute_tool(
            "compare_programs",
            {
                "topic": "",
                "course_keyword": "Lập trình mạng",
                "major_a": "IT-E7",
                "major_b": "IT-E6",
                "collection": "chuong_trinh",
            },
        )

        assert len(calls) == 2
        assert calls[0]["resolved_major"] == "IT-E7"
        assert calls[1]["resolved_major"] == "IT-E6"
        assert "Lập trình mạng" in str(calls[0]["query"])
        assert "Lập trình mạng" in str(calls[1]["query"])
        assert "IT-E7" in result
        assert "IT-E6" in result

    def test_compare_cohorts_rejects_mixed_major_and_cohort(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """compare_cohorts rejects a mix of major code (IT-E6) and cohort (K65)."""
        calls: list[dict[str, str | None]] = []

        def _fake_rag_search(
            query: str,
            collection: str,
            top_k: int | None = None,
            resolved_cohort: str | None = None,
            resolved_major: str | None = None,
        ) -> str:
            calls.append(
                {
                    "query": query,
                    "collection": collection,
                    "resolved_cohort": resolved_cohort,
                    "resolved_major": resolved_major,
                }
            )
            return "unexpected"

        monkeypatch.setattr(tool_adapters, "_rag_search", _fake_rag_search)

        result = execute_tool(
            "compare_cohorts",
            {
                "topic": "mon lap trinh mang",
                "cohort_a": "IT-E6",
                "cohort_b": "K65",
                "collection": "chuong_trinh",
            },
        )

        # The rejection message uses Unicode Vietnamese — check key concepts
        assert "compare_programs" in result  # steers user to correct tool
        assert calls == []  # no search calls should be made


class TestRagSearch:
    """Integration checks requiring Qdrant/Elasticsearch + local models."""

    @pytest.mark.integration
    def test_rag_search_quy_dinh(self) -> None:
        result = execute_tool(
            "rag_search",
            {
                "query": "dieu kien tot nghiep",
                "collection": "quy_dinh",
            },
        )
        assert isinstance(result, str)
        assert len(result) > 50
        assert "Khong tim thay" not in result

    @pytest.mark.integration
    def test_rag_search_invalid_collection(self) -> None:
        result = execute_tool(
            "rag_search",
            {
                "query": "test",
                "collection": "invalid_collection_xyz",
            },
        )
        assert "[Loi:" in result

    @pytest.mark.integration
    def test_multi_rag_search_returns_multiple_sections(self) -> None:
        result = execute_tool(
            "multi_rag_search",
            {
                "queries": [
                    {"query": "dieu kien tot nghiep", "collection": "quy_dinh"},
                    {"query": "tin chi tich luy", "collection": "chuong_trinh"},
                ]
            },
        )
        assert "---" in result
        assert "quy_dinh" in result
        assert "chuong_trinh" in result

    @pytest.mark.integration
    def test_compare_cohorts_returns_both_cohorts(self) -> None:
        result = execute_tool(
            "compare_cohorts",
            {
                "topic": "hoc bong KKHT",
                "cohort_a": "K65",
                "cohort_b": "K70",
                "collection": "quy_dinh",
            },
        )
        assert "K65" in result
        assert "K70" in result


class TestWebSearch:
    """Integration check for Tavily tool path."""

    @pytest.mark.integration
    def test_web_search_returns_content(self) -> None:
        result = execute_tool(
            "web_search",
            {
                "query": "Dai hoc Bach Khoa Ha Noi thong bao moi",
            },
        )
        assert isinstance(result, str)
        if "Tavily chua duoc cau hinh" in result:
            pytest.skip("Tavily API key is not configured for this environment")
        assert len(result) > 100
