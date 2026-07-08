"""Tests for api/response_mapper — ChatResponseMapper.

Run:
    pytest tests/test_response_mapper.py -v
"""

from __future__ import annotations

from typing import Any


class TestNormalizeV3Result:
    def test_backfills_missing_fields(self) -> None:
        from api.response_mapper import ChatResponseMapper

        result = ChatResponseMapper.normalize_v3_result(
            {"answer": "ok", "question": "q"},
            session_id="sid-1",
        )
        assert result["session_id"] == "sid-1"
        assert result["tools_used"] == []
        assert result["tool_calls"] == []
        assert result["iterations"] == 0
        assert result["agent_trace"] is None

    def test_does_not_overwrite_existing_session_id(self) -> None:
        from api.response_mapper import ChatResponseMapper

        result = ChatResponseMapper.normalize_v3_result(
            {"session_id": "original"},
            session_id="fallback",
        )
        assert result["session_id"] == "original"

    def test_converts_sources_to_retrieved_documents(self) -> None:
        from api.response_mapper import ChatResponseMapper

        result = ChatResponseMapper.normalize_v3_result(
            {
                "sources": [
                    {"text": "doc content", "score": 0.9, "metadata": {"source": "test"}}
                ]
            },
            session_id="s",
        )
        docs = result["retrieved_documents"]
        assert len(docs) == 1
        assert docs[0]["content"] == "doc content"

    def test_filters_empty_structured_rows_from_retrieved_documents(self) -> None:
        from api.response_mapper import ChatResponseMapper

        result = ChatResponseMapper.normalize_v3_result(
            {
                "sources": [
                    {
                        "subject_code": "CH1012",
                        "subject_name": "Hóa học 1",
                        "exam_room": "D3-201",
                    }
                ]
            },
            session_id="s",
        )
        assert result["retrieved_documents"] == []

    def test_accepts_chunk_text_sources(self) -> None:
        from api.response_mapper import ChatResponseMapper

        result = ChatResponseMapper.normalize_v3_result(
            {"sources": [{"chunk_text": "chunk body", "metadata": {"source": "doc.pdf"}}]},
            session_id="s",
        )
        assert result["retrieved_documents"][0]["content"] == "chunk body"

    def test_backfills_tool_calls_from_agent_trace(self) -> None:
        from api.response_mapper import ChatResponseMapper

        result = ChatResponseMapper.normalize_v3_result(
            {
                "tool_calls": [],
                "agent_trace": {
                    "tool_calls": [{"tool": "rag_search", "args": {}, "result": "x", "iteration": 0}],
                    "tool_names_sequence": ["rag_search"],
                },
            },
            session_id="s",
        )
        assert result["tools_used"] == ["rag_search"]
        assert len(result["tool_calls"]) == 1


class TestToFilterModels:
    def test_dict_input(self) -> None:
        from api.response_mapper import ChatResponseMapper

        raw = {
            "quy_dinh": {"applied": True, "matched_ids": 5, "filter_desc": "major=IT-E6"},
        }
        models = ChatResponseMapper.to_filter_models(raw)
        assert models is not None
        assert len(models) == 1
        assert models[0].collection == "quy_dinh"
        assert models[0].applied is True
        assert models[0].matched_ids == 5

    def test_list_input(self) -> None:
        from api.response_mapper import ChatResponseMapper
        from schemas.chat import FilterInfo

        raw = [FilterInfo(collection="ctdt", applied=False, matched_ids=0)]
        models = ChatResponseMapper.to_filter_models(raw)
        assert models is not None
        assert models[0].collection == "ctdt"

    def test_none_and_empty_returns_none(self) -> None:
        from api.response_mapper import ChatResponseMapper

        assert ChatResponseMapper.to_filter_models(None) is None
        assert ChatResponseMapper.to_filter_models({}) is None
        assert ChatResponseMapper.to_filter_models([]) is None


class TestToCollectionResultModels:
    def test_dict_input(self) -> None:
        from api.response_mapper import ChatResponseMapper

        raw = {
            "quy_dinh": {"vector": 10, "keyword": 5},
        }
        models = ChatResponseMapper.to_collection_result_models(raw)
        assert models is not None
        assert models[0].collection == "quy_dinh"
        assert models[0].vector_count == 10
        assert models[0].keyword_count == 5

    def test_empty_returns_none(self) -> None:
        from api.response_mapper import ChatResponseMapper

        assert ChatResponseMapper.to_collection_result_models(None) is None
        assert ChatResponseMapper.to_collection_result_models({}) is None


