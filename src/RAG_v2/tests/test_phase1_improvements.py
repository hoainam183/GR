"""Tests for Phase 1 retrieval improvements.

Covers:
  1. HyDE prompt fix (HUST → Quy Nhơn)
  2. Embedding LRU cache (BGE-M3 and E5)
  3. Search result TTL cache in RetrievalService
  4. ES synonym filter and BM25 tuning in index settings
"""

from __future__ import annotations

import hashlib
import importlib
import sys
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


# ─── Helpers to import modules despite missing heavy dependencies ────────────


def _mock_heavy_deps():
    """Mock heavy dependencies that aren't installed locally (torch, qdrant_client, etc.).

    This environment lacks torch, qdrant_client, sklearn, openai etc.
    We mock entire package trees so import chains don't fail.
    """
    # Generate exhaustive list including all known transitive deps
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
    ]
    # sklearn subtree
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

    # Wire up subpackage attributes
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

    # Mock the query package to avoid deep import chains
    # We only need it to not crash — actual query logic isn't under test.
    query_mocks = [
        "query", "query.signals", "query.structured_query",
        "query.domain_classifier", "query.router", "query.reflection",
        "query.complexity_router", "query.decomposer",
    ]
    for mod_name in query_mocks:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()

    # config.settings needs to provide a Settings mock
    if "config" not in sys.modules:
        sys.modules["config"] = MagicMock()
    if "config.settings" not in sys.modules:
        sys.modules["config.settings"] = MagicMock()


_mock_heavy_deps()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. HyDE Prompt Fix
# ═══════════════════════════════════════════════════════════════════════════════


class TestHyDEPromptFix:
    """Verify HyDE uses Đại học Quy Nhơn, not HUST."""

    def test_prompt_contains_quy_nhon(self):
        from retrieval.hyde import _HYPOTHESIS_PROMPT_VI

        assert "Quy Nhơn" in _HYPOTHESIS_PROMPT_VI
        assert "QNU" in _HYPOTHESIS_PROMPT_VI

    def test_prompt_does_not_contain_hust(self):
        from retrieval.hyde import _HYPOTHESIS_PROMPT_VI

        assert "HUST" not in _HYPOTHESIS_PROMPT_VI
        assert "Bách khoa Hà Nội" not in _HYPOTHESIS_PROMPT_VI

    def test_hyde_expander_generates_correct_prompt(self):
        from retrieval.hyde import HyDEExpander

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Hypothetical answer"
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 1024

        hyde = HyDEExpander(llm=mock_llm, embedder=mock_embedder)
        hyde.generate_hypothesis("Điều kiện tốt nghiệp?")

        called_prompt = mock_llm.generate.call_args[0][0]
        assert "Quy Nhơn" in called_prompt
        assert "Điều kiện tốt nghiệp?" in called_prompt


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Embedding LRU Cache
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmbeddingCacheBGE:
    """Test BGE-M3 embedder LRU cache."""

    def test_cache_basic_operations(self):
        from embedding.bge_m3 import _EmbeddingCache

        cache = _EmbeddingCache(maxsize=3)

        # Miss
        assert cache.get("hello") is None
        assert cache.stats["misses"] == 1

        # Put and hit
        cache.put("hello", [0.1, 0.2, 0.3])
        result = cache.get("hello")
        assert result == [0.1, 0.2, 0.3]
        assert cache.stats["hits"] == 1

    def test_cache_eviction(self):
        from embedding.bge_m3 import _EmbeddingCache

        cache = _EmbeddingCache(maxsize=2)
        cache.put("a", [1.0])
        cache.put("b", [2.0])
        cache.put("c", [3.0])  # evicts "a"

        assert cache.get("a") is None  # evicted
        assert cache.get("b") == [2.0]
        assert cache.get("c") == [3.0]

    def test_cache_lru_ordering(self):
        from embedding.bge_m3 import _EmbeddingCache

        cache = _EmbeddingCache(maxsize=2)
        cache.put("a", [1.0])
        cache.put("b", [2.0])
        cache.get("a")  # access "a" to make it recently used
        cache.put("c", [3.0])  # should evict "b" (least recently used)

        assert cache.get("a") == [1.0]
        assert cache.get("b") is None  # evicted
        assert cache.get("c") == [3.0]

    def test_bge_embed_query_uses_cache(self):
        """Verify embed_query returns cached result on second call."""
        from embedding.bge_m3 import BGEm3Embedder, _EmbeddingCache

        embedder = BGEm3Embedder.__new__(BGEm3Embedder)
        embedder._query_cache = _EmbeddingCache(maxsize=10)

        # Mock the internal encoding
        fake_vec = [0.5] * 1024
        with patch.object(embedder, "_encode_dense", return_value=[fake_vec]) as mock_encode:
            # First call: cache miss → encode
            result1 = embedder.embed_query("test query")
            assert result1 == fake_vec
            assert mock_encode.call_count == 1

            # Second call: cache hit → no encode
            result2 = embedder.embed_query("test query")
            assert result2 == fake_vec
            assert mock_encode.call_count == 1  # no additional call

        assert embedder._query_cache.stats["hits"] == 1
        assert embedder._query_cache.stats["misses"] == 1


