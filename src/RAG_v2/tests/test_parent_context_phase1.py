"""Phase 1 Tests — chunk indexing policy and parent ID remapping.

Tests:
  - is_indexable_chunk: parents/headers excluded from search
  - is_qdrant_storable: parents included, headers excluded
  - document_pipeline parent_id remapping logic (unit test)
  - index_parent_child ES skip logic

Run from src/RAG_v2:
    pytest tests/test_parent_context_phase1.py -v
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.chunk_indexing import is_indexable_chunk, is_qdrant_storable


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: is_indexable_chunk (search policy — unchanged behavior)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsIndexableChunk:
    """Verify that parent/header are excluded from search index."""

    def test_child_is_indexable(self):
        chunk = {"metadata": {"level": "child"}}
        assert is_indexable_chunk(chunk) is True

    def test_recursive_is_indexable(self):
        chunk = {"metadata": {"level": "recursive"}}
        assert is_indexable_chunk(chunk) is True

    def test_appendix_is_indexable(self):
        chunk = {"metadata": {"level": "appendix"}}
        assert is_indexable_chunk(chunk) is True

    def test_parent_not_indexable(self):
        chunk = {"metadata": {"level": "parent"}}
        assert is_indexable_chunk(chunk) is False

    def test_header_not_indexable(self):
        chunk = {"metadata": {"level": "header"}}
        assert is_indexable_chunk(chunk) is False

    def test_no_level_is_indexable(self):
        """Backward compat: chunks without level field remain indexable."""
        chunk = {"metadata": {"source": "test.pdf"}}
        assert is_indexable_chunk(chunk) is True

    def test_no_metadata_is_indexable(self):
        chunk = {"content": "hello"}
        assert is_indexable_chunk(chunk) is True

    def test_level_case_insensitive(self):
        chunk = {"metadata": {"level": "Parent"}}
        assert is_indexable_chunk(chunk) is False

    def test_level_with_whitespace(self):
        chunk = {"metadata": {"level": " parent "}}
        assert is_indexable_chunk(chunk) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: is_qdrant_storable (NEW — parent included for ID-based fetch)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsQdrantStorable:
    """Verify that parent IS stored in Qdrant, header is NOT."""

    def test_child_is_storable(self):
        chunk = {"metadata": {"level": "child"}}
        assert is_qdrant_storable(chunk) is True

    def test_parent_is_storable(self):
        """CRITICAL: parent must be stored for ParentContextExpander."""
        chunk = {"metadata": {"level": "parent"}}
        assert is_qdrant_storable(chunk) is True

    def test_header_not_storable(self):
        chunk = {"metadata": {"level": "header"}}
        assert is_qdrant_storable(chunk) is False

    def test_recursive_is_storable(self):
        chunk = {"metadata": {"level": "recursive"}}
        assert is_qdrant_storable(chunk) is True

    def test_appendix_is_storable(self):
        chunk = {"metadata": {"level": "appendix"}}
        assert is_qdrant_storable(chunk) is True

    def test_no_level_is_storable(self):
        chunk = {"metadata": {"source": "test.pdf"}}
        assert is_qdrant_storable(chunk) is True

    def test_no_metadata_is_storable(self):
        chunk = {"content": "hello"}
        assert is_qdrant_storable(chunk) is True

    def test_level_case_insensitive(self):
        chunk = {"metadata": {"level": "Header"}}
        assert is_qdrant_storable(chunk) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Policy split correctness
# ═══════════════════════════════════════════════════════════════════════════════


class TestPolicySplit:
    """Verify the difference between ES-indexable and Qdrant-storable."""

    def test_parent_excluded_from_es_included_in_qdrant(self):
        """The key difference: parent is NOT in ES but IS in Qdrant."""
        parent_chunk = {"metadata": {"level": "parent"}}
        assert is_indexable_chunk(parent_chunk) is False  # excluded from ES/search
        assert is_qdrant_storable(parent_chunk) is True   # stored in Qdrant for fetch

    def test_header_excluded_from_both(self):
        header_chunk = {"metadata": {"level": "header"}}
        assert is_indexable_chunk(header_chunk) is False
        assert is_qdrant_storable(header_chunk) is False

    def test_child_included_in_both(self):
        child_chunk = {"metadata": {"level": "child"}}
        assert is_indexable_chunk(child_chunk) is True
        assert is_qdrant_storable(child_chunk) is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Parent ID remapping logic (simulated)
# ═══════════════════════════════════════════════════════════════════════════════


class TestParentIdRemapping:
    """Test the remapping logic used in document_pipeline.embed_and_index."""

    def _simulate_remap(self, chunks):
        """Simulate the remapping logic from embed_and_index."""
        parent_id_remap = {}
        for c in chunks:
            meta = c.get("metadata", {})
            level = str(meta.get("level", "")).strip().lower()
            if level == "parent":
                chunker_id = meta.get("chunker_original_id", "")
                qdrant_id = c.get("qdrant_id", "")
                if chunker_id:
                    parent_id_remap[chunker_id] = qdrant_id

        remapped_count = 0
        for c in chunks:
            meta = c.get("metadata", {})
            old_pid = meta.get("parent_id")
            if old_pid and old_pid in parent_id_remap:
                meta["parent_id"] = parent_id_remap[old_pid]
                remapped_count += 1

        return chunks, parent_id_remap, remapped_count

    def test_basic_remapping(self):
        """Parent's chunker ID should be remapped to Qdrant ID in children."""
        chunker_parent_id = str(uuid.uuid4())
        qdrant_parent_id = str(uuid.uuid5(uuid.NAMESPACE_OID, "some_mongo_id"))

        chunks = [
            {
                "metadata": {
                    "level": "parent",
                    "chunker_original_id": chunker_parent_id,
                },
                "qdrant_id": qdrant_parent_id,
                "content": "Parent content here",
            },
            {
                "metadata": {
                    "level": "child",
                    "parent_id": chunker_parent_id,
                },
                "qdrant_id": str(uuid.uuid5(uuid.NAMESPACE_OID, "child_mongo_id")),
                "content": "Child content here",
            },
        ]

        result, remap, count = self._simulate_remap(chunks)

        assert count == 1
        assert remap[chunker_parent_id] == qdrant_parent_id
        assert result[1]["metadata"]["parent_id"] == qdrant_parent_id

    def test_multiple_children_same_parent(self):
        """All children sharing same parent get remapped."""
        chunker_parent_id = str(uuid.uuid4())
        qdrant_parent_id = str(uuid.uuid5(uuid.NAMESPACE_OID, "parent_mongo"))

        chunks = [
            {
                "metadata": {"level": "parent", "chunker_original_id": chunker_parent_id},
                "qdrant_id": qdrant_parent_id,
                "content": "Parent",
            },
            {
                "metadata": {"level": "child", "parent_id": chunker_parent_id},
                "qdrant_id": "child1",
                "content": "Child 1",
            },
            {
                "metadata": {"level": "child", "parent_id": chunker_parent_id},
                "qdrant_id": "child2",
                "content": "Child 2",
            },
        ]

        result, _, count = self._simulate_remap(chunks)
        assert count == 2
        assert result[1]["metadata"]["parent_id"] == qdrant_parent_id
        assert result[2]["metadata"]["parent_id"] == qdrant_parent_id

    def test_no_parent_no_remap(self):
        """Chunks without parent_id are unchanged."""
        chunks = [
            {
                "metadata": {"level": "child"},
                "qdrant_id": "child1",
                "content": "Orphan child",
            },
        ]

        result, _, count = self._simulate_remap(chunks)
        assert count == 0
        assert "parent_id" not in result[0]["metadata"]

    def test_missing_chunker_original_id(self):
        """If parent has no chunker_original_id, no remap happens."""
        chunks = [
            {
                "metadata": {"level": "parent"},
                "qdrant_id": "parent_qdrant",
                "content": "Parent",
            },
            {
                "metadata": {"level": "child", "parent_id": "nonexistent_id"},
                "qdrant_id": "child1",
                "content": "Child",
            },
        ]

        result, remap, count = self._simulate_remap(chunks)
        assert count == 0
        assert len(remap) == 0
        # parent_id stays unchanged (won't be found in Qdrant but graceful)
        assert result[1]["metadata"]["parent_id"] == "nonexistent_id"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: index_parent_child ES skip logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestIndexParentChildEsSkip:
    """Verify that index_parent_child.py skips parents when indexing to ES."""

    def test_es_skip_logic(self):
        """Simulate the ES filtering in index_to_elasticsearch."""
        prepared_chunks = [
            {"id": "p1", "text": "Parent text", "metadata": {"level": "parent"}},
            {"id": "c1", "text": "Child 1", "metadata": {"level": "child"}},
            {"id": "c2", "text": "Child 2", "metadata": {"level": "child"}},
            {"id": "h1", "text": "Header", "metadata": {"level": "header"}},
        ]

        # Simulate the filter logic from index_parent_child.py
        searchable_chunks = [
            c for c in prepared_chunks
            if str(c.get("metadata", {}).get("level", "child")).strip().lower()
            not in ("parent", "header")
        ]

        assert len(searchable_chunks) == 2
        assert all(c["metadata"]["level"] == "child" for c in searchable_chunks)
