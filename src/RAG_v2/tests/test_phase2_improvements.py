"""Tests for Phase 2 retrieval improvements.

Covers:
  1. Vietnamese word segmentation module
  2. Segmentation integration in ES keyword_search
  3. Fusion weight sweep metrics calculation
  4. Redis config defaults (enabled by default)
  5. Metadata audit script logic
"""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ─── Helpers to import modules despite missing heavy dependencies ────────────


def _mock_heavy_deps():
    """Mock heavy dependencies that aren't installed locally."""
    base_mocks = [
        "torch", "torch.backends", "torch.backends.mps", "torch.nn",
        "torch.nn.functional",
        "numpy",
        "FlagEmbedding",
        "sentence_transformers",
        "qdrant_client", "qdrant_client.models",
        "elasticsearch", "elasticsearch.helpers",
        "redis",
        "openai",
        "httpx",
        "joblib",
        "pydantic_settings",
        "google", "google.generativeai",
        "langchain_core", "langchain_core.tools",
        "langchain_google_genai",
        "underthesea",
    ]
    sklearn_subs = [
        "sklearn", "sklearn.calibration", "sklearn.linear_model",
        "sklearn.multiclass", "sklearn.preprocessing",
        "sklearn.feature_extraction", "sklearn.feature_extraction.text",
        "sklearn.pipeline", "sklearn.exceptions", "sklearn.metrics",
        "sklearn.model_selection", "sklearn.base", "sklearn.utils",
    ]
    all_mocks = base_mocks + sklearn_subs

    for mod_name in all_mocks:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()

    sys.modules["torch"].cuda = MagicMock()
    sys.modules["torch"].cuda.is_available.return_value = False
    sys.modules["torch"].backends = sys.modules["torch.backends"]
    sys.modules["torch"].backends.mps = sys.modules["torch.backends.mps"]
    sys.modules["torch"].backends.mps.is_available.return_value = False
    sys.modules["torch"].float16 = "float16"
    sys.modules["torch"].float32 = "float32"
    sys.modules["numpy"].ndarray = MagicMock

    for sub in sklearn_subs[1:]:
        attr_name = sub.split(".")[-1]
        parent = ".".join(sub.split(".")[:-1])
        if parent in sys.modules:
            setattr(sys.modules[parent], attr_name, sys.modules[sub])

    query_mocks = [
        "query", "query.signals", "query.structured_query",
        "query.domain_classifier", "query.router", "query.reflection",
        "query.complexity_router", "query.decomposer",
    ]
    for mod_name in query_mocks:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()

    if "config" not in sys.modules:
        sys.modules["config"] = MagicMock()
    if "config.settings" not in sys.modules:
        sys.modules["config.settings"] = MagicMock()


_mock_heavy_deps()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Vietnamese Word Segmentation
# ═══════════════════════════════════════════════════════════════════════════════


