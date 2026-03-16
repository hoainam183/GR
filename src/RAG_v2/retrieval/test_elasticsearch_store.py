"""Quick integration test for ElasticsearchStore.

Requires:
  - Elasticsearch running on localhost:9200
  - pip install elasticsearch
"""

from elasticsearch_store import ElasticsearchStore

TEST_INDEX = "test_university_docs"


def main() -> None:
    # 1. Connect and create index
    store = ElasticsearchStore(index_name=TEST_INDEX)
    print(f"[OK] Connected. Index: {TEST_INDEX}")

    # 2. Index sample documents
    texts = [
        "Sinh viên phải hoàn thành tối thiểu 150 tín chỉ để tốt nghiệp chương trình đại học.",
        "Học bổng khuyến khích học tập được xét theo từng học kỳ dựa trên điểm trung bình tích lũy.",
        "Quy chế đánh giá điểm rèn luyện sinh viên được ban hành theo quyết định số 1234/QĐ-ĐHBK.",
        "Sinh viên được phép đăng ký tối đa 25 tín chỉ mỗi học kỳ nếu điểm trung bình trên 3.2.",
        "Chương trình đào tạo kỹ sư chất lượng cao yêu cầu thực tập doanh nghiệp 6 tháng.",
    ]
    metadatas = [
        {"doc_id": 1, "title": "Quy chế đào tạo", "type_doc": "QuyDinh"},
        {"doc_id": 2, "title": "Quy định học bổng", "type_doc": "QuyDinh"},
        {"doc_id": 3, "title": "Điểm rèn luyện", "type_doc": "QuyDinh"},
        {"doc_id": 4, "title": "Quy chế đào tạo", "type_doc": "QuyDinh"},
        {"doc_id": 5, "title": "Chương trình CLCQ", "type_doc": "CTDT"},
    ]
    ids = ["chunk_1", "chunk_2", "chunk_3", "chunk_4", "chunk_5"]

    indexed = store.index_documents(texts, metadatas, ids)
    print(f"[OK] Indexed {indexed} documents")

    # 3. Count
    count = store.count()
    print(f"[OK] Document count: {count}")
    assert count == 5, f"Expected 5, got {count}"

    # 4. Keyword search
    results = store.keyword_search("tín chỉ tốt nghiệp", top_k=3)
    print(f"\n[Search] Query: 'tín chỉ tốt nghiệp' → {len(results)} results")
    for r in results:
        print(
            f"  score={r['score']:.4f}  id={r['id']}  text={r['text'][:80]}..."
        )

    assert len(results) > 0, "Expected at least 1 result"

    # 5. Search with filter
    results_filtered = store.keyword_search(
        "tín chỉ",
        top_k=5,
        filters={"term": {"type_doc": "CTDT"}},
    )
    print(f"\n[Search+Filter] type_doc=CTDT → {len(results_filtered)} results")
    for r in results_filtered:
        assert r["metadata"].get("type_doc") == "CTDT", "Filter failed!"
        print(f"  score={r['score']:.4f}  text={r['text'][:80]}...")

    # 6. Delete by metadata
    deleted = store.delete_by_metadata("type_doc", "CTDT")
    print(f"\n[OK] Deleted {deleted} docs with type_doc=CTDT")
    assert store.count() == 4, f"Expected 4, got {store.count()}"

    # 7. Cleanup
    store.delete_index()
    print(f"[OK] Deleted test index '{TEST_INDEX}'")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    main()
