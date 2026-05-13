"""Unit tests for same-document cross-reference resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from retrieval.reference_resolver import ReferenceResolver, extract_references


DOC_ID = "6a034e61506cdfd33a4f9b0c"
SOURCE = "Quy định Học bổng Trần Đại Nghĩa 2025.pdf"


@dataclass
class _FakePoint:
    id: str
    payload: Dict[str, Any]


class _FakeClient:
    def __init__(self, points: List[_FakePoint]) -> None:
        self.points = points
        self.scroll_calls: list[dict[str, Any]] = []

    def scroll(
        self,
        *,
        collection_name: str,
        scroll_filter: Any,
        limit: int,
        offset: Any = None,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> tuple[list[_FakePoint], Any]:
        self.scroll_calls.append(
            {
                "collection_name": collection_name,
                "scroll_filter": scroll_filter,
                "limit": limit,
                "offset": offset,
                "with_payload": with_payload,
                "with_vectors": with_vectors,
            }
        )
        wanted_doc = self._document_id_from_filter(scroll_filter)
        filtered = [
            point
            for point in self.points
            if point.payload.get("document_id") == wanted_doc
        ]
        start = int(offset or 0)
        end = min(start + limit, len(filtered))
        next_offset = end if end < len(filtered) else None
        return filtered[start:end], next_offset

    @staticmethod
    def _document_id_from_filter(scroll_filter: Any) -> str | None:
        for condition in getattr(scroll_filter, "must", []) or []:
            if getattr(condition, "key", None) != "document_id":
                continue
            match = getattr(condition, "match", None)
            return getattr(match, "value", None)
        return None


class _FakeStore:
    def __init__(self, points: List[_FakePoint]) -> None:
        self.collection_name = "quydinh"
        self.client = _FakeClient(points)


class _FakeSearcher:
    def __init__(self, store: _FakeStore | None = None) -> None:
        self.qdrant_stores = {"quydinh": store} if store is not None else {}


class _FakeService:
    def __init__(
        self,
        *,
        points: List[_FakePoint] | None = None,
        search_results: List[Dict[str, Any]] | None = None,
    ) -> None:
        self.searcher = _FakeSearcher(_FakeStore(points or [])) if points is not None else _FakeSearcher()
        self.search_results = search_results or []
        self.search_calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> List[Dict[str, Any]]:
        self.search_calls.append(kwargs)
        return list(self.search_results)


def _metadata(**overrides: Any) -> Dict[str, Any]:
    metadata = {
        "document_id": DOC_ID,
        "source": SOURCE,
        "filename": SOURCE,
        "collection": "quydinh",
        "level": "child",
        "chunk_type": "text",
    }
    metadata.update(overrides)
    return metadata


def _article7_doc() -> Dict[str, Any]:
    return {
        "id": "quydinh/article-7",
        "text": (
            "### Điều 7. Mức Học bổng Trần Đại Nghĩa\n"
            "1. Đối tượng quy định tại khoản 1 và khoản 2 Điều 5: "
            "Học bổng có 2 mức tương ứng bằng 50% và 100% học phí.\n"
            "2. Đối tượng quy định tại khoản 3 và khoản 4 Điều 5: "
            "Học bổng có 2 mức tương ứng 5.000.000 đồng và 10.000.000 đồng."
        ),
        "metadata": _metadata(section_h3="Điều 7. Mức Học bổng Trần Đại Nghĩa", chunk_index=8),
        "collection": "quydinh",
    }


def _point(point_id: str, text: str, **metadata_overrides: Any) -> _FakePoint:
    payload = _metadata(**metadata_overrides)
    payload["text"] = text
    return _FakePoint(point_id, payload)


def test_extract_references_merges_clause_lists_by_article() -> None:
    refs = extract_references(
        "Đối tượng tại khoản 1 và khoản 2 Điều 5; xem Điều 7 khoản 3."
    )

    assert [ref["article"] for ref in refs] == [5, 7]
    assert refs[0]["clauses"] == [1, 2]
    assert refs[0]["clause"] == 1
    assert refs[1]["clauses"] == [3]


def test_metadata_lookup_resolves_all_split_article_chunks_in_chunk_order() -> None:
    points = [
        _point(
            "article-5-b",
            "### Điều 5. Tiêu chuẩn\n\n2. Sinh viên từ học kỳ 2.\n3. Sinh viên gặp rủi ro.\n4. Trường hợp đặc biệt.",
            section_h3="Điều 5. Tiêu chuẩn được đăng ký xét Học bổng Trần Đại Nghĩa",
            chunk_index=6,
        ),
        _point(
            "article-5-parent",
            "### Điều 5. Tiêu chuẩn\n1. Parent copy.\n### Điều 6. Nguyên tắc\n...",
            section_h3=None,
            level="parent",
            chunk_type="parent",
            chunk_index=4,
        ),
        _point(
            "article-5-a",
            "### Điều 5. Tiêu chuẩn\nSinh viên khó khăn.\n\n1. Sinh viên mới trúng tuyển.",
            section_h3="Điều 5. Tiêu chuẩn được đăng ký xét Học bổng Trần Đại Nghĩa",
            chunk_index=5,
        ),
        _point(
            "other-doc-article-5",
            "### Điều 5. Trách nhiệm của sinh viên\nNội dung từ văn bản khác.",
            document_id="other-doc",
            source="Quy chế sinh viên.pdf",
            filename="Quy chế sinh viên.pdf",
            section_h3="Điều 5. Trách nhiệm của sinh viên",
            chunk_index=10,
        ),
    ]
    service = _FakeService(points=points)
    resolver = ReferenceResolver(service, max_total_refs=5)

    resolved = resolver.resolve([_article7_doc()])

    assert [item["id"] for item in resolved] == [
        "quydinh/article-7",
        "quydinh/article-5-a",
        "quydinh/article-5-b",
    ]
    assert all(item.get("_cross_reference") for item in resolved[1:])
    assert service.search_calls == []


def test_dedup_handles_runtime_and_raw_qdrant_ids() -> None:
    existing_article_5 = {
        "id": "quydinh/article-5-a",
        "text": "### Điều 5. Tiêu chuẩn\n1. Sinh viên mới trúng tuyển.",
        "metadata": _metadata(
            section_h3="Điều 5. Tiêu chuẩn được đăng ký xét Học bổng Trần Đại Nghĩa",
            chunk_index=5,
        ),
        "collection": "quydinh",
    }
    points = [
        _point(
            "article-5-a",
            "### Điều 5. Tiêu chuẩn\n1. Sinh viên mới trúng tuyển.",
            section_h3="Điều 5. Tiêu chuẩn được đăng ký xét Học bổng Trần Đại Nghĩa",
            chunk_index=5,
        ),
        _point(
            "article-5-b",
            "### Điều 5. Tiêu chuẩn\n2. Sinh viên từ học kỳ 2.",
            section_h3="Điều 5. Tiêu chuẩn được đăng ký xét Học bổng Trần Đại Nghĩa",
            chunk_index=6,
        ),
    ]
    resolver = ReferenceResolver(_FakeService(points=points), max_total_refs=5)

    resolved = resolver.resolve([_article7_doc(), existing_article_5])

    ids = [item["id"] for item in resolved]
    assert ids.count("quydinh/article-5-a") == 1
    assert ids.count("quydinh/article-5-b") == 1


def test_fallback_search_filters_cross_document_results() -> None:
    wrong_doc = {
        "id": "quydinh/wrong",
        "text": "### Điều 5. Trách nhiệm của sinh viên\nKhông liên quan học bổng.",
        "metadata": _metadata(
            document_id="other-doc",
            source="Quy chế sinh viên.pdf",
            filename="Quy chế sinh viên.pdf",
            section_h3="Điều 5. Trách nhiệm của sinh viên",
            chunk_index=1,
        ),
        "collection": "quydinh",
        "rerank_score": 0.99,
    }
    correct_doc = {
        "id": "article-5-a",
        "text": "### Điều 5. Tiêu chuẩn\n1. Sinh viên mới trúng tuyển.",
        "metadata": _metadata(
            section_h3="Điều 5. Tiêu chuẩn được đăng ký xét Học bổng Trần Đại Nghĩa",
            chunk_index=5,
        ),
        "collection": "quydinh",
        "rerank_score": 0.1,
    }
    service = _FakeService(search_results=[wrong_doc, correct_doc])
    resolver = ReferenceResolver(service)

    resolved = resolver.resolve([_article7_doc()])

    assert [item["id"] for item in resolved] == [
        "quydinh/article-7",
        "quydinh/article-5-a",
    ]
    assert service.search_calls[0]["query"] == f"Điều 5 {SOURCE}"
    assert service.search_calls[0]["collections"] == ["quydinh"]


def test_fallback_does_not_append_when_only_cross_document_results_exist() -> None:
    wrong_doc = {
        "id": "quydinh/wrong",
        "text": "### Điều 5. Trách nhiệm của sinh viên\nKhông liên quan học bổng.",
        "metadata": _metadata(
            document_id="other-doc",
            source="Quy chế sinh viên.pdf",
            filename="Quy chế sinh viên.pdf",
            section_h3="Điều 5. Trách nhiệm của sinh viên",
        ),
        "collection": "quydinh",
    }
    resolver = ReferenceResolver(_FakeService(search_results=[wrong_doc]))

    resolved = resolver.resolve([_article7_doc()])

    assert resolved == [_article7_doc()]
