"""Tests for Phase 3: Parent-Child Chunk Indexing & Context Expansion.

Covers:
  1. Index script — discover files, load chunks, prepare for indexing
  2. Parent context retrieval — expand children with parent context
  3. Service integration — parent expansion in search pipeline
  4. Parent filtering — exclude parents from vector + keyword search
  5. Config — parent_context_enabled flag
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ─── Mock heavy dependencies ─────────────────────────────────────────────────


def _mock_heavy_deps():
    """Mock heavy dependencies not available locally."""
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

    # Setup qdrant_client.models with necessary attributes
    qdrant_models = sys.modules["qdrant_client.models"]
    qdrant_models.Filter = MagicMock
    qdrant_models.FieldCondition = MagicMock
    qdrant_models.MatchValue = MagicMock
    qdrant_models.VectorParams = MagicMock
    qdrant_models.Distance = MagicMock()
    qdrant_models.Distance.COSINE = "Cosine"


_mock_heavy_deps()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Index Script — File Discovery & Chunk Preparation
# ═══════════════════════════════════════════════════════════════════════════════


class TestIndexScriptDiscovery:
    """Test chunk file discovery and loading logic."""

    def test_discover_ctdt_files(self, tmp_path):
        """Should find JSON files in chunks_recursive_parent_child/ subfolders."""
        from scripts.index_parent_child import discover_chunk_files, PARENT_CHILD_SOURCES, DATA_DIR

        # Patch DATA_DIR to use temp path
        ctdt_dir = tmp_path / "ctdt" / "soict" / "chunks_recursive_parent_child"
        ctdt_dir.mkdir(parents=True)
        (ctdt_dir / "test_chunks.json").write_text("[]", encoding="utf-8")
        (ctdt_dir / "another_chunks.json").write_text("[]", encoding="utf-8")

        with patch("scripts.index_parent_child.DATA_DIR", tmp_path):
            files = discover_chunk_files("ctdt", subfolder="soict")

        assert len(files) == 2
        assert all(f[1] == "soict" for f in files)

    def test_discover_no_files(self, tmp_path):
        from scripts.index_parent_child import discover_chunk_files

        with patch("scripts.index_parent_child.DATA_DIR", tmp_path):
            files = discover_chunk_files("ctdt", subfolder="nonexistent")
        assert files == []

    def test_discover_unknown_collection(self, tmp_path):
        from scripts.index_parent_child import discover_chunk_files

        with patch("scripts.index_parent_child.DATA_DIR", tmp_path):
            files = discover_chunk_files("unknown_collection")
        assert files == []

    def test_load_chunks_list_format(self, tmp_path):
        from scripts.index_parent_child import load_chunks

        chunks = [
            {"id": "abc", "content": "Hello", "metadata": {"level": "child"}},
            {"id": "def", "content": "World", "metadata": {"level": "parent"}},
        ]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(chunks), encoding="utf-8")
        loaded = load_chunks(f)
        assert len(loaded) == 2
        assert loaded[0]["id"] == "abc"

    def test_load_chunks_dict_format(self, tmp_path):
        from scripts.index_parent_child import load_chunks

        data = {"chunks": [{"id": "x", "content": "Text", "metadata": {}}]}
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_chunks(f)
        assert len(loaded) == 1
        assert loaded[0]["id"] == "x"


class TestChunkPreparation:
    """Test prepare_chunk_for_indexing logic."""

    def test_prepare_valid_child(self):
        from scripts.index_parent_child import prepare_chunk_for_indexing

        chunk = {
            "id": "uuid-123",
            "content": "Some content here",
            "metadata": {
                "level": "child",
                "parent_id": "uuid-parent",
                "doc_title": "Test Doc",
            },
        }
        result = prepare_chunk_for_indexing(chunk, "ctdt", "soict", "file.json")
        assert result is not None
        assert result["id"] == "uuid-123"
        assert result["text"] == "Some content here"
        assert result["metadata"]["collection"] == "ctdt"
        assert result["metadata"]["subfolder"] == "soict"
        assert result["metadata"]["source_file"] == "file.json"
        assert result["metadata"]["level"] == "child"
        assert result["metadata"]["parent_id"] == "uuid-parent"

    def test_prepare_valid_parent(self):
        from scripts.index_parent_child import prepare_chunk_for_indexing

        chunk = {
            "id": "uuid-parent",
            "content": "Parent content with children",
            "metadata": {
                "level": "parent",
                "parent_id": None,
                "child_count": 3,
                "chunk_type": "parent",
            },
        }
        result = prepare_chunk_for_indexing(chunk, "ctdt", "hoa", "doc.json")
        assert result is not None
        assert result["metadata"]["level"] == "parent"
        assert result["metadata"]["child_count"] == 3

    def test_prepare_empty_content_returns_none(self):
        from scripts.index_parent_child import prepare_chunk_for_indexing

        chunk = {"id": "empty", "content": "", "metadata": {}}
        result = prepare_chunk_for_indexing(chunk, "ctdt", "soict", "f.json")
        assert result is None

    def test_prepare_no_id_returns_none(self):
        from scripts.index_parent_child import prepare_chunk_for_indexing

        chunk = {"content": "text", "metadata": {}}
        result = prepare_chunk_for_indexing(chunk, "ctdt", "soict", "f.json")
        assert result is None

    def test_prepare_defaults_level_to_child(self):
        from scripts.index_parent_child import prepare_chunk_for_indexing

        chunk = {"id": "x", "content": "text", "metadata": {}}
        result = prepare_chunk_for_indexing(chunk, "ctdt", "soict", "f.json")
        assert result["metadata"]["level"] == "child"
        assert result["metadata"]["parent_id"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Parent Context Retrieval Module
# ═══════════════════════════════════════════════════════════════════════════════


class TestParentContextExpander:
    """Test ParentContextExpander logic."""

    def _make_expander(self):
        from retrieval.parent_context import ParentContextExpander
        expander = ParentContextExpander(
            qdrant_host="localhost",
            qdrant_port=6333,
            max_parent_chars=500,
        )
        # Mock the client
        expander._client = MagicMock()
        return expander

    def test_expand_empty_results(self):
        expander = self._make_expander()
        result = expander.expand_with_parents([], "ctdt")
        assert result == []

    def test_expand_no_parent_ids(self):
        """Results without parent_id should pass through unchanged."""
        expander = self._make_expander()
        results = [
            {"id": "1", "text": "Child text", "metadata": {"level": "child", "parent_id": None}},
            {"id": "2", "text": "Another", "metadata": {"level": "parent", "parent_id": None}},
        ]
        expanded = expander.expand_with_parents(results, "ctdt")
        assert len(expanded) == 2
        # No parent_context should be added
        assert "parent_context" not in expanded[0].get("metadata", {})

    def test_expand_with_parent_id_fetches_parent(self):
        """Child with parent_id should get parent_context in metadata."""
        expander = self._make_expander()

        # Mock parent point
        mock_point = MagicMock()
        mock_point.id = "parent-uuid"
        mock_point.payload = {
            "text": "Parent full content about curriculum",
            "hierarchy_path": "Root > Section",
            "section_h2": "Section Title",
        }
        expander._client.retrieve.return_value = [mock_point]

        results = [
            {
                "id": "child-1",
                "text": "Child text",
                "metadata": {
                    "level": "child",
                    "parent_id": "parent-uuid",
                },
            }
        ]
        expanded = expander.expand_with_parents(results, "ctdt")

        assert len(expanded) == 1
        meta = expanded[0]["metadata"]
        assert "parent_context" in meta
        assert "curriculum" in meta["parent_context"]
        assert meta["parent_title"] == "Root > Section"
        assert meta["parent_section_h2"] == "Section Title"

    def test_expand_truncates_parent_content(self):
        """Parent content exceeding max_parent_chars should be truncated."""
        expander = self._make_expander()
        expander._max_parent_chars = 50

        mock_point = MagicMock()
        mock_point.id = "parent-uuid"
        mock_point.payload = {
            "text": "A" * 200,  # Very long parent content
            "hierarchy_path": "",
            "section_h2": "",
        }
        expander._client.retrieve.return_value = [mock_point]

        results = [
            {
                "id": "child-1",
                "text": "Child",
                "metadata": {"level": "child", "parent_id": "parent-uuid"},
            }
        ]
        expanded = expander.expand_with_parents(results, "ctdt")
        parent_ctx = expanded[0]["metadata"]["parent_context"]
        assert len(parent_ctx) == 53  # 50 + "..."
        assert parent_ctx.endswith("...")

    def test_expand_deduplicates_parent_fetches(self):
        """Multiple children sharing same parent → one fetch call."""
        expander = self._make_expander()

        mock_point = MagicMock()
        mock_point.id = "shared-parent"
        mock_point.payload = {
            "text": "Shared parent content",
            "hierarchy_path": "Path",
            "section_h2": "H2",
        }
        expander._client.retrieve.return_value = [mock_point]

        results = [
            {"id": "c1", "text": "Child 1", "metadata": {"level": "child", "parent_id": "shared-parent"}},
            {"id": "c2", "text": "Child 2", "metadata": {"level": "child", "parent_id": "shared-parent"}},
            {"id": "c3", "text": "Child 3", "metadata": {"level": "child", "parent_id": "shared-parent"}},
        ]
        expanded = expander.expand_with_parents(results, "ctdt")

        # Should only call retrieve once with the deduplicated parent ID
        expander._client.retrieve.assert_called_once()
        call_args = expander._client.retrieve.call_args
        assert "shared-parent" in call_args.kwargs.get("ids", call_args[1].get("ids", []))

        # All three children should have parent context
        for item in expanded:
            assert "parent_context" in item["metadata"]

    def test_get_parent_for_child_no_parent_id(self):
        """get_parent_for_child returns None when no parent_id."""
        expander = self._make_expander()
        result = expander.get_parent_for_child(
            {"id": "x", "metadata": {"level": "child", "parent_id": None}},
            "ctdt",
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Service Integration — Parent Expansion in Pipeline
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceParentExpansion:
    """Test _expand_parent_context in RetrievalService."""

    def _make_service_with_settings(self, parent_enabled=True):
        """Create a minimal RetrievalService mock."""
        from retrieval.service import RetrievalService

        settings = MagicMock()
        settings.parent_context_enabled = parent_enabled
        settings.qdrant_host = "localhost"
        settings.qdrant_port = 6333
        settings.parent_max_chars = 3000
        settings.top_k = 10
        settings.collections = ["ctdt", "stsv"]

        service = RetrievalService(
            settings=settings,
            bge_embedder=MagicMock(),
            e5_embedder=MagicMock(),
            searcher=MagicMock(),
            reranker=None,
        )
        return service

    def test_expand_skipped_when_disabled(self):
        """When parent_context_enabled=False, results pass through unchanged."""
        service = self._make_service_with_settings(parent_enabled=False)
        results = [
            {"id": "1", "text": "test", "metadata": {"level": "child", "parent_id": "p1"}, "collection": "ctdt"}
        ]
        # Should not modify results (feature disabled)
        expanded = service._expand_parent_context(results, ["ctdt"])
        assert expanded == results

    def test_expand_skipped_when_no_parent_ids(self):
        """When no results have parent_id, skip expansion."""
        service = self._make_service_with_settings(parent_enabled=True)
        results = [
            {"id": "1", "text": "test", "metadata": {"level": "child", "parent_id": None}, "collection": "ctdt"},
            {"id": "2", "text": "test2", "metadata": {"level": "child"}, "collection": "ctdt"},
        ]
        # Should pass through without error
        expanded = service._expand_parent_context(results, ["ctdt"])
        assert len(expanded) == 2

    @patch("retrieval.parent_context.ParentContextExpander")
    def test_expand_called_when_parent_ids_present(self, MockExpander):
        """When results have parent_ids, expansion should be called."""
        service = self._make_service_with_settings(parent_enabled=True)

        mock_instance = MockExpander.return_value
        mock_instance.expand_with_parents.return_value = [
            {"id": "c1", "text": "child", "metadata": {"level": "child", "parent_id": "p1", "parent_context": "parent text"}, "collection": "ctdt"}
        ]

        results = [
            {"id": "c1", "text": "child", "metadata": {"level": "child", "parent_id": "p1"}, "collection": "ctdt"}
        ]
        expanded = service._expand_parent_context(results, ["ctdt"])

        MockExpander.assert_called_once()
        assert mock_instance.expand_with_parents.called

    def test_expand_handles_exception_gracefully(self):
        """If parent expansion fails, results should still be returned."""
        service = self._make_service_with_settings(parent_enabled=True)
        results = [
            {"id": "c1", "text": "child", "metadata": {"level": "child", "parent_id": "p1"}, "collection": "ctdt"}
        ]

        with patch("retrieval.parent_context.ParentContextExpander", side_effect=Exception("Connection refused")):
            expanded = service._expand_parent_context(results, ["ctdt"])

        # Should return original results despite error
        assert len(expanded) == 1
        assert expanded[0]["id"] == "c1"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Parent Filtering — Exclude Parents from Search
# ═══════════════════════════════════════════════════════════════════════════════


class TestParentFiltering:
    """Test that parent chunks are excluded from search results."""

    def test_es_must_not_includes_parent_level(self):
        """keyword_search should add must_not for level=parent."""
        # Read the source and verify the filter is present
        source_path = Path(__file__).resolve().parent.parent / "retrieval" / "elasticsearch_store.py"
        source = source_path.read_text(encoding="utf-8")
        assert '{"term": {"level": "parent"}}' in source

    def test_qdrant_filter_excludes_parent_level(self):
        """multi_collection_search._fetch_one should add must_not for level=parent."""
        source_path = Path(__file__).resolve().parent.parent / "retrieval" / "multi_collection_search.py"
        source = source_path.read_text(encoding="utf-8")
        # Verify the parent exclusion filter is added
        assert 'key="level"' in source
        assert 'match=qdrant_models.MatchValue(value="parent")' in source
        assert "must_not" in source


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Config — parent_context_enabled
# ═══════════════════════════════════════════════════════════════════════════════


class TestParentContextConfig:
    """Verify parent-child config in settings."""

    @pytest.fixture(autouse=True)
    def _settings_source(self):
        settings_path = Path(__file__).resolve().parent.parent / "config" / "settings.py"
        self.source = settings_path.read_text(encoding="utf-8")

    def test_parent_context_enabled_default(self):
        """parent_context_enabled should default to True."""
        assert "parent_context_enabled: bool = True" in self.source

    def test_parent_max_chars_config(self):
        """parent_max_chars should be configurable (reduced to 1500 to prevent budget overflow)."""
        assert "parent_max_chars: int = 1500" in self.source


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Integration: Dry-Run Indexing
# ═══════════════════════════════════════════════════════════════════════════════


class TestDryRunIndexing:
    """Test the dry-run mode of indexing script."""

    def test_dry_run_reports_stats(self, tmp_path):
        from scripts.index_parent_child import run_indexing

        # Create test data
        ctdt_dir = tmp_path / "ctdt" / "soict" / "chunks_recursive_parent_child"
        ctdt_dir.mkdir(parents=True)
        chunks = [
            {"id": "p1", "content": "Parent content", "metadata": {"level": "parent", "child_count": 2}},
            {"id": "c1", "content": "Child 1", "metadata": {"level": "child", "parent_id": "p1"}},
            {"id": "c2", "content": "Child 2", "metadata": {"level": "child", "parent_id": "p1"}},
        ]
        (ctdt_dir / "test.json").write_text(json.dumps(chunks), encoding="utf-8")

        with patch("scripts.index_parent_child.DATA_DIR", tmp_path):
            stats = run_indexing("ctdt", subfolder="soict", dry_run=True)

        assert stats["files"] == 1
        assert stats["total_chunks"] == 3
        assert stats["parents"] == 1
        assert stats["children"] == 2

    def test_dry_run_empty_collection(self, tmp_path):
        from scripts.index_parent_child import run_indexing

        with patch("scripts.index_parent_child.DATA_DIR", tmp_path):
            stats = run_indexing("ctdt", subfolder="soict", dry_run=True)

        assert stats["files"] == 0
        assert stats["total_chunks"] == 0
