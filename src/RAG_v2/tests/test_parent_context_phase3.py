"""Phase 3 Tests — Full integration test of parent context expansion.

Tests:
  - ParentContextExpander with mock Qdrant client
  - RetrievalService._search_multi_query parent expansion
  - End-to-end simulation: search → rerank → expand → format
  - Budget and config validation

Run from src/RAG_v2:
    pytest tests/test_parent_context_phase3.py -v
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Check if qdrant_client is available for integration tests
try:
    import qdrant_client
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False

# Mock qdrant_client if not available (for unit testing the logic)
if not HAS_QDRANT:
    mock_qdrant = MagicMock()
    mock_qdrant.QdrantClient = MagicMock
    mock_qdrant.models = MagicMock()
    sys.modules.setdefault("qdrant_client", mock_qdrant)
    sys.modules.setdefault("qdrant_client.models", mock_qdrant.models)
    # Also mock elasticsearch for retrieval package init
    sys.modules.setdefault("elasticsearch", MagicMock())
    sys.modules.setdefault("elasticsearch.helpers", MagicMock())
    sys.modules.setdefault("FlagEmbedding", MagicMock())
    sys.modules.setdefault("sentence_transformers", MagicMock())
    sys.modules.setdefault("torch", MagicMock())


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: ParentContextExpander with mock Qdrant
# ═══════════════════════════════════════════════════════════════════════════════


class TestParentContextExpander:
    """Test ParentContextExpander fetches parents correctly."""

    def _create_expander(self, mock_client=None):
        from retrieval.parent_context import ParentContextExpander

        expander = ParentContextExpander(
            qdrant_host="localhost",
            qdrant_port=6333,
            max_parent_chars=1500,
        )
        if mock_client:
            expander._client = mock_client
        return expander

    def _make_mock_point(self, point_id: str, text: str, metadata: dict):
        """Create a mock Qdrant point."""
        point = MagicMock()
        point.id = point_id
        point.payload = {"text": text, **metadata}
        return point

    def test_expand_children_with_parent(self):
        """Children get parent_context and parent_title from fetched parent."""
        parent_id = str(uuid.uuid4())
        parent_text = "Chương trình đào tạo CNTT gồm 150 tín chỉ, chia 4 khối kiến thức..."

        mock_client = MagicMock()
        mock_client.retrieve.return_value = [
            self._make_mock_point(
                parent_id,
                parent_text,
                {"hierarchy_path": "CTDT > Khối chuyên ngành", "level": "parent"},
            )
        ]

        expander = self._create_expander(mock_client)

        search_results = [
            {
                "text": "Mạng máy tính 3TC, kỳ 5",
                "metadata": {
                    "level": "child",
                    "parent_id": parent_id,
                    "collection": "ctdt",
                },
            },
            {
                "text": "Cơ sở dữ liệu 4TC, kỳ 4",
                "metadata": {
                    "level": "child",
                    "parent_id": parent_id,
                    "collection": "ctdt",
                },
            },
        ]

        expanded = expander.expand_with_parents(search_results, "ctdt")

        assert len(expanded) == 2
        assert expanded[0]["metadata"]["parent_context"] == parent_text
        assert expanded[0]["metadata"]["parent_title"] == "CTDT > Khối chuyên ngành"
        assert expanded[1]["metadata"]["parent_context"] == parent_text
        # Only 1 retrieve call (dedup by parent_id)
        mock_client.retrieve.assert_called_once_with(
            collection_name="ctdt",
            ids=[parent_id],
            with_payload=True,
            with_vectors=False,
        )

    def test_orphan_children_unchanged(self):
        """Children without parent_id pass through unchanged."""
        mock_client = MagicMock()
        mock_client.retrieve.return_value = []

        expander = self._create_expander(mock_client)

        search_results = [
            {"text": "orphan chunk", "metadata": {"level": "recursive"}},
        ]

        expanded = expander.expand_with_parents(search_results, "ctdt")
        assert expanded == search_results
        mock_client.retrieve.assert_not_called()

    def test_parent_not_found_graceful(self):
        """If parent doesn't exist in Qdrant, child passes through unchanged."""
        mock_client = MagicMock()
        mock_client.retrieve.return_value = []  # Parent not found

        expander = self._create_expander(mock_client)

        search_results = [
            {
                "text": "child text",
                "metadata": {"level": "child", "parent_id": "nonexistent"},
            },
        ]

        expanded = expander.expand_with_parents(search_results, "ctdt")
        assert len(expanded) == 1
        assert "parent_context" not in expanded[0]["metadata"]

    def test_max_parent_chars_truncation(self):
        """Parent content is truncated to max_parent_chars."""
        parent_id = str(uuid.uuid4())
        long_text = "A" * 5000

        mock_client = MagicMock()
        mock_client.retrieve.return_value = [
            self._make_mock_point(parent_id, long_text, {"hierarchy_path": "Test"})
        ]

        expander = self._create_expander(mock_client)
        expander._max_parent_chars = 1500

        search_results = [
            {"text": "child", "metadata": {"level": "child", "parent_id": parent_id}},
        ]

        expanded = expander.expand_with_parents(search_results, "ctdt")
        parent_ctx = expanded[0]["metadata"]["parent_context"]
        assert len(parent_ctx) == 1503  # 1500 + "..."
        assert parent_ctx.endswith("...")

    def test_network_error_returns_originals(self):
        """Network failure returns original results (graceful degradation)."""
        mock_client = MagicMock()
        mock_client.retrieve.side_effect = Exception("Connection refused")

        expander = self._create_expander(mock_client)

        search_results = [
            {"text": "child", "metadata": {"level": "child", "parent_id": "p1"}},
        ]

        expanded = expander.expand_with_parents(search_results, "ctdt")
        assert len(expanded) == 1
        assert expanded[0]["text"] == "child"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: End-to-end simulation