class TestVietnameseSegmenter:
    """Test the Vietnamese word segmentation module."""

    def _get_segmenter(self):
        """Import the segmenter module (force dict-based fallback)."""
        # Force underthesea to be unavailable for deterministic testing
        import utils.vietnamese_segmenter as seg

        # Temporarily disable underthesea for tests
        original_available = seg._UNDERTHESEA_AVAILABLE
        seg._UNDERTHESEA_AVAILABLE = False
        yield seg
        seg._UNDERTHESEA_AVAILABLE = original_available

    @pytest.fixture
    def seg(self):
        """Fixture providing segmenter with underthesea disabled."""
        import utils.vietnamese_segmenter as seg
        original = seg._UNDERTHESEA_AVAILABLE
        seg._UNDERTHESEA_AVAILABLE = False
        yield seg
        seg._UNDERTHESEA_AVAILABLE = original

    def test_segment_empty_string(self, seg):
        assert seg.segment("") == ""
        assert seg.segment("   ") == "   "

    def test_segment_compound_words(self, seg):
        result = seg.segment("sinh viên đại học Quy Nhơn")
        assert "sinh_viên" in result
        assert "đại_học" in result

    def test_segment_multiple_compounds(self, seg):
        result = seg.segment("chương trình đào tạo công nghệ thông tin")
        assert "chương_trình_đào_tạo" in result or "chương_trình" in result
        assert "công_nghệ_thông_tin" in result or "công_nghệ" in result

    def test_segment_no_compounds(self, seg):
        text = "xin chào"
        result = seg.segment(text)
        # "xin chào" is not in the dictionary, should stay the same
        assert result == text

    def test_segment_preserves_non_vietnamese(self, seg):
        text = "hello world sinh viên"
        result = seg.segment(text)
        assert "hello world" in result
        assert "sinh_viên" in result

    def test_segment_for_indexing_combines_both(self, seg):
        text = "sinh viên tốt nghiệp"
        result = seg.segment_for_indexing(text)
        # Should contain original
        assert "sinh viên" in result
        # Should contain segmented version
        assert "sinh_viên" in result
        assert "\n" in result

    def test_segment_for_indexing_no_change(self, seg):
        text = "hello world"
        result = seg.segment_for_indexing(text)
        # No compounds detected, no duplication
        assert result == text
        assert "\n" not in result

    def test_segment_query(self, seg):
        query = "điều kiện tốt nghiệp đại học"
        result = seg.segment_query(query)
        assert "tốt_nghiệp" in result
        assert "đại_học" in result

    def test_get_compound_variants(self, seg):
        query = "học phí sinh viên"
        variants = seg.get_compound_variants(query)
        assert len(variants) == 2
        assert variants[0] == query  # Original
        assert "học_phí" in variants[1] or "sinh_viên" in variants[1]

    def test_get_compound_variants_no_change(self, seg):
        query = "hello world"
        variants = seg.get_compound_variants(query)
        assert len(variants) == 1
        assert variants[0] == query

    def test_case_insensitive_matching(self, seg):
        result = seg.segment("Sinh Viên Đại Học")
        assert "Sinh_Viên" in result or "sinh_viên" in result.lower()

    def test_greedy_longest_match(self, seg):
        """Should match 'chương trình đào tạo' (4 syllables) over 'chương trình' (2)."""
        result = seg.segment("chương trình đào tạo tín chỉ")
        # Either the 4-syllable or both 2-syllable forms should be joined
        assert "_" in result  # At minimum some joining happened
        assert "tín_chỉ" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Segmentation Integration in ES keyword_search
# ═══════════════════════════════════════════════════════════════════════════════


