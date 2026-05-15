from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reranking.bge_reranker import BGEReranker


class _FakeModel:
    def compute_score(self, pairs, batch_size: int = 32):  # noqa: ANN001
        return [0.2, -0.1, -4.0, -4.5]


def test_bge_reranker_filters_thresholds_before_top_k() -> None:
    reranker = BGEReranker.__new__(BGEReranker)
    reranker.batch_size = 32
    reranker.top_k = 2
    reranker.score_threshold = 0.0
    reranker.table_score_threshold = -5.0
    reranker._model = _FakeModel()
    reranker.last_stats = {}

    docs = [
        {"id": "text-pass", "text": "text pass", "metadata": {}},
        {"id": "text-fail", "text": "text fail", "metadata": {}},
        {"id": "table-pass-1", "text": "table 1", "metadata": {"has_table": True}},
        {"id": "table-pass-2", "text": "table 2", "metadata": {"has_table": True}},
    ]

    result = reranker.rerank("query", docs, top_k=2)

    assert [doc["id"] for doc in result] == ["text-pass", "table-pass-1"]
    assert reranker.last_stats["rerank_threshold_dropped_count"] == 1
    assert reranker.last_stats["rerank_passing_count"] == 3