class TestEmbeddingCacheE5:
    """Test E5 embedder LRU cache."""

    def test_e5_embed_query_uses_cache(self):
        """Verify E5 embed_query returns cached result on second call."""
        from embedding.e5_multilingual import E5MultilingualEmbedder, _EmbeddingCache

        embedder = E5MultilingualEmbedder.__new__(E5MultilingualEmbedder)
        embedder._query_cache = _EmbeddingCache(maxsize=10)
        embedder.QUERY_PREFIX = "query: "

        fake_vec = [0.3] * 1024
        with patch.object(embedder, "_encode", return_value=[fake_vec]) as mock_encode:
            # First call
            result1 = embedder.embed_query("test query")
            assert result1 == fake_vec
            assert mock_encode.call_count == 1

            # Second call — cached
            result2 = embedder.embed_query("test query")
            assert result2 == fake_vec
            assert mock_encode.call_count == 1

        assert embedder._query_cache.stats["hits"] == 1

    def test_e5_different_queries_not_cached(self):
        """Different queries should not return cached results."""
        from embedding.e5_multilingual import E5MultilingualEmbedder, _EmbeddingCache

        embedder = E5MultilingualEmbedder.__new__(E5MultilingualEmbedder)
        embedder._query_cache = _EmbeddingCache(maxsize=10)
        embedder.QUERY_PREFIX = "query: "

        vec1 = [0.1] * 1024
        vec2 = [0.9] * 1024
        call_count = [0]

        def mock_encode(texts):
            call_count[0] += 1
            if "query1" in texts[0]:
                return [vec1]
            return [vec2]

        with patch.object(embedder, "_encode", side_effect=mock_encode):
            r1 = embedder.embed_query("query1")
            r2 = embedder.embed_query("query2")
            assert r1 == vec1
            assert r2 == vec2
            assert call_count[0] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Search Result Cache (TTL)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchResultCache:
    """Test the _SearchResultCache in retrieval/service.py."""

    def test_cache_miss_then_hit(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=60.0)

        results = [{"id": "1", "text": "doc1", "score": 0.9}]
        assert cache.get("query", ["stsv"]) is None
        cache.put("query", ["stsv"], results)
        cached = cache.get("query", ["stsv"])
        assert cached == results

    def test_cache_ttl_expiry(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=0.1)  # 100ms TTL

        results = [{"id": "1", "text": "doc1"}]
        cache.put("query", ["stsv"], results)

        # Should be present immediately
        assert cache.get("query", ["stsv"]) is not None

        # Wait for TTL expiry
        time.sleep(0.15)
        assert cache.get("query", ["stsv"]) is None

    def test_cache_different_collections_different_keys(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=60.0)

        results_stsv = [{"id": "1", "text": "stsv doc"}]
        results_ctdt = [{"id": "2", "text": "ctdt doc"}]

        cache.put("query", ["stsv"], results_stsv)
        cache.put("query", ["ctdt"], results_ctdt)

        assert cache.get("query", ["stsv"]) == results_stsv
        assert cache.get("query", ["ctdt"]) == results_ctdt

    def test_cache_with_metadata_filters(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=60.0)

        results = [{"id": "1", "text": "doc"}]
        cache.put("query", ["ctdt"], results, resolved_major="IT-E6")

        # Same query without major → miss
        assert cache.get("query", ["ctdt"]) is None
        # With major → hit
        assert cache.get("query", ["ctdt"], resolved_major="IT-E6") == results

    def test_cache_maxsize_eviction(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=2, ttl_seconds=60.0)

        cache.put("q1", ["stsv"], [{"id": "1"}])
        cache.put("q2", ["stsv"], [{"id": "2"}])
        cache.put("q3", ["stsv"], [{"id": "3"}])  # evicts q1

        assert cache.get("q1", ["stsv"]) is None
        assert cache.get("q2", ["stsv"]) is not None
        assert cache.get("q3", ["stsv"]) is not None

    def test_cache_stats(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=60.0)

        cache.put("q", ["s"], [{"id": "1"}])
        cache.get("q", ["s"])  # hit
        cache.get("miss", ["s"])  # miss

        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 1
        assert cache.stats["size"] == 1

    def test_service_uses_cache(self):
        """Integration: RetrievalService._search_single uses cache."""
        from retrieval.service import RetrievalService

        # Build a minimal service with mocks
        mock_settings = MagicMock()
        mock_settings.top_k = 5
        mock_settings.vector_top_k = 20
        mock_settings.keyword_top_k = 20
        mock_settings.vector_pool_k = 15
        mock_settings.keyword_pool_k = 15

        mock_searcher = MagicMock()
        mock_searcher.search.return_value = [
            {"id": "1", "text": "result", "score": 0.9}
        ]

        service = RetrievalService(
            settings=mock_settings,
            bge_embedder=MagicMock(),
            e5_embedder=MagicMock(),
            searcher=mock_searcher,
            reranker=None,
        )
        service.bge_embedder.embed_query.return_value = [0.1] * 1024
        service.e5_embedder.embed_query.return_value = [0.2] * 1024

        # First call — cache miss, calls searcher
        r1 = service._search_single(
            "test", effective_top_k=5, raw_candidate_k=20,
            active_collections=["stsv"], resolved_major=None,
            resolved_cohort=None, rerank=False,
        )
        assert mock_searcher.search.call_count == 1

        # Second call — cache hit, searcher NOT called again
        r2 = service._search_single(
            "test", effective_top_k=5, raw_candidate_k=20,
            active_collections=["stsv"], resolved_major=None,
            resolved_cohort=None, rerank=False,
        )
        assert mock_searcher.search.call_count == 1  # still 1
        assert r1 == r2


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Elasticsearch Synonym Filter & BM25 Tuning
# ═══════════════════════════════════════════════════════════════════════════════