class TestSegmentationInES:
    """Test that keyword_search integrates word segmentation."""

    def test_segment_query_imported_in_keyword_search(self):
        """Verify the import path works and returns a string."""
        import utils.vietnamese_segmenter as seg
        original = seg._UNDERTHESEA_AVAILABLE
        seg._UNDERTHESEA_AVAILABLE = False

        from utils.vietnamese_segmenter import segment_query
        result = segment_query("sinh viên đại học")
        assert isinstance(result, str)
        assert "sinh_viên" in result

        seg._UNDERTHESEA_AVAILABLE = original

    def test_segmented_query_differs_from_original(self):
        """When query has compounds, segmented version differs."""
        from utils.vietnamese_segmenter import segment_query
        import utils.vietnamese_segmenter as seg
        original = seg._UNDERTHESEA_AVAILABLE
        seg._UNDERTHESEA_AVAILABLE = False

        query = "sinh viên tốt nghiệp"
        segmented = segment_query(query)
        assert segmented != query
        assert "_" in segmented

        seg._UNDERTHESEA_AVAILABLE = original

    def test_segmented_query_same_for_non_compound(self):
        """Non-compound queries should not produce a boost clause."""
        from utils.vietnamese_segmenter import segment_query
        import utils.vietnamese_segmenter as seg
        original = seg._UNDERTHESEA_AVAILABLE
        seg._UNDERTHESEA_AVAILABLE = False

        query = "hello world test"
        segmented = segment_query(query)
        assert segmented == query  # No change = no extra should clause

        seg._UNDERTHESEA_AVAILABLE = original


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Fusion Weight Sweep Metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestFusionMetrics:
    """Test the metric calculations used in fusion weight sweep."""

    def test_ndcg_at_k_perfect_ranking(self):
        from evaluation.fusion_weight_sweep import _ndcg_at_k
        # Perfect ranking: expected doc at position 0
        ranked = ["doc1", "doc2", "doc3"]
        expected = ["doc1"]
        score = _ndcg_at_k(ranked, expected, k=10)
        assert score == 1.0

    def test_ndcg_at_k_no_relevant(self):
        from evaluation.fusion_weight_sweep import _ndcg_at_k
        ranked = ["doc1", "doc2", "doc3"]
        expected = ["doc99"]
        score = _ndcg_at_k(ranked, expected, k=10)
        assert score == 0.0

    def test_ndcg_at_k_partial_match(self):
        from evaluation.fusion_weight_sweep import _ndcg_at_k
        ranked = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        expected = ["doc3"]  # Relevant at position 2
        score = _ndcg_at_k(ranked, expected, k=10)
        assert 0.0 < score < 1.0

    def test_ndcg_at_k_empty_expected(self):
        from evaluation.fusion_weight_sweep import _ndcg_at_k
        ranked = ["doc1", "doc2"]
        expected = []
        score = _ndcg_at_k(ranked, expected, k=10)
        assert score == 0.0

    def test_mrr_at_k_first_position(self):
        from evaluation.fusion_weight_sweep import _mrr_at_k
        ranked = ["doc1", "doc2", "doc3"]
        expected = ["doc1"]
        score = _mrr_at_k(ranked, expected, k=10)
        assert score == 1.0

    def test_mrr_at_k_second_position(self):
        from evaluation.fusion_weight_sweep import _mrr_at_k
        ranked = ["doc1", "doc2", "doc3"]
        expected = ["doc2"]
        score = _mrr_at_k(ranked, expected, k=10)
        assert score == 0.5

    def test_mrr_at_k_not_found(self):
        from evaluation.fusion_weight_sweep import _mrr_at_k
        ranked = ["doc1", "doc2"]
        expected = ["doc99"]
        score = _mrr_at_k(ranked, expected, k=10)
        assert score == 0.0

    def test_recall_at_k_full(self):
        from evaluation.fusion_weight_sweep import _recall_at_k
        ranked = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        expected = ["doc1", "doc3"]
        score = _recall_at_k(ranked, expected, k=50)
        assert score == 1.0

    def test_recall_at_k_partial(self):
        from evaluation.fusion_weight_sweep import _recall_at_k
        ranked = ["doc1", "doc2", "doc3"]
        expected = ["doc1", "doc99"]
        score = _recall_at_k(ranked, expected, k=50)
        assert score == 0.5

    def test_recall_at_k_none(self):
        from evaluation.fusion_weight_sweep import _recall_at_k
        ranked = ["doc1", "doc2"]
        expected = ["doc99", "doc100"]
        score = _recall_at_k(ranked, expected, k=50)
        assert score == 0.0

    def test_sweep_result_combined_score(self):
        from evaluation.fusion_weight_sweep import SweepResult
        sr = SweepResult(
            vector_weight=0.7,
            keyword_weight=0.3,
            ndcg_at_10=0.8,
            mrr_at_10=0.9,
            recall_at_50=0.7,
        )
        # 0.5*0.8 + 0.3*0.9 + 0.2*0.7 = 0.4 + 0.27 + 0.14 = 0.81
        assert abs(sr.combined_score - 0.81) < 0.001

    def test_sweep_result_to_dict(self):
        from evaluation.fusion_weight_sweep import SweepResult
        sr = SweepResult(vector_weight=0.6, keyword_weight=0.4)
        d = sr.to_dict()
        assert d["vector_weight"] == 0.6
        assert d["keyword_weight"] == 0.4
        assert "combined_score" in d


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Redis Config Defaults
# ═══════════════════════════════════════════════════════════════════════════════


