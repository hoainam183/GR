from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reranking.bge_reranker import BGEReranker


class _FakeModel:
    def compute_score(self, pairs, batch_size: int = 32):  # noqa: ANN001
        return [0.2, -0.1, -0.5, -4.0]


def test_bge_reranker_filters_thresholds_before_top_k() -> None:
    reranker = BGEReranker.__new__(BGEReranker)
    reranker.batch_size = 32
    reranker.top_k = 2
    reranker.score_threshold = 0.0
    reranker.table_score_threshold = -1.0
    reranker._model = _FakeModel()
    reranker.last_stats = {}

    docs = [
        {"id": "text-pass", "text": "text pass", "metadata": {}},
        {"id": "text-fail", "text": "text fail", "metadata": {}},
        {"id": "table-pass", "text": "table 1", "metadata": {"has_table": True}},
        {"id": "table-fail", "text": "table 2", "metadata": {"has_table": True}},
    ]

    result = reranker.rerank("query", docs, top_k=2)

    assert [doc["id"] for doc in result] == ["text-pass", "table-pass"]
    assert reranker.last_stats["rerank_threshold_dropped_count"] == 2
    assert reranker.last_stats["rerank_passing_count"] == 2


def test_bge_reranker_min_top_k_appends_below_threshold_docs() -> None:
    reranker = BGEReranker.__new__(BGEReranker)
    reranker.batch_size = 32
    reranker.top_k = 3
    reranker.score_threshold = 0.0
    reranker.table_score_threshold = -1.0
    reranker._model = _FakeModel()
    reranker.last_stats = {}

    docs = [
        {"id": "text-pass", "text": "text pass", "metadata": {}},
        {"id": "text-fail", "text": "text fail", "metadata": {}},
        {"id": "table-pass", "text": "table 1", "metadata": {"has_table": True}},
        {"id": "table-fail", "text": "table 2", "metadata": {"has_table": True}},
    ]

    result = reranker.rerank("query", docs, top_k=3, min_top_k=3)

    assert [doc["id"] for doc in result] == ["text-pass", "table-pass", "text-fail"]
    assert reranker.last_stats["rerank_strict_returned_ids"] == [
        "text-pass",
        "table-pass",
    ]
    assert reranker.last_stats["rerank_threshold_fallback_used"] is True
    assert reranker.last_stats["rerank_threshold_fallback_count"] == 1