class TestElasticsearchSettings:
    """Verify _make_settings includes synonyms, stopwords, and BM25 tuning."""

    def _get_settings(self, use_icu: bool = True) -> Dict[str, Any]:
        from retrieval.elasticsearch_store import ElasticsearchStore

        return ElasticsearchStore._make_settings(use_icu=use_icu)

    def test_synonym_filter_defined_icu(self):
        settings = self._get_settings(use_icu=True)
        filters = settings["settings"]["analysis"]["filter"]
        assert "vietnamese_synonym" in filters
        synonyms = filters["vietnamese_synonym"]["synonyms"]
        # Check key abbreviations are present
        synonym_text = " ".join(synonyms)
        assert "CTDT" in synonym_text
        assert "chương trình đào tạo" in synonym_text
        assert "STSV" in synonym_text
        assert "sổ tay sinh viên" in synonym_text
        assert "CNTT" in synonym_text
        assert "công nghệ thông tin" in synonym_text

    def test_synonym_filter_defined_standard(self):
        settings = self._get_settings(use_icu=False)
        filters = settings["settings"]["analysis"]["filter"]
        assert "vietnamese_synonym" in filters

    def test_stopwords_filter_defined(self):
        settings = self._get_settings(use_icu=True)
        filters = settings["settings"]["analysis"]["filter"]
        assert "vietnamese_stop" in filters
        stopwords = filters["vietnamese_stop"]["stopwords"]
        assert "và" in stopwords
        assert "của" in stopwords
        assert "trong" in stopwords

    def test_analyzer_includes_synonym_and_stop_filters(self):
        settings = self._get_settings(use_icu=True)
        analyzer = settings["settings"]["analysis"]["analyzer"]["vietnamese_analyzer"]
        assert "vietnamese_synonym" in analyzer["filter"]
        assert "vietnamese_stop" in analyzer["filter"]

    def test_analyzer_standard_fallback_includes_filters(self):
        settings = self._get_settings(use_icu=False)
        analyzer = settings["settings"]["analysis"]["analyzer"]["vietnamese_analyzer"]
        assert "vietnamese_synonym" in analyzer["filter"]
        assert "vietnamese_stop" in analyzer["filter"]
        assert "asciifolding" in analyzer["filter"]

    def test_bm25_custom_similarity(self):
        settings = self._get_settings(use_icu=True)
        similarity = settings["settings"]["index"]["similarity"]["custom_bm25"]
        assert similarity["type"] == "BM25"
        assert similarity["k1"] == 1.5
        assert similarity["b"] == 0.5

    def test_text_fields_use_custom_bm25(self):
        settings = self._get_settings(use_icu=True)
        props = settings["mappings"]["properties"]

        # Primary text fields should use custom_bm25
        assert props["text"]["similarity"] == "custom_bm25"
        assert props["title"]["similarity"] == "custom_bm25"
        assert props["section_h2"]["similarity"] == "custom_bm25"
        assert props["section_h3"]["similarity"] == "custom_bm25"
        assert props["course_name"]["similarity"] == "custom_bm25"
        assert props["major_name"]["similarity"] == "custom_bm25"

    def test_keyword_fields_unchanged(self):
        settings = self._get_settings(use_icu=True)
        props = settings["mappings"]["properties"]

        # Keyword fields should not have similarity setting
        assert "similarity" not in props["major_code"]
        assert "similarity" not in props["applicable_cohort"]
        assert "similarity" not in props["document_type"]

    def test_bm25_params_standard_fallback(self):
        settings = self._get_settings(use_icu=False)
        similarity = settings["settings"]["index"]["similarity"]["custom_bm25"]
        assert similarity["k1"] == 1.5
        assert similarity["b"] == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Synonym Coverage — important domain abbreviations