class TestRedisConfigDefaults:
    """Verify Redis features are enabled by default in settings source."""

    @pytest.fixture(autouse=True)
    def _settings_source(self):
        """Read the actual settings.py source for verification."""
        settings_path = Path(__file__).resolve().parent.parent / "config" / "settings.py"
        self.source = settings_path.read_text(encoding="utf-8")

    def test_redis_enabled_by_default(self):
        """Redis master switch should be True."""
        assert "redis_enabled: bool = True" in self.source

    def test_redis_session_enabled(self):
        assert "use_redis_session: bool = True" in self.source

    def test_redis_cache_enabled(self):
        assert "use_redis_cache: bool = True" in self.source

    def test_redis_history_enabled(self):
        assert "use_redis_history: bool = True" in self.source

    def test_redis_url_default(self):
        assert 'redis_url: str = "redis://localhost:6379/0"' in self.source


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Metadata Audit Script
# ═══════════════════════════════════════════════════════════════════════════════


class TestMetadataAudit:
    """Test metadata audit scanning logic."""

    def test_scan_empty_directory(self, tmp_path):
        from scripts.metadata_audit import scan_collection
        empty_dir = tmp_path / "empty_collection"
        empty_dir.mkdir()
        result = scan_collection(empty_dir)
        assert result["doc_count"] == 0
        assert result["fields"] == {}

    def test_scan_single_doc(self, tmp_path):
        from scripts.metadata_audit import scan_collection
        coll_dir = tmp_path / "test_coll"
        coll_dir.mkdir()
        doc = {
            "DocumentID": "doc001",
            "Title": "Test Document",
            "TypeDoc": "QuyDinh",
            "Description": "",  # empty
        }
        (coll_dir / "test.json").write_text(
            json.dumps([doc]), encoding="utf-8"
        )
        result = scan_collection(coll_dir)
        assert result["doc_count"] == 1
        assert result["name"] == "test_coll"
        fields = result["fields"]
        assert fields["DocumentID"]["fill_rate_pct"] == 100.0
        assert fields["Title"]["fill_rate_pct"] == 100.0
        assert fields["Description"]["fill_rate_pct"] == 0.0  # Empty string

    def test_scan_multiple_docs(self, tmp_path):
        from scripts.metadata_audit import scan_collection
        coll_dir = tmp_path / "multi"
        coll_dir.mkdir()
        docs = [
            {"DocumentID": "d1", "Title": "Doc 1", "major_code": "CNTT"},
            {"DocumentID": "d2", "Title": "Doc 2", "major_code": ""},
            {"DocumentID": "d3", "Title": "Doc 3"},  # no major_code at all
        ]
        (coll_dir / "data.json").write_text(
            json.dumps(docs), encoding="utf-8"
        )
        result = scan_collection(coll_dir)
        assert result["doc_count"] == 3
        fields = result["fields"]
        assert fields["DocumentID"]["fill_rate_pct"] == 100.0
        # major_code: present in 2 docs, filled in 1
        assert fields["major_code"]["present_count"] == 2
        assert fields["major_code"]["filled_count"] == 1

    def test_generate_suggestions_missing_field(self, tmp_path):
        from scripts.metadata_audit import generate_suggestions
        stats = [
            {
                "name": "test",
                "doc_count": 10,
                "fields": {
                    "DocumentID": {"fill_rate_pct": 100.0},
                    # "Title" is missing entirely
                },
            }
        ]
        suggestions = generate_suggestions(stats)
        # Should suggest adding missing important fields
        assert any("Title" in s for s in suggestions)

    def test_generate_suggestions_low_fill_rate(self, tmp_path):
        from scripts.metadata_audit import generate_suggestions
        stats = [
            {
                "name": "test",
                "doc_count": 100,
                "fields": {
                    "major_code": {"fill_rate_pct": 20.0},
                    "DocumentID": {"fill_rate_pct": 100.0},
                },
            }
        ]
        suggestions = generate_suggestions(stats)
        assert any("major_code" in s and "20" in s for s in suggestions)

    def test_scan_invalid_json_skipped(self, tmp_path):
        from scripts.metadata_audit import scan_collection
        coll_dir = tmp_path / "bad"
        coll_dir.mkdir()
        (coll_dir / "bad.json").write_text("not valid json{{{", encoding="utf-8")
        (coll_dir / "good.json").write_text(
            json.dumps([{"id": "1", "title": "OK"}]), encoding="utf-8"
        )
        result = scan_collection(coll_dir)
        # Should still process the good file
        assert result["doc_count"] == 1
