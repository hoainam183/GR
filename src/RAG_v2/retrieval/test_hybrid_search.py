"""Quick test for HybridSearch RRF fusion logic (no live services needed)."""

import sys

sys.path.insert(0, "..")

from retrieval.hybrid_search import HybridSearch, rrf_score


def test_rrf_score():
    """Basic sanity checks for the RRF formula."""
    assert rrf_score(1, 60) == 1.0 / 61
    assert rrf_score(2, 60) == 1.0 / 62
    assert rrf_score(1, 60) > rrf_score(2, 60)
    print("[PASS] test_rrf_score")


def test_rrf_fusion():
    """Test fusion with mock vector + keyword results."""
    # Build a HybridSearch without connecting to real services
    hs = object.__new__(HybridSearch)
    hs.rrf_k = 60
    hs.vector_weight = 1.0
    hs.keyword_weight = 1.0

    vector_results = [
        {
            "id": "doc1",
            "text": "Text A",
            "metadata": {"src": "a"},
            "score": 0.95,
        },
        {
            "id": "doc2",
            "text": "Text B",
            "metadata": {"src": "b"},
            "score": 0.90,
        },
        {
            "id": "doc3",
            "text": "Text C",
            "metadata": {"src": "c"},
            "score": 0.80,
        },
    ]

    keyword_results = [
        {
            "id": "doc2",
            "text": "Text B",
            "metadata": {"src": "b"},
            "score": 8.5,
        },
        {
            "id": "doc4",
            "text": "Text D",
            "metadata": {"src": "d"},
            "score": 7.0,
        },
        {
            "id": "doc1",
            "text": "Text A",
            "metadata": {"src": "a"},
            "score": 5.0,
        },
    ]

    fused = hs._rrf_fuse(vector_results, keyword_results)

    # Should have 4 unique docs (doc1, doc2, doc3, doc4)
    assert len(fused) == 4, f"Expected 4 docs, got {len(fused)}"

    # doc1: vector rank 1, keyword rank 3 → rrf = 1/61 + 1/63
    # doc2: vector rank 2, keyword rank 1 → rrf = 1/62 + 1/61
    # doc2 should rank higher because 1/62 + 1/61 > 1/61 + 1/63
    expected_doc2_score = 1.0 / 62 + 1.0 / 61
    expected_doc1_score = 1.0 / 61 + 1.0 / 63
    assert expected_doc2_score > expected_doc1_score

    assert (
        fused[0]["id"] == "doc2"
    ), f"Expected doc2 first, got {fused[0]['id']}"
    assert (
        fused[1]["id"] == "doc1"
    ), f"Expected doc1 second, got {fused[1]['id']}"

    # doc3 only in vector (rank 3), doc4 only in keyword (rank 2)
    # doc4: keyword rank 2 → rrf = 1/62
    # doc3: vector rank 3 → rrf = 1/63
    # doc4 > doc3
    assert (
        fused[2]["id"] == "doc4"
    ), f"Expected doc4 third, got {fused[2]['id']}"
    assert (
        fused[3]["id"] == "doc3"
    ), f"Expected doc3 fourth, got {fused[3]['id']}"

    # Check scores are populated
    assert fused[0]["vector_rank"] == 2
    assert fused[0]["keyword_rank"] == 1
    assert fused[0]["score"] > 0

    print("[PASS] test_rrf_fusion")


def test_rrf_fusion_weights():
    """Test that weights correctly scale the RRF components."""
    hs = object.__new__(HybridSearch)
    hs.rrf_k = 60
    hs.vector_weight = 2.0
    hs.keyword_weight = 0.5

    vector_results = [
        {"id": "doc1", "text": "A", "metadata": {}, "score": 0.9},
    ]
    keyword_results = [
        {"id": "doc1", "text": "A", "metadata": {}, "score": 5.0},
    ]

    fused = hs._rrf_fuse(vector_results, keyword_results)
    expected = 2.0 * (1.0 / 61) + 0.5 * (1.0 / 61)
    assert (
        abs(fused[0]["score"] - expected) < 1e-10
    ), f"Expected {expected}, got {fused[0]['score']}"
    print("[PASS] test_rrf_fusion_weights")


def test_empty_results():
    """Fusion with one or both empty result lists."""
    hs = object.__new__(HybridSearch)
    hs.rrf_k = 60
    hs.vector_weight = 1.0
    hs.keyword_weight = 1.0

    # Both empty
    assert hs._rrf_fuse([], []) == []

    # One empty
    vector_results = [
        {"id": "doc1", "text": "A", "metadata": {}, "score": 0.9},
    ]
    fused = hs._rrf_fuse(vector_results, [])
    assert len(fused) == 1
    assert fused[0]["keyword_rrf"] == 0.0

    fused = hs._rrf_fuse([], vector_results)
    assert len(fused) == 1
    assert fused[0]["vector_rrf"] == 0.0

    print("[PASS] test_empty_results")


if __name__ == "__main__":
    test_rrf_score()
    test_rrf_fusion()
    test_rrf_fusion_weights()
    test_empty_results()
    print("\n✅ All hybrid search tests passed!")