# ═══════════════════════════════════════════════════════════════════════════════


class TestSynonymCoverage:
    """Ensure all critical Vietnamese academic abbreviations are mapped."""

    REQUIRED_ABBREVIATIONS = [
        ("CTDT", "chương trình đào tạo"),
        ("STSV", "sổ tay sinh viên"),
        ("CNTT", "công nghệ thông tin"),
        ("SV", "sinh viên"),
        ("GV", "giảng viên"),
        ("HP", "học phần"),
        ("TC", "tín chỉ"),
        ("HK", "học kỳ"),
        ("KLTN", "khóa luận tốt nghiệp"),
    ]

    def test_all_critical_abbreviations_present(self):
        from retrieval.elasticsearch_store import ElasticsearchStore

        settings = ElasticsearchStore._make_settings(use_icu=True)
        synonyms = settings["settings"]["analysis"]["filter"]["vietnamese_synonym"]["synonyms"]
        synonym_text = "\n".join(synonyms).lower()

        for abbr, full_form in self.REQUIRED_ABBREVIATIONS:
            assert abbr.lower() in synonym_text, (
                f"Missing synonym mapping for {abbr}"
            )
            assert full_form.lower() in synonym_text, (
                f"Missing full form '{full_form}' for {abbr}"
            )



# ═══════════════════════════════════════════════════════════════════════════════
# 2. Embedding LRU Cache
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmbeddingCacheBGE:
    """Test BGE-M3 embedder LRU cache."""

    def test_cache_basic_operations(self):
        from embedding.bge_m3 import _EmbeddingCache

        cache = _EmbeddingCache(maxsize=3)

        # Miss
        assert cache.get("hello") is None
        assert cache.stats["misses"] == 1

        # Put and hit
        cache.put("hello", [0.1, 0.2, 0.3])
        result = cache.get("hello")
        assert result == [0.1, 0.2, 0.3]
        assert cache.stats["hits"] == 1

    def test_cache_eviction(self):
        from embedding.bge_m3 import _EmbeddingCache

        cache = _EmbeddingCache(maxsize=2)
        cache.put("a", [1.0])
        cache.put("b", [2.0])
        cache.put("c", [3.0])  # evicts "a"

        assert cache.get("a") is None  # evicted
        assert cache.get("b") == [2.0]
        assert cache.get("c") == [3.0]

    def test_cache_lru_ordering(self):
        from embedding.bge_m3 import _EmbeddingCache

        cache = _EmbeddingCache(maxsize=2)
        cache.put("a", [1.0])
        cache.put("b", [2.0])
        cache.get("a")  # access "a" to make it recently used
        cache.put("c", [3.0])  # should evict "b" (least recently used)

        assert cache.get("a") == [1.0]
        assert cache.get("b") is None  # evicted
        assert cache.get("c") == [3.0]

    def test_bge_embed_query_uses_cache(self):
        """Verify embed_query returns cached result on second call."""
        from embedding.bge_m3 import BGEm3Embedder

        embedder = BGEm3Embedder.__new__(BGEm3Embedder)
        from embedding.bge_m3 import _EmbeddingCache

        embedder._query_cache = _EmbeddingCache(maxsize=10)

        # Mock the internal encoding
        fake_vec = [0.5] * 1024
        with patch.object(embedder, "_encode_dense", return_value=[fake_vec]) as mock_encode:
            # First call: cache miss → encode
            result1 = embedder.embed_query("test query")
            assert result1 == fake_vec
            assert mock_encode.call_count == 1

            # Second call: cache hit → no encode
            result2 = embedder.embed_query("test query")
            assert result2 == fake_vec
            assert mock_encode.call_count == 1  # no additional call

        assert embedder._query_cache.stats["hits"] == 1
        assert embedder._query_cache.stats["misses"] == 1


