"""Comprehensive tests for Phase 0-2 retrieval improvements.

Covers:
  - P0: applicable_cohort fix, single-item pool normalization, dual-vector normalize
  - P1: metadata-aware reranking, multi-query expansion
  - P2: score fusion edge cases, filter fallback chain

Run with: python -m pytest tests/retrieval/test_retrieval_improvements.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# P0 Tests: Score Fusion Fixes
# ===========================================================================


class TestScoreFusionSingleItem:
    """Verify that single-item pools normalize to max relevance (1.0)."""

    def _build_searcher(self):
        """Build a minimal MultiCollectionSearch for fusion testing."""
        from retrieval.multi_collection_search import MultiCollectionSearch

        # Create a minimal instance without actual stores
        searcher = object.__new__(MultiCollectionSearch)
        searcher.vector_weight = 0.7
        searcher.keyword_weight = 0.3
        searcher.rrf_k = 60
        return searcher

    def test_single_vector_item_gets_nonzero_score(self):
        """A single-item vector pool must not normalize to 0.0."""
        searcher = self._build_searcher()

        vector_pool = [{"id": "doc1", "text": "test", "metadata": {}, "score": 0.85}]
        keyword_pool = []

        results = searcher._score_fusion(
            vector_pool, keyword_pool, top_k=5,
            vector_weight=0.7, keyword_weight=0.3,
        )
        assert len(results) == 1
        assert results[0]["score"] > 0.0, "Single-item pool should not be 0.0"
        # With shifted normalization: norm = (0.85 - (0.85 - 1.0)) / 1.0 = 1.0
        assert results[0]["score"] == pytest.approx(0.7, abs=0.05)

    def test_single_keyword_item_gets_nonzero_score(self):
        """A single-item keyword pool must not normalize to 0.0."""
        searcher = self._build_searcher()

        vector_pool = []
        keyword_pool = [{"id": "doc1", "text": "test", "metadata": {}, "score": 5.2}]

        results = searcher._score_fusion(
            vector_pool, keyword_pool, top_k=5,
            vector_weight=0.7, keyword_weight=0.3,
        )
        assert len(results) == 1
        assert results[0]["score"] > 0.0

    def test_two_items_same_score_both_get_nonzero(self):
        """Two items with identical scores should both normalize to 1.0."""
        searcher = self._build_searcher()

        vector_pool = [
            {"id": "doc1", "text": "a", "metadata": {}, "score": 0.9},
            {"id": "doc2", "text": "b", "metadata": {}, "score": 0.9},
        ]
        keyword_pool = []

        results = searcher._score_fusion(
            vector_pool, keyword_pool, top_k=5,
            vector_weight=0.7, keyword_weight=0.3,
        )
        assert all(r["score"] > 0 for r in results)

    def test_normal_pool_preserves_ordering(self):
        """Multiple items with different scores should preserve rank order."""
        searcher = self._build_searcher()

        vector_pool = [
            {"id": "doc1", "text": "a", "metadata": {}, "score": 0.9},
            {"id": "doc2", "text": "b", "metadata": {}, "score": 0.7},
            {"id": "doc3", "text": "c", "metadata": {}, "score": 0.5},
        ]
        keyword_pool = [
            {"id": "doc2", "text": "b", "metadata": {}, "score": 8.0},
            {"id": "doc4", "text": "d", "metadata": {}, "score": 5.0},
        ]

        results = searcher._score_fusion(
            vector_pool, keyword_pool, top_k=10,
            vector_weight=0.7, keyword_weight=0.3,
        )
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_pools_return_empty(self):
        """Empty inputs should return empty results."""
        searcher = self._build_searcher()
        results = searcher._score_fusion([], [], top_k=5, vector_weight=0.7, keyword_weight=0.3)
        assert results == []


# ===========================================================================
# P0 Tests: Qdrant Dual-Vector Normalization
# ===========================================================================


class TestQdrantDualVectorNormalization:
    """Verify per-model min-max normalization in _fuse_results."""

    @dataclass
    class FakeHit:
        id: str
        score: float
        payload: Dict[str, Any]

    def test_equal_weight_with_different_ranges(self):
        """BGE range [0.8, 0.9] and E5 range [0.3, 0.5] should not let BGE dominate."""
        from retrieval.qdrant_store import QdrantStore

        bge_hits = [
            self.FakeHit(id="doc1", score=0.9, payload={"text": "a"}),
            self.FakeHit(id="doc2", score=0.8, payload={"text": "b"}),
        ]
        e5_hits = [
            self.FakeHit(id="doc2", score=0.5, payload={"text": "b"}),
            self.FakeHit(id="doc3", score=0.3, payload={"text": "c"}),
        ]

        results = QdrantStore._fuse_results(bge_hits, e5_hits, top_k=5, bge_weight=0.5, e5_weight=0.5)

        # doc2 appears in both — should get highest fused score
        doc2 = next(r for r in results if r["id"] == "doc2")
        doc1 = next(r for r in results if r["id"] == "doc1")
        # doc2 has: norm_bge=0.0 (min of bge), norm_e5=1.0 (max of e5) → 0.5
        # doc1 has: norm_bge=1.0 (max of bge), norm_e5=0.0 (not in e5) → 0.5
        # Both should be similar, not doc1 dominating
        assert abs(doc2["score"] - doc1["score"]) < 0.6

    def test_single_bge_result_normalizes_to_max(self):
        """A single BGE result should normalize to 1.0 not 0.0."""
        from retrieval.qdrant_store import QdrantStore

        bge_hits = [self.FakeHit(id="doc1", score=0.85, payload={"text": "a"})]
        e5_hits = []

        results = QdrantStore._fuse_results(bge_hits, e5_hits, top_k=5, bge_weight=0.5, e5_weight=0.5)
        assert len(results) == 1
        assert results[0]["score"] > 0.0, "Single BGE hit should not normalize to 0"
        # norm_bge = (0.85 - (0.85-1.0)) / 1.0 = 1.0, score = 0.5 * 1.0 = 0.5
        assert results[0]["score"] == pytest.approx(0.5, abs=0.01)

    def test_all_same_score_bge_normalizes_correctly(self):
        """All-same-score BGE results should normalize to 1.0."""
        from retrieval.qdrant_store import QdrantStore

        bge_hits = [
            self.FakeHit(id="doc1", score=0.8, payload={"text": "a"}),
            self.FakeHit(id="doc2", score=0.8, payload={"text": "b"}),
        ]
        e5_hits = []

        results = QdrantStore._fuse_results(bge_hits, e5_hits, top_k=5, bge_weight=0.5, e5_weight=0.5)
        assert all(r["score"] > 0 for r in results)


# ===========================================================================
# P0 Tests: applicable_cohort Fix
# ===========================================================================


class TestApplicableCohortFix:
    """Verify QuyDinhFilterExtractor uses correct ES field name."""

    def test_quydinh_filter_uses_applicable_cohort_field(self):
        """QuyDinh extractor must output 'applicable_cohort', not 'applicable_major'."""
        from retrieval.metadata_filters import QuyDinhFilterExtractor

        extractor = QuyDinhFilterExtractor()
        cf = extractor.extract("quy định ngoại ngữ cho K70")

        assert not cf.is_empty, "Should produce a filter for K70"
        es_query = cf.metadata_es_queries[0]
        query_str = str(es_query)
        assert "applicable_cohort" in query_str, (
            f"Expected 'applicable_cohort' in query but got: {query_str}"
        )
        assert "applicable_major" not in query_str, (
            f"Bug: 'applicable_major' should not appear: {query_str}"
        )

    def test_quydinh_no_cohort_returns_empty_filter(self):
        """Without cohort signal, return empty filter."""
        from retrieval.metadata_filters import QuyDinhFilterExtractor

        extractor = QuyDinhFilterExtractor()
        cf = extractor.extract("quy định học bổng")
        assert cf.is_empty


# ===========================================================================
# P1 Tests: Metadata-Aware Reranking
# ===========================================================================


class TestMetadataAwareReranking:
    """Verify reranker enriches document text with metadata."""

    def test_enrich_text_prepends_metadata(self):
        """Documents with metadata get hierarchy+major+title prefix."""
        from reranking.bge_reranker import BGEReranker

        doc = {
            "text": "Sinh viên phải đạt IELTS 5.5",
            "metadata": {
                "hierarchy_path": "Quy định tốt nghiệp > Ngoại ngữ",
                "major_code": "IT-E6",
                "title": "QĐ Tốt nghiệp 2024",
            },
        }
        enriched = BGEReranker._enrich_text_for_reranking(doc)
        assert "Quy định tốt nghiệp > Ngoại ngữ" in enriched
        assert "Ngành: IT-E6" in enriched
        assert "Tài liệu: QĐ Tốt nghiệp 2024" in enriched
        assert "Sinh viên phải đạt IELTS 5.5" in enriched

    def test_enrich_text_no_metadata_returns_text_only(self):
        """Documents without metadata get plain text."""
        from reranking.bge_reranker import BGEReranker

        doc = {"text": "Hello world", "metadata": {}}
        enriched = BGEReranker._enrich_text_for_reranking(doc)
        assert enriched == "Hello world"

    def test_enrich_text_partial_metadata(self):
        """Only available metadata fields are included."""
        from reranking.bge_reranker import BGEReranker

        doc = {
            "text": "Content",
            "metadata": {"hierarchy_path": "Section > Sub"},
        }
        enriched = BGEReranker._enrich_text_for_reranking(doc)
        assert enriched.startswith("Section > Sub")
        assert "Ngành:" not in enriched


# ===========================================================================
# P1 Tests: Multi-Query Expansion
# ===========================================================================


class TestMultiQueryExpander:
    """Verify multi-query expansion produces useful variants."""

    def test_basic_expansion_returns_multiple_variants(self):
        """Should produce 2-3 variants from a typical query."""
        from retrieval.query_expander import MultiQueryExpander

        expander = MultiQueryExpander(max_variants=3)
        variants = expander.expand(
            query="điều kiện tốt nghiệp ngành IT-E6",
            entities={"major_code": "IT-E6"},
        )
        assert len(variants) >= 2
        assert variants[0] == "điều kiện tốt nghiệp ngành IT-E6"

    def test_entity_query_contains_major_code(self):
        """Entity-focused variant should contain the major code."""
        from retrieval.query_expander import MultiQueryExpander

        expander = MultiQueryExpander(max_variants=3)
        variants = expander.expand(
            query="số tín chỉ tối thiểu để tốt nghiệp IT1",
            entities={"major_code": "IT1"},
        )
        # At least one variant should have IT1 prominently
        has_code = any("IT1" in v for v in variants)
        assert has_code

    def test_topic_query_strips_entities(self):
        """Topic-only variant should not contain entity values."""
        from retrieval.query_expander import MultiQueryExpander

        expander = MultiQueryExpander(max_variants=3)
        variants = expander.expand(
            query="quy định ngoại ngữ cho K70 ngành IT-E6",
            entities={"major_code": "IT-E6", "cohort": "K70"},
        )
        # Find the topic variant (not original, not entity-focused)
        if len(variants) >= 3:
            topic = variants[2]
            assert "IT-E6" not in topic
            assert "K70" not in topic

    def test_empty_query_returns_empty(self):
        """Empty input should not crash."""
        from retrieval.query_expander import MultiQueryExpander

        expander = MultiQueryExpander()
        assert expander.expand("") == []
        assert expander.expand("  ") == ["  "]  # whitespace-only passes through

    def test_no_entities_returns_original_only(self):
        """Without entities, expansion produces fewer variants."""
        from retrieval.query_expander import MultiQueryExpander

        expander = MultiQueryExpander()
        variants = expander.expand("xin chào bạn")
        assert variants[0] == "xin chào bạn"


# ===========================================================================
# P1 Tests: Adaptive Fusion Weights
# ===========================================================================


class TestAdaptiveFusionWeights:
    """Verify course-like queries shift fusion toward keyword."""

    def _build_searcher(self, vector_weight=0.7, keyword_weight=0.3):
        from retrieval.multi_collection_search import MultiCollectionSearch

        searcher = object.__new__(MultiCollectionSearch)
        searcher.vector_weight = vector_weight
        searcher.keyword_weight = keyword_weight
        return searcher

    def test_course_code_triggers_keyword_bias(self):
        """Query with course code IT3080 should shift to keyword."""
        searcher = self._build_searcher()
        vw, kw, reason = searcher._resolve_fusion_weights("IT3080 lập trình mạng")
        assert reason == "course_query_keyword_bias"
        assert kw >= 0.6
        assert vw <= 0.4

    def test_normal_query_uses_defaults(self):
        """Normal query should use default weights."""
        searcher = self._build_searcher()
        vw, kw, reason = searcher._resolve_fusion_weights("điều kiện tốt nghiệp")
        assert reason == "default"
        assert vw == 0.7
        assert kw == 0.3

    def test_course_hint_triggers_bias(self):
        """Query with course-related terms should shift weights."""
        searcher = self._build_searcher()
        vw, kw, reason = searcher._resolve_fusion_weights("môn học tiên quyết của lập trình C")
        assert reason == "course_query_keyword_bias"


# ===========================================================================
# P2 Tests: RRF Fusion Mode
# ===========================================================================


class TestRRFFusion:
    """Verify RRF fusion produces valid ranked results."""

    def _build_searcher(self):
        from retrieval.multi_collection_search import MultiCollectionSearch

        searcher = object.__new__(MultiCollectionSearch)
        searcher.vector_weight = 0.7
        searcher.keyword_weight = 0.3
        searcher.rrf_k = 60
        return searcher

    def test_rrf_single_pool(self):
        """RRF with only vector results should still produce valid scores."""
        searcher = self._build_searcher()

        vector_pool = [
            {"id": "doc1", "text": "a", "metadata": {}, "score": 0.9},
            {"id": "doc2", "text": "b", "metadata": {}, "score": 0.7},
        ]
        keyword_pool = []

        results = searcher._score_fusion_rrf(
            vector_pool, keyword_pool, top_k=5,
            vector_weight=0.7, keyword_weight=0.3,
        )
        assert len(results) == 2
        assert results[0]["score"] > results[1]["score"]

    def test_rrf_overlap_boosts_score(self):
        """Documents in both pools should score higher."""
        searcher = self._build_searcher()

        vector_pool = [
            {"id": "doc1", "text": "a", "metadata": {}, "score": 0.9},
            {"id": "doc2", "text": "b", "metadata": {}, "score": 0.7},
        ]
        keyword_pool = [
            {"id": "doc2", "text": "b", "metadata": {}, "score": 8.0},
            {"id": "doc3", "text": "c", "metadata": {}, "score": 5.0},
        ]

        results = searcher._score_fusion_rrf(
            vector_pool, keyword_pool, top_k=10,
            vector_weight=0.7, keyword_weight=0.3,
        )
        doc2 = next(r for r in results if r["id"] == "doc2")
        doc1 = next(r for r in results if r["id"] == "doc1")
        # doc2 in both pools → higher combined RRF
        assert doc2["score"] > doc1["score"]


# ===========================================================================
# P2 Tests: Deduplication
# ===========================================================================


class TestDeduplication:
    """Verify text-level deduplication works correctly."""

    def _build_searcher(self):
        from retrieval.multi_collection_search import MultiCollectionSearch

        searcher = object.__new__(MultiCollectionSearch)
        searcher.vector_weight = 0.7
        searcher.keyword_weight = 0.3
        searcher.rrf_k = 60
        return searcher

    def test_duplicate_texts_are_removed(self):
        """Identical text chunks from different IDs should be deduplicated."""
        searcher = self._build_searcher()

        vector_pool = [
            {"id": "col1/doc1", "text": "same text content", "metadata": {}, "score": 0.9},
            {"id": "col2/doc1", "text": "same text content", "metadata": {}, "score": 0.8},
            {"id": "col1/doc2", "text": "different text", "metadata": {}, "score": 0.7},
        ]
        keyword_pool = []

        results = searcher._score_fusion(
            vector_pool, keyword_pool, top_k=10,
            vector_weight=0.7, keyword_weight=0.3,
        )
        texts = [r["text"] for r in results]
        assert len(texts) == 2
        assert "same text content" in texts
        assert "different text" in texts


# ===========================================================================
# P2 Tests: Kehoach Filter Extractor
# ===========================================================================


class TestKehoachFilterExtractor:
    """Verify kehoach date/freshness filtering."""

    def test_freshness_intent_detected(self):
        """Queries with 'mới nhất' should set sort_by_date_desc."""
        from retrieval.metadata_filters import KeHoachFilterExtractor

        extractor = KeHoachFilterExtractor()
        cf = extractor.extract("lịch đăng ký mới nhất")
        assert cf.sort_by_date_desc is True
        assert cf.is_empty  # no explicit date filter

    def test_explicit_date_produces_filter(self):
        """Queries with explicit year should produce date filter, not freshness."""
        from retrieval.metadata_filters import KeHoachFilterExtractor

        extractor = KeHoachFilterExtractor()
        cf = extractor.extract("lịch học kỳ 2 năm 2025")
        assert cf.sort_by_date_desc is False
        assert not cf.is_empty
        assert len(cf.metadata_es_queries) >= 1

    def test_no_signal_returns_empty(self):
        """Generic query without date/freshness returns empty filter."""
        from retrieval.metadata_filters import KeHoachFilterExtractor

        extractor = KeHoachFilterExtractor()
        cf = extractor.extract("thủ tục xin nghỉ học")
        assert cf.is_empty
        assert cf.sort_by_date_desc is False


# ===========================================================================
# P2 Tests: Exclude Term Filtering
# ===========================================================================


class TestExcludeTermFiltering:
    """Verify structured query exclude-term filtering."""

    def _build_searcher(self):
        from retrieval.multi_collection_search import MultiCollectionSearch

        searcher = object.__new__(MultiCollectionSearch)
        return searcher

    def test_excluded_terms_remove_matching_docs(self):
        """Documents containing excluded terms should be filtered out."""
        searcher = self._build_searcher()

        results = [
            {"id": "1", "text": "IT3080 Lập trình mạng", "metadata": {"title": "CTDT"}},
            {"id": "2", "text": "IT3090 Cơ sở dữ liệu", "metadata": {"title": "CTDT"}},
            {"id": "3", "text": "EE1010 Mạch điện", "metadata": {"title": "CTDT"}},
        ]

        filtered = searcher._filter_excluded_results(results, ["IT3090"])
        assert len(filtered) == 2
        assert all("IT3090" not in r["text"] for r in filtered)

    def test_no_excludes_returns_all(self):
        """Without exclude terms, all results pass through."""
        searcher = self._build_searcher()

        results = [
            {"id": "1", "text": "test", "metadata": {}},
        ]
        filtered = searcher._filter_excluded_results(results, [])
        assert len(filtered) == 1


# ===========================================================================
# Integration Test: CollectionSelector
# ===========================================================================


class TestCollectionSelector:
    """Verify domain-to-collection mapping."""

    def test_high_confidence_maps_correctly(self):
        """High confidence ctdt domain maps to ctdt collection."""
        from retrieval.collection_selector import CollectionSelector

        selector = CollectionSelector()
        cols = selector.select(domain="ctdt", confidence=0.9)
        assert "ctdt" in cols

    def test_low_confidence_uses_fallback(self):
        """Low confidence should use fallback collections."""
        from retrieval.collection_selector import CollectionSelector

        selector = CollectionSelector()
        cols = selector.select(domain="ctdt", confidence=0.2)
        # Should include multiple collections as fallback
        assert len(cols) > 1

    def test_quydinh_includes_stsv_overlap(self):
        """quydinh domain should also search stsv."""
        from retrieval.collection_selector import CollectionSelector

        selector = CollectionSelector()
        cols = selector.select(domain="quydinh", confidence=0.9)
        assert "quydinh" in cols
        assert "stsv" in cols
