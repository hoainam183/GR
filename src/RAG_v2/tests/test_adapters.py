"""Tests for Week 1 tool adapters.

Run unit-only checks:
    pytest src/RAG_v2/tests/test_adapters.py -v -m "not integration"
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent import tool_adapters
from agent.tool_adapters import (
    _rag_search,
    _format_search_results,
    _format_web_results,
    execute_tool,
    get_agent_docs,
    init_agent_docs,
    set_runtime,
)


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

    def test_format_search_results_uses_agent_result_settings(self) -> None:
        results = [
            {
                "text": f"noi dung {i} " + ("x" * 100),
                "metadata": {"title": f"doc-{i}"},
            }
            for i in range(5)
        ]
        settings = SimpleNamespace(
            agent_search_result_count=4,
            agent_search_result_char_limit=30,
            agent_tool_result_limit=3000,
        )

        formatted = _format_search_results(results, "chuong_trinh", settings)

        assert "[4]" in formatted
        assert "[5]" not in formatted
        assert "x" * 31 not in formatted

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

    def test_rag_search_passes_runtime_retrieval_knobs(self) -> None:
        settings = SimpleNamespace(
            top_k=5,
            raw_candidate_multiplier=3.0,
            raw_candidate_min=12,
            vector_top_k=31,
            keyword_top_k=32,
            vector_pool_k=33,
            keyword_pool_k=34,
            reranker_min_top_k=4,
            reranker_score_threshold=-1.0,
            reranker_table_score_threshold=-2.0,
            parent_context_enabled=False,
            agent_search_result_count=3,
            agent_search_result_char_limit=500,
            agent_tool_result_limit=3000,
        )
        bge = SimpleNamespace(embed_query=lambda _query: [0.1])
        e5 = SimpleNamespace(embed_query=lambda _query: [0.2])
        searcher = MagicMock(
            search=MagicMock(
                return_value=[
                    {
                        "text": "noi dung hoc bong",
                        "metadata": {"title": "doc"},
                    }
                ]
            )
        )
        reranker = MagicMock(
            rerank=MagicMock(
                return_value=[
                    {
                        "text": "noi dung hoc bong",
                        "metadata": {"title": "doc"},
                    }
                ]
            )
        )
        runtime = tool_adapters._AdapterRuntime(
            settings=settings,
            bge_embedder=bge,
            e5_embedder=e5,
            searcher=searcher,
            reranker=reranker,
            tavily_tool=None,
        )

        tool_adapters.cache_clear()
        init_agent_docs()
        set_runtime(runtime)
        try:
            result = _rag_search("hoc bong KKHT", "quy_dinh", top_k=6)
        finally:
            set_runtime(None)
            tool_adapters.cache_clear()

        assert "noi dung hoc bong" in result
        search_kwargs = searcher.search.call_args.kwargs
        assert search_kwargs["top_k"] == 18
        assert search_kwargs["vector_top_k"] == 31
        assert search_kwargs["keyword_top_k"] == 32
        assert search_kwargs["vector_pool_k"] == 33
        assert search_kwargs["keyword_pool_k"] == 34
        rerank_kwargs = reranker.rerank.call_args.kwargs
        assert rerank_kwargs["top_k"] == 6
        assert rerank_kwargs["min_top_k"] == 4
        assert rerank_kwargs["score_threshold"] == -1.0
        assert rerank_kwargs["table_score_threshold"] == -2.0


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

    def test_format_web_results_dedupes_by_url(self) -> None:
        init_agent_docs()
        result = _format_web_results({
            "answer": "short",
            "results": [
                {
                    "title": "A",
                    "url": "https://ctt.hust.edu.vn/a",
                    "content": "first",
                },
                {
                    "title": "A duplicate",
                    "url": "https://ctt.hust.edu.vn/a",
                    "content": "duplicate",
                },
                {
                    "title": "B",
                    "url": "https://ctt.hust.edu.vn/b",
                    "content": "second",
                },
            ],
        })

        assert result.count("URL:") == 2
        assert len(get_agent_docs()) == 2

    def test_format_web_results_treats_none_answer_as_empty(self) -> None:
        result = _format_web_results({"answer": None, "results": []})

        assert result == "Khong tim thay thong tin tren web."

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
        if result == "Khong tim thay thong tin tren web.":
            pytest.skip("Tavily returned no web content for this environment")
        assert len(result) > 100