class TestEmbeddingCacheE5:
    """Test E5 embedder LRU cache."""

    def test_e5_embed_query_uses_cache(self):
        """Verify E5 embed_query returns cached result on second call."""
        from embedding.e5_multilingual import E5MultilingualEmbedder, _EmbeddingCache

        embedder = E5MultilingualEmbedder.__new__(E5MultilingualEmbedder)
        embedder._query_cache = _EmbeddingCache(maxsize=10)
        embedder.QUERY_PREFIX = "query: "

        fake_vec = [0.3] * 1024
        with patch.object(embedder, "_encode", return_value=[fake_vec]) as mock_encode:
            # First call
            result1 = embedder.embed_query("test query")
            assert result1 == fake_vec
            assert mock_encode.call_count == 1

            # Second call — cached
            result2 = embedder.embed_query("test query")
            assert result2 == fake_vec
            assert mock_encode.call_count == 1

        assert embedder._query_cache.stats["hits"] == 1

    def test_e5_different_queries_not_cached(self):
        """Different queries should not return cached results."""
        from embedding.e5_multilingual import E5MultilingualEmbedder, _EmbeddingCache

        embedder = E5MultilingualEmbedder.__new__(E5MultilingualEmbedder)
        embedder._query_cache = _EmbeddingCache(maxsize=10)
        embedder.QUERY_PREFIX = "query: "

        vec1 = [0.1] * 1024
        vec2 = [0.9] * 1024
        call_count = [0]

        def mock_encode(texts):
            call_count[0] += 1
            if "query1" in texts[0]:
                return [vec1]
            return [vec2]

        with patch.object(embedder, "_encode", side_effect=mock_encode):
            r1 = embedder.embed_query("query1")
            r2 = embedder.embed_query("query2")
            assert r1 == vec1
            assert r2 == vec2
            assert call_count[0] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Search Result Cache (TTL)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchResultCache:
    """Test the _SearchResultCache in retrieval/service.py."""

    def test_cache_miss_then_hit(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=60.0)

        results = [{"id": "1", "text": "doc1", "score": 0.9}]
        assert cache.get("query", ["stsv"]) is None
        cache.put("query", ["stsv"], results)
        cached = cache.get("query", ["stsv"])
        assert cached == results

    def test_cache_ttl_expiry(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=0.1)  # 100ms TTL

        results = [{"id": "1", "text": "doc1"}]
        cache.put("query", ["stsv"], results)

        # Should be present immediately
        assert cache.get("query", ["stsv"]) is not None

        # Wait for TTL expiry
        time.sleep(0.15)
        assert cache.get("query", ["stsv"]) is None

    def test_cache_different_collections_different_keys(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=60.0)

        results_stsv = [{"id": "1", "text": "stsv doc"}]
        results_ctdt = [{"id": "2", "text": "ctdt doc"}]

        cache.put("query", ["stsv"], results_stsv)
        cache.put("query", ["ctdt"], results_ctdt)

        assert cache.get("query", ["stsv"]) == results_stsv
        assert cache.get("query", ["ctdt"]) == results_ctdt

    def test_cache_with_metadata_filters(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=60.0)

        results = [{"id": "1", "text": "doc"}]
        cache.put("query", ["ctdt"], results, resolved_major="IT-E6")

        # Same query without major → miss
        assert cache.get("query", ["ctdt"]) is None
        # With major → hit
        assert cache.get("query", ["ctdt"], resolved_major="IT-E6") == results

    def test_cache_maxsize_eviction(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=2, ttl_seconds=60.0)

        cache.put("q1", ["stsv"], [{"id": "1"}])
        cache.put("q2", ["stsv"], [{"id": "2"}])
        cache.put("q3", ["stsv"], [{"id": "3"}])  # evicts q1

        assert cache.get("q1", ["stsv"]) is None
        assert cache.get("q2", ["stsv"]) is not None
        assert cache.get("q3", ["stsv"]) is not None

    def test_cache_stats(self):
        from retrieval.service import _SearchResultCache

        cache = _SearchResultCache(maxsize=10, ttl_seconds=60.0)

        cache.put("q", ["s"], [{"id": "1"}])
        cache.get("q", ["s"])  # hit
        cache.get("miss", ["s"])  # miss

        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 1
        assert cache.stats["size"] == 1

    def test_service_uses_cache(self):
        """Integration: RetrievalService._search_single uses cache."""
        from retrieval.service import RetrievalService

        # Build a minimal service with mocks
        mock_settings = MagicMock()
        mock_settings.top_k = 5
        mock_settings.vector_top_k = 20
        mock_settings.keyword_top_k = 20
        mock_settings.vector_pool_k = 15
        mock_settings.keyword_pool_k = 15

        mock_searcher = MagicMock()
        mock_searcher.search.return_value = [
            {"id": "1", "text": "result", "score": 0.9}
        ]

        service = RetrievalService(
            settings=mock_settings,
            bge_embedder=MagicMock(),
            e5_embedder=MagicMock(),
            searcher=mock_searcher,
            reranker=None,
        )
        service.bge_embedder.embed_query.return_value = [0.1] * 1024
        service.e5_embedder.embed_query.return_value = [0.2] * 1024

        # First call — cache miss, calls searcher
        r1 = service._search_single(
            "test", effective_top_k=5, raw_candidate_k=20,
            active_collections=["stsv"], resolved_major=None,
            resolved_cohort=None, rerank=False,
        )
        assert mock_searcher.search.call_count == 1

        # Second call — cache hit, searcher NOT called again
        r2 = service._search_single(
            "test", effective_top_k=5, raw_candidate_k=20,
            active_collections=["stsv"], resolved_major=None,
            resolved_cohort=None, rerank=False,
        )
        assert mock_searcher.search.call_count == 1  # still 1
        assert r1 == r2


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Elasticsearch Synonym Filter & BM25 Tuning
# ═══════════════════════════════════════════════════════════════════════════════


