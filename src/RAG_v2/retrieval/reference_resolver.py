"""Cross-reference resolver for same-document legal references.

When a retrieved chunk says "khoản 1 Điều 5" or "xem thêm Điều 12",
this module fetches the referenced article chunks and inserts them directly
after the chunk that mentioned them.  Same-document metadata lookup is tried
first so short references such as "Điều 5" do not drift to another document
with a better semantic score.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_ARTICLE_WORD = r"(?:Điều|điều)"
_CLAUSE_WORD = r"(?:Khoản|khoản)"
_REFERENCE_PREFIX = (
    r"(?:(?:theo|xem|tại|căn cứ|quy định tại|nêu tại)\s+)?"
)

# "khoản 1 và khoản 2 Điều 5", "khoản 3, khoản 4 Điều 5"
_CLAUSE_FIRST_RE = re.compile(
    _REFERENCE_PREFIX
    + rf"(?P<clauses>{_CLAUSE_WORD}\s+\d+"
    + rf"(?:\s*(?:,|và|hoặc)\s*(?:{_CLAUSE_WORD}\s+)?\d+)*)"
    + rf"\s+(?:của\s+)?{_ARTICLE_WORD}\s+(?P<article>\d+)",
    re.UNICODE,
)

# "Điều 5", "Điều 5 khoản 2", "Điều 5 khoản 1 và khoản 2"
_ARTICLE_FIRST_RE = re.compile(
    _REFERENCE_PREFIX
    + rf"{_ARTICLE_WORD}\s+(?P<article>\d+)"
    + rf"(?:\s+(?P<clauses>{_CLAUSE_WORD}\s+\d+"
    + rf"(?:\s*(?:,|và|hoặc)\s*(?:{_CLAUSE_WORD}\s+)?\d+)*))?",
    re.UNICODE,
)

_CLAUSE_NUMBER_RE = re.compile(r"\d+", re.UNICODE)
_ARTICLE_HEADING_RE = re.compile(
    rf"^\s*(?:#{{1,6}}\s*)?{_ARTICLE_WORD}\s+(?P<article>\d+)(?:\b|[.:])",
    re.IGNORECASE | re.MULTILINE | re.UNICODE,
)
_CLAUSE_LINE_RE_TEMPLATE = r"(?m)^\s*{clause}\.\s+"

_DEFAULT_SCROLL_PAGE_SIZE = 128
_DEFAULT_SCROLL_MAX_POINTS = 500


def _extract_clause_numbers(text: str | None) -> List[int]:
    if not text:
        return []
    return [int(value) for value in _CLAUSE_NUMBER_RE.findall(text)]


def _merge_reference(
    refs_by_article: Dict[int, Dict[str, Any]],
    *,
    article: int,
    clauses: Iterable[int],
    raw_match: str,
    start: int,
) -> None:
    cleaned_raw = " ".join(raw_match.split())
    existing = refs_by_article.get(article)
    if existing is None:
        clause_list = sorted(set(int(clause) for clause in clauses))
        refs_by_article[article] = {
            "article": article,
            "clause": clause_list[0] if clause_list else None,
            "clauses": clause_list,
            "raw_match": cleaned_raw,
            "_start": start,
        }
        return

    merged_clauses = sorted(
        set(existing.get("clauses") or []) | {int(clause) for clause in clauses}
    )
    existing["clauses"] = merged_clauses
    existing["clause"] = merged_clauses[0] if merged_clauses else None
    existing["_start"] = min(int(existing.get("_start", start)), start)
    if cleaned_raw and cleaned_raw not in str(existing.get("raw_match", "")):
        existing["raw_match"] = f"{existing['raw_match']}; {cleaned_raw}"


def extract_references(text: str) -> List[Dict[str, Any]]:
    """Extract Vietnamese legal article references from a text chunk.

    Returns one item per referenced article.  If the same article is mentioned
    multiple times with different clauses, clause numbers are merged into the
    ``clauses`` list while the legacy ``clause`` key remains as the first
    clause for backwards compatibility.
    """
    refs_by_article: Dict[int, Dict[str, Any]] = {}

    for match in _CLAUSE_FIRST_RE.finditer(text or ""):
        article = int(match.group("article"))
        _merge_reference(
            refs_by_article,
            article=article,
            clauses=_extract_clause_numbers(match.group("clauses")),
            raw_match=match.group(0),
            start=match.start(),
        )

    for match in _ARTICLE_FIRST_RE.finditer(text or ""):
        article = int(match.group("article"))
        _merge_reference(
            refs_by_article,
            article=article,
            clauses=_extract_clause_numbers(match.group("clauses")),
            raw_match=match.group(0),
            start=match.start(),
        )

    refs = sorted(refs_by_article.values(), key=lambda item: int(item["_start"]))
    for ref in refs:
        ref.pop("_start", None)
    return refs


def _as_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata = item.get("metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _item_collection(item: Dict[str, Any]) -> str:
    metadata = _as_metadata(item)
    return str(item.get("collection") or metadata.get("collection") or "")


def _raw_id(result_id: Any) -> str:
    value = str(result_id or "").strip()
    if "/" in value:
        return value.split("/", 1)[1]
    return value


def _runtime_id(result_id: Any, collection: str) -> str:
    raw = _raw_id(result_id)
    if not raw:
        return ""
    return f"{collection}/{raw}" if collection else raw


def _dedup_keys(item: Dict[str, Any]) -> Set[str]:
    result_id = str(item.get("id") or "").strip()
    if not result_id:
        return set()
    keys = {result_id}
    raw = _raw_id(result_id)
    if raw:
        keys.add(raw)
    collection = _item_collection(item)
    if collection and raw:
        keys.add(f"{collection}/{raw}")
    return keys


def _text_key(item: Dict[str, Any]) -> str:
    text = str(item.get("text") or item.get("content") or "")
    return text[:200]


def _article_from_heading(text: str | None) -> Optional[int]:
    if not text:
        return None
    match = _ARTICLE_HEADING_RE.search(str(text))
    if not match:
        return None
    return int(match.group("article"))


def _current_article(item: Dict[str, Any]) -> Optional[int]:
    metadata = _as_metadata(item)
    return (
        _article_from_heading(str(metadata.get("section_h3") or ""))
        or _article_from_heading(str(item.get("text") or item.get("content") or ""))
    )


def _matches_article_heading(item: Dict[str, Any], article: int) -> bool:
    metadata = _as_metadata(item)
    section_h3 = str(metadata.get("section_h3") or "")
    if _article_from_heading(section_h3) == article:
        return True

    text = str(item.get("text") or item.get("content") or "")
    for match in _ARTICLE_HEADING_RE.finditer(text):
        if int(match.group("article")) == article:
            return True
    return False


def _chunk_index(item: Dict[str, Any]) -> int:
    value = _as_metadata(item).get("chunk_index")
    try:
        return int(value)
    except (TypeError, ValueError):
        return 10**9


def _is_parent_chunk(item: Dict[str, Any]) -> bool:
    metadata = _as_metadata(item)
    return (
        str(metadata.get("chunk_type") or "").lower() == "parent"
        or str(metadata.get("level") or "").lower() == "parent"
    )


def _chunk_contains_clause(item: Dict[str, Any], clause: int) -> bool:
    text = str(item.get("text") or item.get("content") or "")
    if re.search(_CLAUSE_LINE_RE_TEMPLATE.format(clause=clause), text):
        return True
    return bool(re.search(rf"\bkhoản\s+{clause}\b", text, re.IGNORECASE))


def _sort_reference_items(
    items: List[Dict[str, Any]],
    clauses: List[int],
) -> List[Dict[str, Any]]:
    if not items:
        return []

    non_parent = [item for item in items if not _is_parent_chunk(item)]
    if non_parent:
        items = non_parent

    def sort_key(item: Dict[str, Any]) -> Tuple[int, int]:
        clause_rank = 0
        if clauses and not any(_chunk_contains_clause(item, clause) for clause in clauses):
            clause_rank = 1
        return clause_rank, _chunk_index(item)

    return sorted(items, key=sort_key)


class ReferenceResolver:
    """Fetch referenced articles/clauses and add them to context."""

    def __init__(
        self,
        retrieval_service: Any = None,
        *,
        max_refs_per_chunk: int = 2,
        max_total_refs: int = 3,
        scroll_page_size: int = _DEFAULT_SCROLL_PAGE_SIZE,
        scroll_max_points: int = _DEFAULT_SCROLL_MAX_POINTS,
    ) -> None:
        self._service = retrieval_service
        self._max_refs_per_chunk = max_refs_per_chunk
        self._max_total_refs = max_total_refs
        self._scroll_page_size = scroll_page_size
        self._scroll_max_points = scroll_max_points

    def resolve(
        self,
        results: List[Dict[str, Any]],
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """Scan results for cross-references and insert resolved chunks."""
        if not results or self._service is None:
            return results

        enriched: List[Dict[str, Any]] = []
        existing_ids: Set[str] = set()
        existing_texts: Set[str] = set()

        for item in results:
            if not isinstance(item, dict):
                continue
            existing_ids.update(_dedup_keys(item))
            existing_texts.add(_text_key(item))

        total_added = 0
        for item in results:
            enriched.append(item)
            if not isinstance(item, dict):
                continue

            text = str(item.get("text") or item.get("content") or "")
            refs = extract_references(text)
            if not refs:
                continue

            metadata = _as_metadata(item)
            collection = _item_collection(item)
            source = str(
                item.get("source")
                or metadata.get("source")
                or metadata.get("filename")
                or ""
            )
            current_article = _current_article(item)
            refs_resolved_for_chunk = 0

            logger.info(
                "Cross-references found in chunk (source=%s): %s",
                source[:40],
                [ref["raw_match"] for ref in refs[:5]],
            )

            for ref in refs:
                if total_added >= self._max_total_refs:
                    break
                if refs_resolved_for_chunk >= self._max_refs_per_chunk:
                    break
                if current_article == ref["article"]:
                    continue

                ref_items = self._resolve_one_reference(item, ref)
                refs_resolved_for_chunk += 1

                for ref_item in ref_items:
                    if total_added >= self._max_total_refs:
                        break

                    item_id_keys = _dedup_keys(ref_item)
                    text_key = _text_key(ref_item)
                    if item_id_keys & existing_ids:
                        continue
                    if not item_id_keys and text_key in existing_texts:
                        continue

                    enriched.append(ref_item)
                    existing_ids.update(item_id_keys)
                    existing_texts.add(text_key)
                    total_added += 1
                    logger.info(
                        "Resolved cross-reference: %s (from %s)",
                        ref["raw_match"],
                        source[:40],
                    )

        if total_added:
            logger.info(
                "Cross-reference resolver: added %d referenced chunks.",
                total_added,
            )
        return enriched

    def _resolve_one_reference(
        self,
        source_item: Dict[str, Any],
        ref: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        metadata = _as_metadata(source_item)
        collection = _item_collection(source_item)
        document_id = str(metadata.get("document_id") or "")
        source = str(metadata.get("source") or source_item.get("source") or "")
        filename = str(metadata.get("filename") or "")

        ref_items = self._lookup_by_metadata(
            collection=collection,
            document_id=document_id,
            ref=ref,
            source=source,
        )
        if ref_items:
            return ref_items

        return self._lookup_by_search(
            collection=collection,
            document_id=document_id,
            source=source,
            filename=filename,
            ref=ref,
        )

    def _lookup_by_metadata(
        self,
        *,
        collection: str,
        document_id: str,
        ref: Dict[str, Any],
        source: str,
    ) -> List[Dict[str, Any]]:
        if not collection or not document_id:
            return []

        store = self._qdrant_store(collection)
        if store is None:
            return []

        try:
            from qdrant_client import models as qmodels
        except Exception:
            logger.debug("qdrant_client models unavailable for reference lookup")
            return []

        scroll_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=document_id),
                )
            ]
        )

        matched: List[Dict[str, Any]] = []
        offset: Any = None
        scanned = 0
        try:
            while scanned < self._scroll_max_points:
                limit = min(self._scroll_page_size, self._scroll_max_points - scanned)
                points, next_offset = store.client.scroll(
                    collection_name=store.collection_name,
                    scroll_filter=scroll_filter,
                    limit=limit,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                scanned += len(points)

                for point in points:
                    item = self._point_to_item(point, collection)
                    if _matches_article_heading(item, int(ref["article"])):
                        matched.append(item)

                if not points or next_offset is None:
                    break
                offset = next_offset
        except Exception:
            logger.debug(
                "Metadata reference lookup failed for %s Điều %s",
                collection,
                ref.get("article"),
                exc_info=True,
            )
            return []

        matched = _sort_reference_items(matched, list(ref.get("clauses") or []))
        return [
            self._mark_cross_reference(item, ref, collection=collection, source=source)
            for item in matched
        ]

    def _lookup_by_search(
        self,
        *,
        collection: str,
        document_id: str,
        source: str,
        filename: str,
        ref: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        context_name = filename or source
        ref_query = f"Điều {ref['article']}"
        if context_name:
            ref_query = f"{ref_query} {context_name}"

        try:
            ref_results = self._service.search(
                query=ref_query,
                collections=[collection] if collection else None,
                top_k=max(self._max_total_refs * 2, 4),
                rerank=True,
            )
        except Exception:
            logger.debug(
                "Semantic fallback failed for reference %s",
                ref.get("raw_match"),
                exc_info=True,
            )
            return []

        filtered: List[Dict[str, Any]] = []
        for item in ref_results:
            if not isinstance(item, dict):
                continue
            if not self._same_document(
                item,
                document_id=document_id,
                source=source,
                filename=filename,
            ):
                continue
            if not _matches_article_heading(item, int(ref["article"])):
                continue
            filtered.append(
                self._mark_cross_reference(
                    dict(item),
                    ref,
                    collection=collection or _item_collection(item),
                    source=source,
                )
            )

        return _sort_reference_items(filtered, list(ref.get("clauses") or []))

    def _qdrant_store(self, collection: str) -> Any | None:
        searcher = getattr(self._service, "searcher", None)
        qdrant_stores = getattr(searcher, "qdrant_stores", None)
        if callable(qdrant_stores):
            qdrant_stores = qdrant_stores()
        if not isinstance(qdrant_stores, dict):
            return None
        return qdrant_stores.get(collection)

    @staticmethod
    def _point_to_item(point: Any, collection: str) -> Dict[str, Any]:
        payload = dict(getattr(point, "payload", None) or {})
        text = payload.pop("text", "")
        raw_point_id = str(getattr(point, "id", "") or "")
        payload.setdefault("collection", collection)
        return {
            "id": _runtime_id(raw_point_id, collection),
            "text": text,
            "metadata": payload,
            "collection": collection,
            "score": 0.0,
        }

    @staticmethod
    def _same_document(
        item: Dict[str, Any],
        *,
        document_id: str,
        source: str,
        filename: str,
    ) -> bool:
        metadata = _as_metadata(item)
        candidate_document_id = str(metadata.get("document_id") or "")
        if document_id:
            return candidate_document_id == document_id

        expected_names = {value for value in (source, filename) if value}
        if not expected_names:
            return False
        candidate_names = {
            str(metadata.get("source") or ""),
            str(metadata.get("filename") or ""),
            str(item.get("source") or ""),
        }
        return bool(expected_names & candidate_names)

    @staticmethod
    def _mark_cross_reference(
        item: Dict[str, Any],
        ref: Dict[str, Any],
        *,
        collection: str,
        source: str,
    ) -> Dict[str, Any]:
        metadata = dict(_as_metadata(item))
        item["metadata"] = metadata
        resolved_collection = collection or _item_collection(item)
        if resolved_collection:
            item["collection"] = resolved_collection
            item["id"] = _runtime_id(item.get("id"), resolved_collection)
            metadata.setdefault("collection", resolved_collection)
        item["_cross_reference"] = True
        item["_referenced_from"] = source[:60]
        item["_reference"] = ref.get("raw_match")
        return item
