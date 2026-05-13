"""Tests for RAGPipeline — all heavy components are mocked so no GPU/services needed."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock, patch

import pytest

# Make sure pipeline package is importable without real model deps
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # src/RAG_v2

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(idx: int, score: float = 0.9) -> Dict[str, Any]:
    return {
        "id": f"doc_{idx}",
        "text": f"Nội dung tài liệu số {idx}.",
        "score": score,
        "rerank_score": score - 0.05,
        "metadata": {"title": f"Tài liệu {idx}", "source": f"doc_{idx}.md"},
        "collection": "stsv",
    }


def _make_pipeline(intent: str = "rag") -> Any:
    """Return a RAGPipeline where every component is replaced by a MagicMock."""
    # Patch all heavy import targets before the module is imported / instantiated
    with (
        patch("pipeline.rag_pipeline.QueryRouter") as MockRouter,
        patch("pipeline.rag_pipeline.BGEm3Embedder") as MockBGE,
        patch("pipeline.rag_pipeline.E5MultilingualEmbedder") as MockE5,
        patch("pipeline.rag_pipeline.MultiCollectionSearch") as MockSearch,
        patch("pipeline.rag_pipeline.BGEReranker") as MockReranker,
        patch("pipeline.rag_pipeline.ChatModel") as MockChat,
        patch("pipeline.rag_pipeline.load_dotenv"),
    ):
        # Router
        mock_router_inst = MagicMock()
        mock_router_inst.route.return_value = {"intent": intent}
        MockRouter.return_value = mock_router_inst

        # Embedders
        mock_bge_inst = MagicMock()
        mock_bge_inst.embed_query.return_value = [0.1] * 1024
        MockBGE.return_value = mock_bge_inst

        mock_e5_inst = MagicMock()
        mock_e5_inst.embed_query.return_value = [0.2] * 1024
        MockE5.return_value = mock_e5_inst

        # Searcher (factory class method)
        mock_search_inst = MagicMock()
        mock_search_inst.search.return_value = [_make_doc(i) for i in range(10)]
        MockSearch.from_collection_names.return_value = mock_search_inst

        # Reranker
        mock_reranker_inst = MagicMock()
        mock_reranker_inst.rerank.return_value = [
            _make_doc(i) for i in range(5)
        ]
        MockReranker.return_value = mock_reranker_inst

        # Chat model
        mock_chat_inst = MagicMock()
        mock_chat_inst.model = "gemini-3.1-flash-lite-preview"
        mock_chat_inst.generate.return_value = "Câu trả lời từ LLM."
        mock_chat_inst.generate_stream.return_value = iter(
            ["Câu ", "trả lời ", "streaming."]
        )
        MockChat.return_value = mock_chat_inst

        from pipeline.rag_pipeline import RAGPipeline

        pipeline = RAGPipeline(api_key="test-key")

    # Expose mocks for assertion inside tests
    pipeline._router = mock_router_inst
    pipeline._bge = mock_bge_inst
    pipeline._e5 = mock_e5_inst
    pipeline._searcher = mock_search_inst
    pipeline._reranker = mock_reranker_inst
    pipeline._chat = mock_chat_inst
    return pipeline


# ---------------------------------------------------------------------------
# Tests — query() RAG flow
# ---------------------------------------------------------------------------


class TestRAGPipelineQuery:
    def test_rag_returns_answer_and_sources(self):
        pipeline = _make_pipeline(intent="rag")
        result = pipeline.query("Điều kiện học bổng là gì?")

        assert result["question"] == "Điều kiện học bổng là gì?"
        assert result["answer"] == "Câu trả lời từ LLM."
        assert result["intent"] == "rag"
        assert result["num_sources"] == 5
        assert len(result["sources"]) == 5
        assert result["model_name"] == "gemini-3.1-flash-lite-preview"

    def test_rag_calls_embed_and_search(self):
        pipeline = _make_pipeline(intent="rag")
        pipeline.query("Câu hỏi kiểm tra embed")

        pipeline._bge.embed_query.assert_called_once_with(
            "Câu hỏi kiểm tra embed"
        )
        pipeline._e5.embed_query.assert_called_once_with(
            "Câu hỏi kiểm tra embed"
        )
        pipeline._searcher.search.assert_called_once()

    def test_rag_calls_reranker(self):
        pipeline = _make_pipeline(intent="rag")
        pipeline.query("Câu hỏi kiểm tra rerank")

        pipeline._reranker.rerank.assert_called_once()
        call_kwargs = pipeline._reranker.rerank.call_args
        assert call_kwargs.kwargs["query"] == "Câu hỏi kiểm tra rerank"

    def test_rag_generates_with_rag_mode(self):
        pipeline = _make_pipeline(intent="rag")
        pipeline.query("Câu hỏi nào đó")

        pipeline._chat.generate.assert_called_once()
        _, kwargs = pipeline._chat.generate.call_args
        assert kwargs.get("mode") == "rag"
        assert kwargs.get("context") is not None

    def test_rag_top_k_override(self):
        pipeline = _make_pipeline(intent="rag")
        pipeline.query("Câu hỏi", top_k=3)

        search_kwargs = pipeline._searcher.search.call_args.kwargs
        # over-fetch: top_k * 4
        assert search_kwargs["top_k"] == 12

    def test_rag_passes_history_to_chat(self):
        pipeline = _make_pipeline(intent="rag")
        history = [
            {"role": "user", "content": "Xin chào"},
            {"role": "assistant", "content": "Chào bạn!"},
        ]
        pipeline.query("Câu hỏi có history", history=history)

        _, kwargs = pipeline._chat.generate.call_args
        assert kwargs.get("history") == history

    def test_rag_history_trimmed_to_6(self):
        pipeline = _make_pipeline(intent="rag")
        long_history = [
            {"role": "user", "content": f"msg {i}"} for i in range(20)
        ]
        pipeline.query("Câu hỏi", history=long_history)

        _, kwargs = pipeline._chat.generate.call_args
        assert len(kwargs.get("history", [])) == 6


# ---------------------------------------------------------------------------
# Tests — query() chitchat flow
# ---------------------------------------------------------------------------


class TestRAGPipelineChitchat:
    def test_chitchat_skips_retrieval(self):
        pipeline = _make_pipeline(intent="chitchat")
        result = pipeline.query("Xin chào!")

        pipeline._bge.embed_query.assert_not_called()
        pipeline._e5.embed_query.assert_not_called()
        pipeline._searcher.search.assert_not_called()
        pipeline._reranker.rerank.assert_not_called()

    def test_chitchat_returns_empty_sources(self):
        pipeline = _make_pipeline(intent="chitchat")
        result = pipeline.query("Xin chào!")

        assert result["intent"] == "chitchat"
        assert result["sources"] == []
        assert result["num_sources"] == 0

    def test_chitchat_uses_chitchat_mode(self):
        pipeline = _make_pipeline(intent="chitchat")
        pipeline.query("Xin chào!")

        pipeline._chat.generate.assert_called_once()
        _, kwargs = pipeline._chat.generate.call_args
        assert kwargs.get("mode") == "chitchat"


# ---------------------------------------------------------------------------
# Tests — query_stream()
# ---------------------------------------------------------------------------


class TestRAGPipelineStream:
    def test_stream_yields_chunks_rag(self):
        pipeline = _make_pipeline(intent="rag")
        chunks = list(pipeline.query_stream("Câu hỏi stream"))

        assert chunks == ["Câu ", "trả lời ", "streaming."]

    def test_stream_sets_last_sources(self):
        pipeline = _make_pipeline(intent="rag")
        list(pipeline.query_stream("Câu hỏi stream"))

        assert hasattr(pipeline, "last_sources")
        assert len(pipeline.last_sources) == 5

    def test_stream_chitchat_skips_retrieval(self):
        pipeline = _make_pipeline(intent="chitchat")
        chunks = list(pipeline.query_stream("Xin chào"))

        pipeline._searcher.search.assert_not_called()
        assert chunks == ["Câu ", "trả lời ", "streaming."]

    def test_stream_calls_generate_stream(self):
        pipeline = _make_pipeline(intent="rag")
        list(pipeline.query_stream("Câu hỏi"))

        pipeline._chat.generate_stream.assert_called_once()
        _, kwargs = pipeline._chat.generate_stream.call_args
        assert kwargs.get("mode") == "rag"


# ---------------------------------------------------------------------------
# Tests — _format_context helper
# ---------------------------------------------------------------------------


class TestFormatContext:
    def test_formats_all_documents(self):
        from pipeline.rag_pipeline import _format_context

        docs = [_make_doc(i) for i in range(3)]
        ctx = _format_context(docs)

        assert "[1]" in ctx
        assert "[2]" in ctx
        assert "[3]" in ctx
        assert "Tài liệu 0" in ctx

    def test_empty_docs_returns_empty_string(self):
        from pipeline.rag_pipeline import _format_context

        assert _format_context([]) == ""

    def test_separator_between_docs(self):
        from pipeline.rag_pipeline import _format_context

        docs = [_make_doc(0), _make_doc(1)]
        ctx = _format_context(docs)
        assert "---" in ctx


# ---------------------------------------------------------------------------
# Tests — _trim_history helper
# ---------------------------------------------------------------------------


class TestTrimHistory:
    def test_trims_to_limit(self):
        from pipeline.rag_pipeline import _trim_history

        history = [{"role": "user", "content": str(i)} for i in range(20)]
        trimmed = _trim_history(history, limit=6)
        assert len(trimmed) == 6
        assert trimmed[-1]["content"] == "19"

    def test_short_history_unchanged(self):
        from pipeline.rag_pipeline import _trim_history

        history = [{"role": "user", "content": "hi"}]
        assert _trim_history(history, limit=6) == history

    def test_empty_history_returns_empty(self):
        from pipeline.rag_pipeline import _trim_history

        assert _trim_history([]) == []


# ---------------------------------------------------------------------------
# Entry point for quick manual run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