class TestElasticsearchSettings:
    """Verify _make_settings includes synonyms, stopwords, and BM25 tuning."""

    def _get_settings(self, use_icu: bool = True) -> Dict[str, Any]:
        from retrieval.elasticsearch_store import ElasticsearchStore

        return ElasticsearchStore._make_settings(use_icu=use_icu)

    def test_synonym_filter_defined_icu(self):
        settings = self._get_settings(use_icu=True)
        filters = settings["settings"]["analysis"]["filter"]
        assert "vietnamese_synonym" in filters
        synonyms = filters["vietnamese_synonym"]["synonyms"]
        # Check key abbreviations are present
        synonym_text = " ".join(synonyms)
        assert "CTDT" in synonym_text
        assert "chương trình đào tạo" in synonym_text
        assert "STSV" in synonym_text
        assert "sổ tay sinh viên" in synonym_text
        assert "CNTT" in synonym_text
        assert "công nghệ thông tin" in synonym_text

    def test_synonym_filter_defined_standard(self):
        settings = self._get_settings(use_icu=False)
        filters = settings["settings"]["analysis"]["filter"]
        assert "vietnamese_synonym" in filters

    def test_stopwords_filter_defined(self):
        settings = self._get_settings(use_icu=True)
        filters = settings["settings"]["analysis"]["filter"]
        assert "vietnamese_stop" in filters
        stopwords = filters["vietnamese_stop"]["stopwords"]
        assert "và" in stopwords
        assert "của" in stopwords
        assert "trong" in stopwords

    def test_analyzer_includes_synonym_and_stop_filters(self):
        settings = self._get_settings(use_icu=True)
        analyzer = settings["settings"]["analysis"]["analyzer"]["vietnamese_analyzer"]
        assert "vietnamese_synonym" in analyzer["filter"]
        assert "vietnamese_stop" in analyzer["filter"]

    def test_analyzer_standard_fallback_includes_filters(self):
        settings = self._get_settings(use_icu=False)
        analyzer = settings["settings"]["analysis"]["analyzer"]["vietnamese_analyzer"]
        assert "vietnamese_synonym" in analyzer["filter"]
        assert "vietnamese_stop" in analyzer["filter"]
        assert "asciifolding" in analyzer["filter"]

    def test_bm25_custom_similarity(self):
        settings = self._get_settings(use_icu=True)
        similarity = settings["settings"]["index"]["similarity"]["custom_bm25"]
        assert similarity["type"] == "BM25"
        assert similarity["k1"] == 1.5
        assert similarity["b"] == 0.5

    def test_text_fields_use_custom_bm25(self):
        settings = self._get_settings(use_icu=True)
        props = settings["mappings"]["properties"]

        # Primary text fields should use custom_bm25
        assert props["text"]["similarity"] == "custom_bm25"
        assert props["title"]["similarity"] == "custom_bm25"
        assert props["section_h2"]["similarity"] == "custom_bm25"
        assert props["section_h3"]["similarity"] == "custom_bm25"
        assert props["course_name"]["similarity"] == "custom_bm25"
        assert props["major_name"]["similarity"] == "custom_bm25"

    def test_keyword_fields_unchanged(self):
        settings = self._get_settings(use_icu=True)
        props = settings["mappings"]["properties"]

        # Keyword fields should not have similarity setting
        assert "similarity" not in props["major_code"]
        assert "similarity" not in props["applicable_cohort"]
        assert "similarity" not in props["document_type"]

    def test_bm25_params_standard_fallback(self):
        settings = self._get_settings(use_icu=False)
        similarity = settings["settings"]["index"]["similarity"]["custom_bm25"]
        assert similarity["k1"] == 1.5
        assert similarity["b"] == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Synonym Coverage — important domain abbreviations
# ═══════════════════════════════════════════════════════════════════════════════


class TestSynonymCoverage:
    """Ensure all critical Vietnamese academic abbreviations are mapped."""

    REQUIRED_ABBREVIATIONS = [
        ("CTDT", "chương trình đào tạo"),
        ("STSV", "sổ tay sinh viên"),
        ("CNTT", "công nghệ thông tin"),
        ("SV", "sinh viên"),
        ("GV", "giảng viên"),
        ("HP", "học phần"),
        ("TC", "tín chỉ"),
        ("HK", "học kỳ"),
        ("KLTN", "khóa luận tốt nghiệp"),
    ]

    def test_all_critical_abbreviations_present(self):
        from retrieval.elasticsearch_store import ElasticsearchStore

        settings = ElasticsearchStore._make_settings(use_icu=True)
        synonyms = settings["settings"]["analysis"]["filter"]["vietnamese_synonym"]["synonyms"]
        synonym_text = "\n".join(synonyms).lower()

        for abbr, full_form in self.REQUIRED_ABBREVIATIONS:
            assert abbr.lower() in synonym_text, (
                f"Missing synonym mapping for {abbr}"
            )
            assert full_form.lower() in synonym_text, (
                f"Missing full form '{full_form}' for {abbr}"
            )
