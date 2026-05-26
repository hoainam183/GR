"""Phase 2 Tests — Parent context expansion logic (isolated from heavy imports).

Tests the LOGIC of:
  - _format_context parent prepend behavior
  - _expand_parent_context_post_rerank helper
  - _format_search_results parent context inclusion

These tests replicate the exact logic from flows.py and tool_adapters.py
without importing the full module chain (which requires openai, torch, etc.).

Run from src/RAG_v2:
    pytest tests/test_parent_context_phase2.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ═══════════════════════════════════════════════════════════════════════════════
# Replicate _format_context logic for isolated testing
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_CONTEXT_DOC_CHAR_LIMIT = 2000
_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET = 12000


def _format_context_impl(
    documents: List[Dict[str, Any]],
    *,
    per_doc_char_limit: int = _DEFAULT_CONTEXT_DOC_CHAR_LIMIT,
    total_char_budget: int = _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET,
    sibling_per_doc_limit: int = 800,
    trace_out: Optional[Dict[str, Any]] = None,
) -> str:
    """Exact replica of _format_context from flows.py (with parent context support)."""
    parts: List[str] = []
    used = 0
    docs_used = 0
    for i, doc in enumerate(documents, 1):
        meta = doc.get("metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or "Tài liệu không rõ nguồn"

        meta_parts = []
        if meta.get("major_code"):
            meta_parts.append(f"Mã ngành: {meta['major_code']}")
        if meta.get("major_name"):
            meta_parts.append(f"Ngành: {meta['major_name']}")
        if meta.get("applicable_cohort"):
            meta_parts.append(f"Khóa: {meta['applicable_cohort']}")
        if doc.get("collection") == "kehoach":
            if meta.get("date_str"):
                meta_parts.append(f"Ngày đăng: {meta['date_str']}")
            if meta.get("url"):
                meta_parts.append(f"URL: {meta['url']}")
        meta_str = f" [{', '.join(meta_parts)}]" if meta_parts else ""

        text = str(doc.get("text", "") or "").strip()

        # C5: Prepend parent context for broader section context
        parent_ctx = str((meta.get("parent_context") or "")).strip()
        parent_title = str(
            (meta.get("parent_title") or meta.get("parent_section_h2") or "")
        ).strip()
        if parent_ctx:
            parent_header = (
                f"[Ngữ cảnh section: {parent_title}]"
                if parent_title
                else "[Ngữ cảnh section]"
            )
            text = f"{parent_header}\n{parent_ctx}\n\n[Chi tiết]\n{text}"

        effective_limit = (
            sibling_per_doc_limit if doc.get("_expansion_source") else per_doc_char_limit
        )
        if parent_ctx:
            effective_limit = min(effective_limit + 1500, per_doc_char_limit + 1500)
        if len(text) > effective_limit:
            text = text[:effective_limit] + "\u2026"

        chunk = f"--- Văn bản: {title}{meta_str}\n{text}"
        separator_cost = 7 if parts else 0
        if used + len(chunk) + separator_cost > total_char_budget:
            break
        parts.append(chunk)
        docs_used += 1
        used += len(chunk) + separator_cost

    context = "\n\n---\n\n".join(parts)
    if trace_out is not None:
        trace_out["context_chars"] = len(context)
        trace_out["context_docs_used"] = docs_used
        trace_out["context_docs_dropped"] = max(0, len(documents) - docs_used)
    return context


# ═══════════════════════════════════════════════════════════════════════════════
# Replicate _expand_parent_context_post_rerank logic
# ═══════════════════════════════════════════════════════════════════════════════

def _cfg_bool(cfg, key, default):
    value = cfg.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _cfg_int(cfg, key, default):
    try:
        return int(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _expand_helper(
    reranked: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    mock_expander=None,
) -> List[Dict[str, Any]]:
    """Standalone version of _expand_parent_context_post_rerank for testing."""
    if not _cfg_bool(cfg, "parent_context_enabled", True):
        return reranked
    if not reranked:
        return reranked

    has_parent = any(
        r.get("metadata", {}).get("parent_id")
        and str(r.get("metadata", {}).get("level", "child")).strip().lower() == "child"
        for r in reranked
    )
    if not has_parent:
        return reranked

    if mock_expander is None:
        return reranked

    try:
        collection_groups: Dict[str, List[int]] = {}
        for idx, r in enumerate(reranked):
            coll = (
                r.get("collection", "")
                or r.get("metadata", {}).get("collection", "")
            )
            if coll:
                collection_groups.setdefault(coll, []).append(idx)

        for coll, indices in collection_groups.items():
            group = [reranked[i] for i in indices]
            expanded = mock_expander.expand_with_parents(group, coll)
            for i, exp in zip(indices, expanded):
                reranked[i] = exp
    except Exception:
        pass

    return reranked


# ═══════════════════════════════════════════════════════════════════════════════
# Replicate _format_search_results logic (agent path)
# ═══════════════════════════════════════════════════════════════════════════════

def _format_search_results_impl(
    results: Any,
    collection: str,
    result_count: int = 3,
    char_limit: int = 500,
) -> str:
    """Replica of agent _format_search_results with parent context."""
    if not results:
        return f"Khong tim thay thong tin phu hop trong {collection}."

    chunks: list[str] = []

    for index, item in enumerate(results[:result_count], 1):
        content = ""
        source = ""
        metadata = {}

        if isinstance(item, dict):
            metadata = item.get("metadata", {}) or {}
            content = str(item.get("text") or item.get("content") or "")
            source = str(
                item.get("source")
                or metadata.get("source")
                or metadata.get("title")
                or item.get("collection", "")
            )
        else:
            content = str(item)

        content = " ".join(content.split())

        parent_ctx = str((metadata.get("parent_context") or "")).strip()
        if parent_ctx:
            parent_short = parent_ctx[:300] + "..." if len(parent_ctx) > 300 else parent_ctx
            parent_short = " ".join(parent_short.split())
            content = f"[Section] {parent_short}\n[Detail] {content}"

        if len(content) > char_limit:
            content = content[:char_limit].rstrip() + "..."

        if not content:
            continue

        chunk = f"[{index}] {content}"
        if source:
            chunk += f"\n    Nguon: {source}"
        chunks.append(chunk)

    if not chunks:
        return f"Khong tim thay thong tin phu hop trong {collection}."
    return "\n\n".join(chunks)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _format_context with parent context
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatContextWithParent:
    """Verify _format_context prepends parent context to child text."""

    def test_parent_context_prepended(self):
        docs = [
            {
                "text": "Chi tiết: Môn Mạng máy tính có 3 tín chỉ.",
                "metadata": {
                    "title": "CTDT IT1",
                    "parent_context": "Chương trình đào tạo ngành CNTT bao gồm...",
                    "parent_title": "Khối kiến thức chuyên ngành",
                    "level": "child",
                },
            }
        ]
        context = _format_context_impl(docs, per_doc_char_limit=5000, total_char_budget=10000)
        assert "[Ngữ cảnh section: Khối kiến thức chuyên ngành]" in context
        assert "Chương trình đào tạo ngành CNTT bao gồm..." in context
        assert "[Chi tiết]" in context
        assert "Môn Mạng máy tính có 3 tín chỉ" in context

    def test_no_parent_context_unchanged(self):
        docs = [
            {
                "text": "Nội dung bình thường.",
                "metadata": {"title": "Test Doc"},
            }
        ]
        context = _format_context_impl(docs, per_doc_char_limit=5000, total_char_budget=10000)
        assert "[Ngữ cảnh section]" not in context
        assert "[Chi tiết]" not in context
        assert "Nội dung bình thường." in context

    def test_parent_context_empty_string_ignored(self):
        docs = [
            {
                "text": "Regular text.",
                "metadata": {"title": "Test", "parent_context": "", "parent_title": ""},
            }
        ]
        context = _format_context_impl(docs, per_doc_char_limit=5000, total_char_budget=10000)
        assert "[Ngữ cảnh section]" not in context

    def test_parent_context_increases_effective_limit(self):
        parent_text = "P" * 1000
        child_text = "C" * 1500
        docs = [
            {
                "text": child_text,
                "metadata": {
                    "title": "Doc",
                    "parent_context": parent_text,
                    "parent_title": "Section",
                },
            }
        ]
        context = _format_context_impl(docs, per_doc_char_limit=2000, total_char_budget=20000)
        assert parent_text in context
        assert child_text in context

    def test_total_budget_still_caps(self):
        docs = []
        for i in range(10):
            docs.append({
                "text": f"Child text {i} " * 100,
                "metadata": {
                    "title": f"Doc {i}",
                    "parent_context": f"Parent {i} " * 100,
                    "parent_title": f"Section {i}",
                },
            })
        context = _format_context_impl(docs, per_doc_char_limit=2000, total_char_budget=5000)
        # Total should not wildly exceed budget
        assert len(context) <= 8000

    def test_parent_title_fallback_to_generic(self):
        docs = [
            {
                "text": "Detail text.",
                "metadata": {
                    "title": "Doc",
                    "parent_context": "Some parent content",
                    "parent_title": "",
                },
            }
        ]
        context = _format_context_impl(docs, per_doc_char_limit=5000, total_char_budget=10000)
        assert "[Ngữ cảnh section]" in context
        assert "Some parent content" in context


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _expand_parent_context_post_rerank
# ═══════════════════════════════════════════════════════════════════════════════


class TestExpandParentContextPostRerank:
    """Test the expansion helper with mocked ParentContextExpander."""

    def test_disabled_by_flag(self):
        cfg = {"parent_context_enabled": False}
        docs = [{"text": "hello", "metadata": {"level": "child", "parent_id": "abc"}}]
        result = _expand_helper(docs, cfg)
        assert result == docs

    def test_empty_list(self):
        result = _expand_helper([], {"parent_context_enabled": True})
        assert result == []

    def test_no_parent_ids_skips(self):
        docs = [
            {"text": "doc1", "metadata": {"level": "recursive"}},
            {"text": "doc2", "metadata": {"level": "child"}},
        ]
        mock_exp = MagicMock()
        result = _expand_helper(docs, {"parent_context_enabled": True}, mock_expander=mock_exp)
        # No parent_id → expander not called
        mock_exp.expand_with_parents.assert_not_called()
        assert result == docs

    def test_expansion_called_for_children_with_parent_id(self):
        mock_exp = MagicMock()
        enriched_doc = {
            "text": "child text",
            "metadata": {
                "level": "child",
                "parent_id": "parent_123",
                "collection": "ctdt",
                "parent_context": "Parent section content here",
                "parent_title": "Section A",
            },
            "collection": "ctdt",
        }
        mock_exp.expand_with_parents.return_value = [enriched_doc]

        docs = [
            {
                "text": "child text",
                "metadata": {"level": "child", "parent_id": "parent_123", "collection": "ctdt"},
                "collection": "ctdt",
            }
        ]
        result = _expand_helper(docs, {"parent_context_enabled": True}, mock_expander=mock_exp)

        mock_exp.expand_with_parents.assert_called_once()
        call_args = mock_exp.expand_with_parents.call_args
        assert call_args[0][1] == "ctdt"  # collection arg
        assert result[0]["metadata"]["parent_context"] == "Parent section content here"

    def test_multiple_collections_grouped(self):
        mock_exp = MagicMock()

        def side_effect(group, coll):
            return [{**doc, "metadata": {**doc["metadata"], "parent_context": f"from {coll}"}} for doc in group]

        mock_exp.expand_with_parents.side_effect = side_effect

        docs = [
            {"text": "d1", "metadata": {"level": "child", "parent_id": "p1", "collection": "ctdt"}, "collection": "ctdt"},
            {"text": "d2", "metadata": {"level": "child", "parent_id": "p2", "collection": "quydinh"}, "collection": "quydinh"},
        ]

        result = _expand_helper(docs, {"parent_context_enabled": True}, mock_expander=mock_exp)

        assert mock_exp.expand_with_parents.call_count == 2
        assert result[0]["metadata"]["parent_context"] == "from ctdt"
        assert result[1]["metadata"]["parent_context"] == "from quydinh"

    def test_exception_graceful_degradation(self):
        mock_exp = MagicMock()
        mock_exp.expand_with_parents.side_effect = Exception("network error")

        docs = [
            {
                "text": "child",
                "metadata": {"level": "child", "parent_id": "p1", "collection": "ctdt"},
                "collection": "ctdt",
            }
        ]

        result = _expand_helper(docs, {"parent_context_enabled": True}, mock_expander=mock_exp)
        assert result[0]["text"] == "child"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: _format_search_results with parent context (agent path)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatSearchResultsWithParent:
    """Verify agent _format_search_results includes parent context."""

    def test_parent_context_included_in_output(self):
        results = [
            {
                "text": "Điều kiện tốt nghiệp: GPA >= 2.0",
                "metadata": {
                    "source": "quydinh.pdf",
                    "parent_context": "Quy định về tốt nghiệp theo QĐ số 123",
                    "level": "child",
                },
                "collection": "quydinh",
            }
        ]
        output = _format_search_results_impl(results, "quydinh")
        assert "[Section]" in output
        assert "Quy định về tốt nghiệp" in output
        assert "[Detail]" in output
        assert "GPA >= 2.0" in output

    def test_no_parent_context_normal_output(self):
        results = [
            {
                "text": "Regular content here",
                "metadata": {"source": "doc.pdf"},
                "collection": "stsv",
            }
        ]
        output = _format_search_results_impl(results, "stsv")
        assert "[Section]" not in output
        assert "Regular content here" in output

    def test_parent_context_truncated_at_300_chars(self):
        long_parent = "A" * 500
        results = [
            {
                "text": "Child text",
                "metadata": {
                    "source": "doc.pdf",
                    "parent_context": long_parent,
                },
                "collection": "ctdt",
            }
        ]
        output = _format_search_results_impl(results, "ctdt", char_limit=2000)
        # Should be truncated to 300 + "..."
        assert "A" * 300 in output
        assert "A" * 500 not in output
        assert "..." in output

    def test_empty_results(self):
        output = _format_search_results_impl([], "ctdt")
        assert "Khong tim thay" in output
