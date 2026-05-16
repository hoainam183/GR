from __future__ import annotations

from retrieval.multi_collection_search import MultiCollectionSearch


def _searcher() -> MultiCollectionSearch:
    searcher = object.__new__(MultiCollectionSearch)
    searcher.rrf_k = 60
    return searcher


def test_score_fusion_rrf_prefers_docs_seen_by_both_channels() -> None:
    searcher = _searcher()
    vector_pool = [
        {"id": "doc1", "text": "A", "metadata": {}, "score": 0.90},
        {"id": "doc2", "text": "B", "metadata": {}, "score": 0.80},
    ]
    keyword_pool = [
        {"id": "doc2", "text": "B", "metadata": {}, "score": 10.0},
        {"id": "doc3", "text": "C", "metadata": {}, "score": 9.0},
    ]

    results = searcher._score_fusion_rrf(
        vector_pool,
        keyword_pool,
        top_k=3,
        vector_weight=1.0,
        keyword_weight=1.0,
    )

    assert [row["id"] for row in results] == ["doc2", "doc1", "doc3"]
    assert results[0]["vector_rank"] == 2
    assert results[0]["keyword_rank"] == 1


def test_filter_excluded_results_checks_text_and_metadata() -> None:
    rows = [
        {
            "id": "keep",
            "text": "Quy định học phí nghiên cứu sinh",
            "metadata": {},
            "score": 1.0,
        },
        {
            "id": "drop_text",
            "text": "Học phần bổ sung không nằm trong học phí",
            "metadata": {},
            "score": 0.9,
        },
        {
            "id": "drop_meta",
            "text": "Thông tin chung",
            "metadata": {"course_name": "Đồ án tốt nghiệp"},
            "score": 0.8,
        },
    ]

    filtered = MultiCollectionSearch._filter_excluded_results(
        rows,
        ["hoc phan bo sung", "do an tot nghiep"],
    )

    assert [row["id"] for row in filtered] == ["keep"]