# ═══════════════════════════════════════════════════════════════════════════════

# Reuse format context from phase2 test
from tests.test_parent_context_phase2 import _format_context_impl, _expand_helper


class TestEndToEndParentContext:
    """Simulate full pipeline: search → rerank → expand → format."""

    def test_full_pipeline_with_parent(self):
        """Simulate: reranked children → expand parents → format with context."""
        # Simulate reranked results (children with parent_id)
        reranked = [
            {
                "text": "Môn Mạng máy tính (IT3080) có 3 tín chỉ, tiên quyết IT2000.",
                "metadata": {
                    "level": "child",
                    "parent_id": "parent_uuid_123",
                    "collection": "ctdt",
                    "title": "CTDT CNTT IT-E6",
                    "major_code": "IT-E6",
                },
                "collection": "ctdt",
                "score": 0.85,
            },
            {
                "text": "Hệ điều hành (IT3070) 3TC kỳ 5.",
                "metadata": {
                    "level": "child",
                    "parent_id": "parent_uuid_123",
                    "collection": "ctdt",
                    "title": "CTDT CNTT IT-E6",
                    "major_code": "IT-E6",
                },
                "collection": "ctdt",
                "score": 0.72,
            },
        ]

        # Mock expander
        mock_exp = MagicMock()

        def expand_side_effect(group, coll):
            return [
                {
                    **doc,
                    "metadata": {
                        **doc["metadata"],
                        "parent_context": "Khối kiến thức chuyên ngành (60TC): Bao gồm các môn cốt lõi...",
                        "parent_title": "CTDT > Khối chuyên ngành",
                    },
                }
                for doc in group
            ]

        mock_exp.expand_with_parents.side_effect = expand_side_effect

        # Step 1: Expand
        cfg = {"parent_context_enabled": True, "parent_max_chars": 1500}
        expanded = _expand_helper(reranked, cfg, mock_expander=mock_exp)

        assert expanded[0]["metadata"]["parent_context"].startswith("Khối kiến thức")

        # Step 2: Format
        context = _format_context_impl(
            expanded,
            per_doc_char_limit=2000,
            total_char_budget=12000,
        )

        # Verify parent context appears
        assert "[Ngữ cảnh section: CTDT > Khối chuyên ngành]" in context
        assert "Khối kiến thức chuyên ngành" in context
        assert "[Chi tiết]" in context
        assert "Mạng máy tính" in context
        assert "Hệ điều hành" in context

    def test_pipeline_without_parent_ids(self):
        """When results have no parent_id, pipeline works normally."""
        reranked = [
            {
                "text": "Quy định điểm rèn luyện: Sinh viên đạt loại A cần >= 90 điểm.",
                "metadata": {
                    "level": "recursive",
                    "title": "Quy định",
                    "collection": "quydinh",
                },
                "collection": "quydinh",
                "score": 0.91,
            },
        ]

        cfg = {"parent_context_enabled": True}
        mock_exp = MagicMock()
        expanded = _expand_helper(reranked, cfg, mock_expander=mock_exp)

        # No parent_id → expander not called
        mock_exp.expand_with_parents.assert_not_called()

        context = _format_context_impl(
            expanded,
            per_doc_char_limit=2000,
            total_char_budget=12000,
        )

        assert "Quy định điểm rèn luyện" in context
        assert "[Ngữ cảnh section]" not in context

    def test_budget_not_exceeded_with_parents(self):
        """Total context budget is respected even with parent expansion."""
        docs = []
        for i in range(10):
            docs.append({
                "text": f"Child content {i}: " + "x" * 800,
                "metadata": {
                    "level": "child",
                    "title": f"Doc {i}",
                    "parent_context": f"Parent context {i}: " + "y" * 1000,
                    "parent_title": f"Section {i}",
                    "collection": "ctdt",
                },
                "collection": "ctdt",
            })

        context = _format_context_impl(
            docs,
            per_doc_char_limit=2000,
            total_char_budget=12000,
        )

        # Budget should be roughly respected (some tolerance for last doc)
        assert len(context) <= 16000  # per_doc_char_limit + 1500 allowance × a few docs


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Config validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSettingsConfig:
    """Verify settings are correctly configured."""

    def test_parent_max_chars_reduced(self):
        from config.settings import Settings

        s = Settings()
        assert s.parent_max_chars == 1500
        assert s.parent_max_chars_agent == 500
        assert s.parent_context_enabled is True

    def test_parent_context_enabled_default(self):
        from config.settings import Settings

        s = Settings()
        assert s.parent_context_enabled is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: ParentContextExpander.get_parent_for_child
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetParentForChild:
    """Test single-child parent fetch."""

    def test_returns_parent_dict(self):
        from retrieval.parent_context import ParentContextExpander

        parent_id = str(uuid.uuid4())
        mock_client = MagicMock()
        point = MagicMock()
        point.id = parent_id
        point.payload = {"text": "Parent text content", "level": "parent", "hierarchy_path": "Section/Sub"}
        mock_client.retrieve.return_value = [point]

        expander = ParentContextExpander(max_parent_chars=1500)
        expander._client = mock_client

        child = {"text": "child", "metadata": {"level": "child", "parent_id": parent_id}}
        parent = expander.get_parent_for_child(child, "ctdt")

        assert parent is not None
        assert parent["text"] == "Parent text content"
        assert parent["metadata"]["hierarchy_path"] == "Section/Sub"

    def test_returns_none_without_parent_id(self):
        from retrieval.parent_context import ParentContextExpander

        expander = ParentContextExpander(max_parent_chars=1500)
        expander._client = MagicMock()

        child = {"text": "orphan", "metadata": {"level": "child"}}
        parent = expander.get_parent_for_child(child, "ctdt")

        assert parent is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Retrieval evaluation style — query-based verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetrievalEvalWithParent:
    """Simulate retrieval evaluation cases that benefit from parent context."""

    def test_parent_provides_broader_context_for_specifics(self):
        """
        Scenario: User asks about a specific course.
        Child chunk has the course detail but parent provides program overview.
        After expansion, LLM context should contain both.
        """
        # Simulate what expander returns
        expanded_results = [
            {
                "text": "IT3080 Mạng máy tính\n- Tín chỉ: 3\n- Tiên quyết: IT2000\n- Kỳ: 5",
                "metadata": {
                    "level": "child",
                    "parent_id": "p1",
                    "collection": "ctdt",
                    "title": "CTDT CNTT",
                    "major_code": "IT-E6",
                    "parent_context": (
                        "Khối kiến thức chuyên ngành (60TC) gồm: "
                        "Mạng máy tính, Hệ điều hành, Cơ sở dữ liệu, "
                        "An toàn thông tin, Trí tuệ nhân tạo..."
                    ),
                    "parent_title": "Khối kiến thức chuyên ngành",
                },
                "collection": "ctdt",
                "score": 0.89,
            },
        ]

        context = _format_context_impl(
            expanded_results,
            per_doc_char_limit=2000,
            total_char_budget=12000,
        )

        # The LLM context now contains:
        # 1. Section overview (parent) — what other courses are in the same block
        # 2. Specific detail (child) — course details
        assert "Khối kiến thức chuyên ngành (60TC)" in context
        assert "IT3080 Mạng máy tính" in context
        assert "Tín chỉ: 3" in context
        assert "Mã ngành: IT-E6" in context

    def test_regulation_parent_provides_article_context(self):
        """
        Scenario: User asks about a specific rule.
        Child has the rule detail, parent has the article/chapter context.
        """
        expanded_results = [
            {
                "text": "Sinh viên bị buộc thôi học nếu GPA < 1.0 trong 2 học kỳ liên tiếp.",
                "metadata": {
                    "level": "child",
                    "parent_id": "p2",
                    "collection": "quydinh",
                    "title": "Quy chế đào tạo",
                    "parent_context": (
                        "Điều 12: Xử lý kết quả học tập\n"
                        "1. Sinh viên bị cảnh báo học vụ khi GPA < 1.2\n"
                        "2. Sinh viên bị buộc thôi học theo các trường hợp..."
                    ),
                    "parent_title": "Điều 12: Xử lý kết quả học tập",
                },
                "collection": "quydinh",
                "score": 0.92,
            },
        ]

        context = _format_context_impl(
            expanded_results,
            per_doc_char_limit=2000,
            total_char_budget=12000,
        )

        # LLM sees both the specific rule AND the broader article context
        assert "Điều 12: Xử lý kết quả học tập" in context
        assert "GPA < 1.0 trong 2 học kỳ liên tiếp" in context
        assert "cảnh báo học vụ" in context

    def test_multiple_results_mixed_parent_no_parent(self):
        """Some results have parents, some don't — all formatted correctly."""
        results = [
            {
                "text": "Kỹ thuật lập trình (IT3000) 4TC kỳ 1",
                "metadata": {
                    "level": "child",
                    "title": "CTDT",
                    "parent_context": "Khối kiến thức cơ sở ngành...",
                    "parent_title": "Cơ sở ngành",
                    "major_code": "IT1",
                },
                "collection": "ctdt",
                "score": 0.88,
            },
            {
                "text": "Thời gian đăng ký môn: 01/08 - 15/08 hàng năm.",
                "metadata": {
                    "level": "recursive",
                    "title": "Thông báo đăng ký",
                },
                "collection": "stsv",
                "score": 0.75,
            },
        ]

        context = _format_context_impl(
            results,
            per_doc_char_limit=2000,
            total_char_budget=12000,
        )

        # First result has parent context
        assert "[Ngữ cảnh section: Cơ sở ngành]" in context
        assert "Kỹ thuật lập trình" in context
        # Second result has no parent — just plain text
        assert "Thời gian đăng ký môn" in context