class TestToChatResponse:
    def _rag_result(self) -> dict[str, Any]:
        return {
            "question": "Điều kiện tốt nghiệp?",
            "answer": "Cần 120 tín chỉ.",
            "sources": [
                {
                    "text": "Tốt nghiệp cần 120 TC",
                    "score": 0.85,
                    "metadata": {"source": "quy_dinh"},
                }
            ],
            "num_sources": 1,
            "model_name": "gemini",
            "intent": "rag",
            "mode": "rag_v2",
            "route": "simple",
        }

    def test_rag_response_fields(self) -> None:
        from api.response_mapper import ChatResponseMapper

        resp = ChatResponseMapper.to_chat_response(
            self._rag_result(),
            fallback_question="fallback",
            session_id="s-1",
        )
        assert resp.question == "Điều kiện tốt nghiệp?"
        assert resp.answer == "Cần 120 tín chỉ."
        assert resp.num_documents == 1
        assert resp.session_id == "s-1"
        assert resp.mode == "rag_v2"
        assert resp.route == "simple"

    def test_retrieved_documents_populated(self) -> None:
        from api.response_mapper import ChatResponseMapper

        resp = ChatResponseMapper.to_chat_response(
            self._rag_result(),
            fallback_question="q",
            session_id="s",
        )
        assert len(resp.retrieved_documents) == 1
        assert resp.retrieved_documents[0].score == 0.85

    def test_fallback_question_used_when_missing(self) -> None:
        from api.response_mapper import ChatResponseMapper

        resp = ChatResponseMapper.to_chat_response(
            {"answer": "ok"},
            fallback_question="My fallback",
            session_id="s",
        )
        assert resp.question == "My fallback"

    def test_preserves_extended_debug_trace_fields(self) -> None:
        from api.response_mapper import ChatResponseMapper

        resp = ChatResponseMapper.to_chat_response(
            {
                "answer": "ok",
                "context_trace": {"context_docs_used": 2},
                "rerank_trace": {"rerank_candidate_count": 4},
                "answer_quality_gate": {"answer_status": "answered"},
                "fusion_weights": {"vector": 0.7, "keyword": 0.3},
                "answer_status": "answered",
                "agent_trace": {
                    "query": "q",
                    "sub_questions": ["q1", "q2"],
                    "planner_trace": {"raw_response_preview": "{}"},
                    "executor_results": [{"query": "q1", "empty_result": False}],
                    "synthesis_trace": {"context_chars": 1200},
                },
            },
            fallback_question="q",
            session_id="s",
        )

        assert resp.context_trace == {"context_docs_used": 2}
        assert resp.rerank_trace == {"rerank_candidate_count": 4}
        assert resp.answer_quality_gate == {"answer_status": "answered"}
        assert resp.fusion_weights == {"vector": 0.7, "keyword": 0.3}
        assert resp.answer_status == "answered"
        assert resp.agent_trace is not None
        assert resp.agent_trace.sub_questions == ["q1", "q2"]
        assert resp.agent_trace.planner_trace == {"raw_response_preview": "{}"}
        assert resp.agent_trace.executor_results == [{"query": "q1", "empty_result": False}]
        assert resp.agent_trace.synthesis_trace == {"context_chars": 1200}


class TestIsValidApiKey:
    def test_empty_key_invalid(self) -> None:
        from agent.tool_adapters import _is_valid_api_key

        assert _is_valid_api_key("") is False

    def test_sentinel_values_invalid(self) -> None:
        from agent.tool_adapters import _is_valid_api_key

        for bad in ["your-key-here", "CHANGE_ME", "tvly-xxx", "your-tavily-api-key-here"]:
            assert _is_valid_api_key(bad) is False, f"Expected invalid: {bad!r}"

    def test_realistic_key_valid(self) -> None:
        from agent.tool_adapters import _is_valid_api_key

        assert _is_valid_api_key("tvly-AbcXyzRealKey12345") is True

    def test_key_with_spaces_invalid(self) -> None:
        from agent.tool_adapters import _is_valid_api_key

        assert _is_valid_api_key("  ") is False


class TestSetRuntime:
    def test_set_runtime_injects_mock(self) -> None:
        """set_runtime() should allow injecting a mock for testing."""
        import agent.tool_adapters as ta
        from unittest.mock import MagicMock

        mock_runtime = MagicMock()
        ta.set_runtime(mock_runtime)
        try:
            assert ta._get_runtime() is mock_runtime
        finally:
            ta.set_runtime(None)  # reset to allow lazy init on next real call
