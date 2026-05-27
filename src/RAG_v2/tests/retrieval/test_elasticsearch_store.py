"""Quick integration test for ElasticsearchStore.

Requires:
  - Elasticsearch running on localhost:9200
  - pip install elasticsearch
"""

from __future__ import annotations

import json

import retrieval.elasticsearch_store as es_module
from retrieval.elasticsearch_store import ElasticsearchStore, INDEX_SETTINGS

TEST_INDEX = "test_university_docs"


class _FakeESClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.indices = _FakeIndices()

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        return {"hits": {"hits": []}}


class _FakeIndices:
    def __init__(self):
        self.refresh_calls = []

    def refresh(self, **kwargs):
        self.refresh_calls.append(kwargs)


def _make_store_with_client(client: _FakeESClient) -> ElasticsearchStore:
    store = ElasticsearchStore.__new__(ElasticsearchStore)
    store.index_name = "unit-test"
    store.client = client
    return store


def test_index_mapping_declares_applicable_cohort_keyword() -> None:
    settings = ElasticsearchStore._make_settings(use_icu=False)
    properties = settings["mappings"]["properties"]

    assert properties["applicable_cohort"]["type"] == "keyword"
    assert (
        INDEX_SETTINGS["mappings"]["properties"]["applicable_cohort"]["type"]
        == "keyword"
    )


def test_index_mapping_uses_vi_tokenizer_and_search_text() -> None:
    settings = ElasticsearchStore._make_settings(use_icu=True)
    analysis = settings["settings"]["analysis"]
    analyzer = analysis["analyzer"]["vietnamese_analyzer"]
    filters = analysis["filter"]
    properties = settings["mappings"]["properties"]

    assert analyzer["tokenizer"] == "vi_tokenizer"
    assert "vietnamese_ascii_folding" in analyzer["filter"]
    assert filters["vietnamese_ascii_folding"]["type"] == "asciifolding"
    assert filters["vietnamese_ascii_folding"]["preserve_original"] is True
    assert properties["search_text"]["analyzer"] == "vietnamese_analyzer"
    assert properties["search_text"]["similarity"] == "custom_bm25"
    assert properties["level"]["type"] == "keyword"
    assert properties["chunk_id"]["type"] == "keyword"
    assert properties["readable_id"]["type"] == "keyword"
    assert properties["parent_id"]["type"] == "keyword"
    assert properties["collection"]["type"] == "keyword"
    assert properties["source_file"]["type"] == "keyword"


def test_index_mapping_fallback_uses_standard_tokenizer() -> None:
    settings = ElasticsearchStore._make_settings(use_icu=False)
    analyzer = settings["settings"]["analysis"]["analyzer"]["vietnamese_analyzer"]

    assert analyzer["tokenizer"] == "standard"
    assert "vietnamese_ascii_folding" in analyzer["filter"]


def test_index_documents_builds_search_text_and_chunk_id(monkeypatch) -> None:
    captured_actions = []

    def fake_bulk(client, actions, raise_on_error=False):
        captured_actions.extend(actions)
        return len(actions), []

    monkeypatch.setattr(es_module.helpers, "bulk", fake_bulk)
    client = _FakeESClient([])
    store = _make_store_with_client(client)

    indexed = store.index_documents(
        texts=["### Điều kiện tốt nghiệp\n| Tín chỉ | 120 |"],
        metadatas=[
            {
                "title": "Quy chế đào tạo",
                "doc_title": "Quy chế 2025",
                "hierarchy_path": "Chương II / Điều 13",
                "applicable_cohort": ["K70"],
                "level": "child",
            }
        ],
        ids=["chunk-1"],
    )

    source = captured_actions[0]["_source"]
    assert indexed == 1
    assert captured_actions[0]["_id"] == "chunk-1"
    assert source["chunk_id"] == "chunk-1"
    assert "search_text" in source
    assert "Điều kiện tốt nghiệp" in source["search_text"]
    assert "Quy chế đào tạo" in source["search_text"]
    assert "K70" in source["search_text"]
    assert "|" not in source["search_text"]


def test_keyword_search_exact_phrase_and_table_boost_without_fuzzy_main() -> None:
    client = _FakeESClient(
        [
            {
                "hits": {
                    "hits": [
                        {
                            "_id": "df79f3f4-5445-4da1-aa34-c59a81784319",
                            "_score": 42.0,
                            "_source": {
                                "text": "Tham gia hiến máu nhân đạo được 6 điểm.",
                                "title": "Khung đánh giá điểm rèn luyện",
                                "has_table": True,
                            },
                        }
                    ]
                }
            }
        ]
    )
    store = _make_store_with_client(client)

    results = store.keyword_search("hiến máu được bao nhiêu điểm rèn luyện", top_k=5)

    assert len(client.calls) == 1
    first_query = json.dumps(client.calls[0]["query"], ensure_ascii=False)
    assert '"fuzziness": "AUTO"' not in first_query
    assert '"match_phrase"' in first_query
    assert '"has_table"' in first_query
    assert results[0]["id"] == "df79f3f4-5445-4da1-aa34-c59a81784319"
    assert results[0]["metadata"]["_keyword_table_lookup_hit"] is True


def test_keyword_search_uses_fuzzy_only_as_fallback() -> None:
    client = _FakeESClient(
        [
            {"hits": {"hits": []}},
            {
                "hits": {
                    "hits": [
                        {
                            "_id": "fallback",
                            "_score": 3.0,
                            "_source": {
                                "text": "Điểm rèn luyện sinh viên",
                                "title": "Quy định",
                                "has_table": False,
                            },
                        }
                    ]
                }
            },
        ]
    )
    store = _make_store_with_client(client)

    results = store.keyword_search("diem ren luyen", top_k=5)

    assert len(client.calls) == 2
    first_query = json.dumps(client.calls[0]["query"], ensure_ascii=False)
    second_query = json.dumps(client.calls[1]["query"], ensure_ascii=False)
    assert '"fuzziness": "AUTO"' not in first_query
    assert '"fuzziness": "AUTO"' in second_query
    assert results[0]["metadata"]["_keyword_search_mode"] == "fuzzy_fallback"


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
