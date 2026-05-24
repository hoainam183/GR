"""Tests for Phase 2 features: HyDE, Contextual Retrieval, Multi-Query Service.

Run with: python -m pytest tests/retrieval/test_phase2_features.py -v
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest


# ===========================================================================
# HyDE Tests
# ===========================================================================


class TestHyDEExpander:
    """Verify HyDE hypothesis generation and embedding."""

    def test_generate_hypothesis_calls_llm(self):
        """HyDE should call LLM with properly formatted prompt."""
        from retrieval.hyde import HyDEExpander

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Sinh viên cần đạt IELTS 5.5 để tốt nghiệp."
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 1024

        hyde = HyDEExpander(llm=mock_llm, embedder=mock_embedder)
        hypothesis = hyde.generate_hypothesis("điều kiện ngoại ngữ tốt nghiệp")

        mock_llm.generate.assert_called_once()
        assert "IELTS" in hypothesis

    def test_generate_embedding_uses_hypothesis(self):
        """Embedding should be of the hypothesis, not the original query."""
        from retrieval.hyde import HyDEExpander

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Hypothesis answer about regulations."
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.5] * 1024

        hyde = HyDEExpander(llm=mock_llm, embedder=mock_embedder)
        vec = hyde.generate_embedding("test query")

        # embedder should be called with the hypothesis, not "test query"
        mock_embedder.embed_query.assert_called_once_with(
            "Hypothesis answer about regulations."
        )
        assert len(vec) == 1024

    def test_generate_hypothesis_truncates_long_output(self):
        """Long hypotheses should be truncated."""
        from retrieval.hyde import HyDEExpander

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "x" * 2000
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 10

        hyde = HyDEExpander(llm=mock_llm, embedder=mock_embedder, max_hypothesis_len=100)
        hypothesis = hyde.generate_hypothesis("test")

        assert len(hypothesis) == 100

    def test_generate_hypothesis_fallback_on_error(self):
        """On LLM error, hypothesis should fall back to original query."""
        from retrieval.hyde import HyDEExpander

        mock_llm = MagicMock()
        mock_llm.generate.side_effect = RuntimeError("API error")
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 10

        hyde = HyDEExpander(llm=mock_llm, embedder=mock_embedder)
        hypothesis = hyde.generate_hypothesis("original query")

        assert hypothesis == "original query"


class TestShouldUseHyde:
    """Verify HyDE trigger conditions."""

    def test_triggers_on_few_results(self):
        """Should trigger when fewer results than threshold."""
        from retrieval.hyde import should_use_hyde

        results = [{"id": "1"}, {"id": "2"}]
        assert should_use_hyde(results, min_results=3) is True

    def test_does_not_trigger_on_enough_results(self):
        """Should not trigger when enough results with good scores."""
        from retrieval.hyde import should_use_hyde

        results = [{"id": str(i)} for i in range(5)]
        stats = {"rerank_score_mean": 0.8}
        assert should_use_hyde(results, stats, min_results=3) is False

    def test_triggers_on_low_confidence(self):
        """Should trigger when reranker mean score is low."""
        from retrieval.hyde import should_use_hyde

        results = [{"id": str(i)} for i in range(10)]
        stats = {"rerank_score_mean": 0.1}
        assert should_use_hyde(results, stats, confidence_threshold=0.3) is True

    def test_does_not_trigger_without_stats(self):
        """Without reranker stats and enough results, should not trigger."""
        from retrieval.hyde import should_use_hyde

        results = [{"id": str(i)} for i in range(5)]
        assert should_use_hyde(results, None) is False


# ===========================================================================
# Contextual Retrieval Tests
# ===========================================================================


class TestChunkContextualizer:
    """Verify chunk contextualization at indexing time."""

    def test_contextualize_adds_prefix(self):
        """Chunks should get a contextual prefix."""
        from chunking.contextualizer import ChunkContextualizer

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Điều kiện tốt nghiệp về ngoại ngữ cho sinh viên chính quy"

        ctx = ChunkContextualizer(llm=mock_llm)
        chunks = [
            {
                "content": "Sinh viên phải đạt IELTS 5.5 hoặc tương đương để được xét tốt nghiệp đại học chính quy.",
                "metadata": {"level": "child", "hierarchy_path": "Quy định TN > Ngoại ngữ"},
            }
        ]
        doc_meta = {"title": "Quy định tốt nghiệp 2024", "doc_type": "Quy định", "collection": "quydinh"}

        result = ctx.contextualize(chunks, doc_meta)

        assert len(result) == 1
        assert result[0]["content"].startswith("[")
        assert "Sinh viên phải đạt IELTS 5.5" in result[0]["content"]

    def test_skips_parent_chunks(self):
        """Parent chunks should not be contextualized."""
        from chunking.contextualizer import ChunkContextualizer

        mock_llm = MagicMock()
        ctx = ChunkContextualizer(llm=mock_llm)

        chunks = [
            {
                "content": "This is a parent chunk with lots of text that should be skipped during indexing.",
                "metadata": {"level": "parent"},
            }
        ]
        result = ctx.contextualize(chunks)

        mock_llm.generate.assert_not_called()
        assert not result[0]["content"].startswith("[")

    def test_skips_short_chunks(self):
        """Very short chunks should not be contextualized."""
        from chunking.contextualizer import ChunkContextualizer

        mock_llm = MagicMock()
        ctx = ChunkContextualizer(llm=mock_llm)

        chunks = [{"content": "Short.", "metadata": {}}]
        result = ctx.contextualize(chunks)

        mock_llm.generate.assert_not_called()

    def test_handles_llm_failure_gracefully(self):
        """LLM failure should not crash — chunk remains unchanged."""
        from chunking.contextualizer import ChunkContextualizer

        mock_llm = MagicMock()
        mock_llm.generate.side_effect = RuntimeError("LLM unavailable")

        ctx = ChunkContextualizer(llm=mock_llm)
        original_content = "A" * 100  # Long enough to not be skipped
        chunks = [{"content": original_content, "metadata": {"level": "child"}}]

        result = ctx.contextualize(chunks)
        assert result[0]["content"] == original_content

    def test_contextualize_single(self):
        """Single chunk contextualization convenience method."""
        from chunking.contextualizer import ChunkContextualizer

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Quy định về học bổng khuyến khích"

        ctx = ChunkContextualizer(llm=mock_llm)
        result = ctx.contextualize_single(
            chunk_text="Sinh viên đạt GPA >= 3.2 được xét học bổng loại A, mức 100% học phí.",
            doc_title="Quy chế học bổng",
            hierarchy_path="Học bổng > Loại A",
        )

        assert result.startswith("[Quy định về học bổng khuyến khích]")
        assert "GPA >= 3.2" in result


# ===========================================================================
# Service Integration Tests (Multi-Query + HyDE)
# ===========================================================================


class TestRetrievalServiceMultiQuery:
    """Test multi-query expansion in RetrievalService."""

    def _build_mock_service(self):
        """Build a RetrievalService with mocked dependencies."""
        from retrieval.service import RetrievalService

        mock_settings = MagicMock()
        mock_settings.top_k = 5
        mock_settings.vector_top_k = 20
        mock_settings.keyword_top_k = 20
        mock_settings.vector_pool_k = 15
        mock_settings.keyword_pool_k = 15
        mock_settings.collections = ["stsv", "quydinh"]

        mock_bge = MagicMock()
        mock_bge.embed_query.return_value = [0.1] * 1024
        mock_e5 = MagicMock()
        mock_e5.embed_query.return_value = [0.2] * 1024

        mock_searcher = MagicMock()
        mock_searcher.search.return_value = [
            {"id": "doc1", "text": "result 1", "metadata": {}, "score": 0.9},
            {"id": "doc2", "text": "result 2", "metadata": {}, "score": 0.8},
        ]

        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [
            {"id": "doc1", "text": "result 1", "metadata": {}, "score": 0.9, "rerank_score": 2.5},
        ]

        service = RetrievalService(
            settings=mock_settings,
            bge_embedder=mock_bge,
            e5_embedder=mock_e5,
            searcher=mock_searcher,
            reranker=mock_reranker,
        )
        return service, mock_searcher, mock_reranker

    def test_multi_query_calls_searcher_multiple_times(self):
        """Multi-query should search multiple variants."""
        service, mock_searcher, _ = self._build_mock_service()

        results = service.search(
            "điều kiện tốt nghiệp IT-E6",
            use_multi_query=True,
            entities={"major_code": "IT-E6"},
        )

        # Should call searcher more than once (one per variant)
        assert mock_searcher.search.call_count >= 2

    def test_multi_query_deduplicates(self):
        """Results from multiple queries should be deduplicated."""
        service, mock_searcher, mock_reranker = self._build_mock_service()

        # Both variants return same docs
        mock_searcher.search.return_value = [
            {"id": "doc1", "text": "same", "metadata": {}, "score": 0.9},
        ]
        mock_reranker.rerank.side_effect = lambda **kwargs: kwargs["documents"][:kwargs["top_k"]]

        results = service.search(
            "test query with IT-E6",
            use_multi_query=True,
            entities={"major_code": "IT-E6"},
        )

        # Dedup should collapse identical IDs
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids))

    def test_without_entities_skips_expansion(self):
        """Without entities, multi_query flag should fall back to single search."""
        service, mock_searcher, _ = self._build_mock_service()

        service.search("simple query", use_multi_query=True, entities=None)

        # Without entities, expander produces only 1 variant → falls through
        # to single search path
        assert mock_searcher.search.call_count == 1

    def test_backward_compatible_search(self):
        """Old-style search call (no new params) should still work."""
        service, mock_searcher, _ = self._build_mock_service()

        results = service.search("điều kiện tốt nghiệp")

        mock_searcher.search.assert_called_once()
        assert len(results) > 0


class TestRetrievalServiceHyDE:
    """Test HyDE integration in RetrievalService."""

    def test_search_with_hyde_uses_hypothesis_embedding(self):
        """HyDE search should embed the hypothesis, not the raw query."""
        from retrieval.service import RetrievalService

        mock_settings = MagicMock()
        mock_settings.top_k = 5
        mock_settings.vector_top_k = 20
        mock_settings.keyword_top_k = 20
        mock_settings.vector_pool_k = 15
        mock_settings.keyword_pool_k = 15
        mock_settings.collections = ["stsv"]

        mock_bge = MagicMock()
        mock_bge.embed_query.return_value = [0.5] * 1024
        mock_e5 = MagicMock()
        mock_e5.embed_query.return_value = [0.3] * 1024

        mock_searcher = MagicMock()
        mock_searcher.search.return_value = [
            {"id": "doc1", "text": "result", "metadata": {}, "score": 0.9},
        ]

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Hypothetical answer about graduation requirements."

        service = RetrievalService(
            settings=mock_settings,
            bge_embedder=mock_bge,
            e5_embedder=mock_e5,
            searcher=mock_searcher,
        )

        results = service.search_with_hyde("graduation requirements", llm=mock_llm)

        # LLM should have been called for hypothesis
        mock_llm.generate.assert_called_once()
        # BGE embedder should embed the hypothesis
        bge_call_arg = mock_bge.embed_query.call_args[0][0]
        assert "Hypothetical answer" in bge_call_arg
        assert len(results) >= 1
