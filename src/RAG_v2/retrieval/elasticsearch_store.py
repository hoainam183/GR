"""Elasticsearch BM25 Store — keyword search with Vietnamese-friendly analysis."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from elasticsearch import Elasticsearch, helpers

from query.signals import analyze_query_signals, extract_key_phrases, fold_vietnamese_text
from query.structured_query import build_es_must_not_clauses

logger = logging.getLogger(__name__)

DEFAULT_INDEX = "stsv"

_KEYWORD_SEARCH_FIELDS = [
    "search_text^3.0",
    "title^2.0",
    "doc_title^1.8",
    "text^1.6",
    "hierarchy_path^1.5",
    "section_h1^1.4",
    "section_h2^1.4",
    "section_h3^1.3",
    "section_h4^1.1",
    "course_name^1.4",
    "major_name^1.2",
    "semester^1.2",
    "section_context^1.0",
    "item_label^1.0",
]

_GENERIC_POLICY_PHRASES = {
    "diem ren luyen",
    "diem ren",
    "ren luyen",
    "tin chi",
    "hoc phi",
    "dieu kien",
    "tot nghiep",
    "hoc bong",
    "quy dinh",
}


def _is_generic_policy_phrase(phrase: str) -> bool:
    return fold_vietnamese_text(phrase) in _GENERIC_POLICY_PHRASES


VIETNAMESE_SYNONYMS = [
    "CTDT,ctdt,chương trình đào tạo",
    "STSV,stsv,sổ tay sinh viên",
    "CNTT,cntt,công nghệ thông tin",
    "SV,sv,sinh viên",
    "GV,gv,giảng viên",
    "ĐHBK,đhbk,đại học bách khoa hà nội",
    "HUST,hust,đại học bách khoa hà nội",
    "HP,hp,học phần",
    "TC,tc,tín chỉ,tin chi",
    "GPA,gpa,điểm trung bình tích lũy,diem trung binh tich luy",
    "NCKH,nckh,nghiên cứu khoa học",
    "KLTN,kltn,khóa luận tốt nghiệp,khoa luan tot nghiep",
    "ĐATN,đatn,datn,đồ án tốt nghiệp,do an tot nghiep",
    "HK,hk,học kỳ,hoc ky",
    "NH,nh,năm học,nam hoc",
    "ĐRL,đrl,drl,điểm rèn luyện,diem ren luyen",
    "TBCTL,tbctl,trung bình chung tích lũy,trung binh chung tich luy",
    "TBC,tbc,trung bình chung,trung binh chung",
]

VIETNAMESE_STOPWORDS = [
    "và", "hoặc", "của", "trong", "là", "có", "được", "cho",
    "với", "về", "từ", "theo", "đến", "các", "những", "một",
    "này", "đó", "khi", "nếu", "thì", "để", "do", "bởi",
    "vì", "như", "tại", "bằng", "qua", "trên", "dưới",
]

_SEARCH_TEXT_METADATA_FIELDS = (
    "title",
    "doc_title",
    "hierarchy_path",
    "section_context",
    "section_h1",
    "section_h2",
    "section_h3",
    "section_h4",
    "item_label",
    "course_code",
    "course_name",
    "semester",
    "major_code",
    "major_name",
    "applicable_cohort",
    "applicable_major",
    "document_type",
    "type_doc",
    "readable_id",
    "source_file",
)

_MARKDOWN_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_MARKDOWN_LINK_RE = re.compile(r"!?(\[([^\]]*)\]\([^)]+\))")
_MARKDOWN_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MARKDOWN_DECORATION_RE = re.compile(r"[*_#>`~]+")
_MARKDOWN_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", re.MULTILINE)
_WHITESPACE_RE = re.compile(r"\s+")


def _text_field(analyzer: str, *, keyword: bool = False) -> Dict[str, Any]:
    field: Dict[str, Any] = {
        "type": "text",
        "analyzer": analyzer,
        "search_analyzer": analyzer,
        "similarity": "custom_bm25",
    }
    if keyword:
        field["fields"] = {"keyword": {"type": "keyword"}}
    return field


def _build_index_settings(use_vietnamese_plugin: bool) -> Dict[str, Any]:
    """Build index settings for the CocCoc Vietnamese plugin or fallback mode."""
    tokenizer = "vi_tokenizer" if use_vietnamese_plugin else "standard"
    text_analyzer = "vietnamese_analyzer"

    filter_cfg = {
        "vietnamese_ascii_folding": {
            "type": "asciifolding",
            "preserve_original": True,
        },
        "vietnamese_synonym": {
            "type": "synonym",
            "synonyms": VIETNAMESE_SYNONYMS,
            "lenient": True,
        },
        "vietnamese_stop": {
            "type": "stop",
            "stopwords": VIETNAMESE_STOPWORDS,
        },
    }
    analyzer_cfg = {
        text_analyzer: {
            "type": "custom",
            "tokenizer": tokenizer,
            "filter": [
                "lowercase",
                "vietnamese_synonym",
                "vietnamese_stop",
                "vietnamese_ascii_folding",
            ],
        }
    }

    text_fields = {
        "search_text": _text_field(text_analyzer),
        "text": _text_field(text_analyzer),
        "title": _text_field(text_analyzer, keyword=True),
        "doc_title": _text_field(text_analyzer, keyword=True),
        "hierarchy_path": _text_field(text_analyzer, keyword=True),
        "section_context": _text_field(text_analyzer, keyword=True),
        "section_h1": _text_field(text_analyzer, keyword=True),
        "section_h2": _text_field(text_analyzer, keyword=True),
        "section_h3": _text_field(text_analyzer, keyword=True),
        "section_h4": _text_field(text_analyzer, keyword=True),
        "course_name": _text_field(text_analyzer, keyword=True),
        "semester": _text_field(text_analyzer, keyword=True),
        "major_name": _text_field(text_analyzer, keyword=True),
    }

    keyword_fields = {
        "type_doc": {"type": "keyword"},
        "time_create": {"type": "keyword"},
        "item_label": {"type": "keyword"},
        "major_code": {"type": "keyword"},
        "applicable_cohort": {"type": "keyword"},
        "applicable_major": {"type": "keyword"},
        "date_str": {"type": "keyword"},
        "document_type": {"type": "keyword"},
        "course_code": {"type": "keyword"},
        "level": {"type": "keyword"},
        "chunk_id": {"type": "keyword"},
        "readable_id": {"type": "keyword"},
        "parent_id": {"type": "keyword"},
        "collection": {"type": "keyword"},
        "source_file": {"type": "keyword"},
    }

    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": analyzer_cfg,
                "filter": filter_cfg,
            },
            "index": {
                "similarity": {
                    "custom_bm25": {
                        "type": "BM25",
                        "k1": 1.5,
                        "b": 0.5,
                    }
                }
            },
        },
        "mappings": {
            "properties": {
                **text_fields,
                **keyword_fields,
                "doc_id": {"type": "integer"},
                "chunk_index": {"type": "integer"},
                "total_chunks": {"type": "integer"},
                "chunk_size": {"type": "integer"},
                "has_links": {"type": "boolean"},
                "has_table": {"type": "boolean"},
            }
        },
    }


# Legacy constant for callers/tests that import INDEX_SETTINGS directly.
INDEX_SETTINGS = _build_index_settings(use_vietnamese_plugin=True)


class ElasticsearchStore:
    """Manages an Elasticsearch index for BM25 keyword search.

    Parameters:
        host: ES server hostname.
        port: ES REST port (default 9200).
        index_name: Name of the ES index to use.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        index_name: str = DEFAULT_INDEX,
    ) -> None:
        self.index_name = index_name
        self.client = Elasticsearch(
            hosts=[f"http://{host}:{port}"],
        )
        if not self.client.ping():
            raise ConnectionError(
                f"Cannot connect to Elasticsearch at {host}:{port}"
            )
        logger.info("Connected to Elasticsearch at %s:%d", host, port)
        self._ensure_index()

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _ensure_index(self) -> None:
        """Create the index with custom mapping if it does not exist."""
        if self.client.indices.exists(index=self.index_name):
            logger.info("Index '%s' already exists.", self.index_name)
            self.uses_vietnamese_plugin = self._index_uses_vi_tokenizer()
            return

        # Production path: CocCoc Vietnamese tokenizer plugin. Fallback remains
        # available for local/unit environments without the ES plugin.
        try:
            settings = self._make_settings(use_icu=True)
            self.client.indices.create(
                index=self.index_name,
                settings=settings["settings"],
                mappings=settings["mappings"],
            )
            logger.info(
                "Created index '%s' with vi_tokenizer analyzer.",
                self.index_name,
            )
            self.uses_vietnamese_plugin = True
        except Exception:
            if not self._is_missing_vietnamese_plugin_error():
                raise
            logger.warning(
                "Vietnamese analysis plugin is not available; falling back to "
                "standard tokenizer analyzer."
            )
            settings = self._make_settings(use_icu=False)
            self.client.indices.create(
                index=self.index_name,
                settings=settings["settings"],
                mappings=settings["mappings"],
            )
            logger.info(
                "Created index '%s' with fallback analyzer.", self.index_name
            )
            self.uses_vietnamese_plugin = False

    @staticmethod
    def _make_settings(use_icu: bool = True) -> Dict[str, Any]:
        """Build index settings.

        ``use_icu`` is kept as a backward-compatible parameter name. In the
        current implementation, ``True`` means the CocCoc Vietnamese plugin
        path (``vi_tokenizer``); ``False`` means the standard-tokenizer fallback.
        """
        return _build_index_settings(use_vietnamese_plugin=use_icu)

    def _index_uses_vi_tokenizer(self) -> bool:
        """Best-effort detection for existing indices."""
        try:
            resp = self.client.indices.get_settings(index=self.index_name)
            index_settings = next(iter(resp.values())).get("settings", {}).get("index", {})
            analysis = index_settings.get("analysis", {})
            analyzer = analysis.get("analyzer", {}).get("vietnamese_analyzer", {})
            return (
                analyzer.get("tokenizer") == "vi_tokenizer"
                or analyzer.get("type") == "vi_analyzer"
            )
        except Exception:
            logger.warning(
                "Could not inspect analyzer for index '%s'. Assuming fallback mode.",
                self.index_name,
                exc_info=True,
            )
            return False

    @staticmethod
    def _is_missing_vietnamese_plugin_error() -> bool:
        """Return True when the active exception looks like a missing ES plugin."""
        import sys

        exc = sys.exc_info()[1]
        msg = str(exc or "").lower()
        return (
            ("vi_tokenizer" in msg or "vi_analyzer" in msg)
            and (
                "unknown" in msg
                or "not found" in msg
                or "failed to find" in msg
                or "failed to load" in msg
            )
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata_text_values(metadata: Dict[str, Any]) -> Iterable[str]:
        """Yield compact text values from metadata fields useful for BM25."""
        for field in _SEARCH_TEXT_METADATA_FIELDS:
            value = metadata.get(field)
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    if item is not None and str(item).strip():
                        yield str(item)
                continue
            if str(value).strip():
                yield str(value)

    @staticmethod
    def _clean_search_text(value: Any) -> str:
        """Normalize Markdown/table-heavy text before indexing as search_text."""
        text = str(value or "")
        if not text:
            return ""
        text = _MARKDOWN_CODE_FENCE_RE.sub(" ", text)
        text = _MARKDOWN_LINK_RE.sub(lambda m: m.group(2) or " ", text)
        text = _MARKDOWN_INLINE_CODE_RE.sub(r"\1", text)
        text = _MARKDOWN_TABLE_SEPARATOR_RE.sub(" ", text)
        text = text.replace("|", " ")
        text = _MARKDOWN_DECORATION_RE.sub(" ", text)
        return _WHITESPACE_RE.sub(" ", text).strip()

    @classmethod
    def _build_search_text(cls, text: str, metadata: Dict[str, Any]) -> str:
        parts = [text, *cls._metadata_text_values(metadata)]
        cleaned_parts: List[str] = []
        seen: set[str] = set()
        for part in parts:
            cleaned = cls._clean_search_text(part)
            if not cleaned:
                continue
            folded = fold_vietnamese_text(cleaned).lower()
            if folded in seen:
                continue
            seen.add(folded)
            cleaned_parts.append(cleaned)
        return "\n".join(cleaned_parts)

    def index_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        batch_size: int = 500,
    ) -> int:
        """Bulk-index document chunks into Elasticsearch.

        Args:
            texts: Raw chunk texts.
            metadatas: Optional list of metadata dicts per chunk.
            ids: Optional list of document ids (chunk_id).
            batch_size: Number of docs per bulk request.

        Returns:
            Number of successfully indexed documents.
        """
        n = len(texts)
        if metadatas is None:
            metadatas = [{}] * n
        _ids: List[Optional[str]] = ids if ids is not None else [None] * n # type: ignore

        indexed = 0
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            actions = []
            for i in range(start, end):
                doc = {**metadatas[i], "text": texts[i]}
                if _ids[i] is not None:
                    doc.setdefault("chunk_id", str(_ids[i]))
                if not doc.get("search_text"):
                    doc["search_text"] = self._build_search_text(texts[i], doc)
                action = {"_index": self.index_name, "_source": doc}
                if _ids[i] is not None:
                    action["_id"] = _ids[i]
                actions.append(action)

            success, errors = helpers.bulk(
                self.client, actions, raise_on_error=False
            )
            indexed += success
            if errors:
                logger.warning("Bulk index errors: %s", errors)

        self.client.indices.refresh(index=self.index_name)
        logger.info(
            "Indexed %d/%d documents into '%s'.", indexed, n, self.index_name
        )
        return indexed

    # ------------------------------------------------------------------
    # Metadata update
    # ------------------------------------------------------------------

    def update_metadata_batch(
        self,
        id_metadata_pairs: List[Tuple[str, Dict[str, Any]]],
        overwrite: bool = False,
        batch_size: int = 500,
    ) -> int:
        """Update metadata/source fields for many Elasticsearch documents.

        Args:
            id_metadata_pairs: Iterable of ``(id, metadata_dict)`` tuples.
            overwrite: If True, replace the full ``_source`` for each document.
                       If False, merge the provided fields into existing docs.
            batch_size: Number of bulk actions per request.

        Returns:
            Number of successful bulk actions reported by Elasticsearch.
        """
        total = len(id_metadata_pairs)
        updated = 0

        for start in range(0, total, batch_size):
            batch = id_metadata_pairs[start : start + batch_size]
            actions: List[Dict[str, Any]] = []

            for doc_id, metadata in batch:
                if overwrite:
                    actions.append(
                        {
                            "_op_type": "index",
                            "_index": self.index_name,
                            "_id": str(doc_id),
                            "_source": metadata,
                        }
                    )
                else:
                    actions.append(
                        {
                            "_op_type": "update",
                            "_index": self.index_name,
                            "_id": str(doc_id),
                            "doc": metadata,
                        }
                    )

            success, errors = helpers.bulk(
                self.client,
                actions,
                raise_on_error=False,
                raise_on_exception=False,
            )
            updated += success
            if errors:
                logger.warning(
                    "Bulk metadata update errors in '%s': %d error(s). sample=%s",
                    self.index_name,
                    len(errors),
                    errors[:1],
                )

            logger.info(
                "update_metadata_batch: %d/%d docs processed in '%s'.",
                min(start + len(batch), total),
                total,
                self.index_name,
            )

        self.client.indices.refresh(index=self.index_name)
        logger.info(
            "update_metadata_batch done: %d/%d doc(s) updated in '%s' (overwrite=%s).",
            updated,
            total,
            self.index_name,
            overwrite,
        )
        return updated

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def metadata_filter_search(
        self,
        es_filter: Dict[str, Any],
        max_results: int = 1000,
    ) -> List[str]:
        """Filter-only search (no text scoring) — returns matching doc IDs.

        Used as the **metadata pre-search step** before hybrid retrieval:
        run an ES query whose ``filter`` clause targets metadata fields
        (major_code, date_str, applicable_cohort, applicable_major …), collect the matching
        doc IDs, then pass them to Qdrant as ``HasIdCondition`` so vector
        search is restricted to that pre-filtered subset.

        Args:
            es_filter: An ES query dict that will be placed inside
                ``{"bool": {"filter": [es_filter]}}`` — no text scoring.
            max_results: Upper bound on returned IDs (default 1 000).

        Returns:
            List of ``_id`` strings for matching documents.
        """
        try:
            resp = self.client.search(
                index=self.index_name,
                size=max_results,
                query={"bool": {"filter": [es_filter]}},
                source=False,  # don't fetch document bodies — IDs only
            )
            return [hit["_id"] for hit in resp["hits"]["hits"]]
        except Exception:
            logger.warning(
                "metadata_filter_search failed for index '%s'",
                self.index_name,
                exc_info=True,
            )
            return []

    def get_latest_chunk_ids_by_date(self, max_n: int = 200) -> List[str]:
        """Return chunk IDs for the *max_n* most-recent documents by ``date_str``.

        Used by the **kehoach freshness path**: when a query contains
        freshness-intent phrases ("mới nhất", "gần đây", …) but no explicit
        calendar date, we pre-filter Qdrant to the newest posted documents so
        that recency becomes a hard constraint rather than a tiny score bonus.

        ``date_str`` is stored as ``"D/M/YYYY"`` (keyword field, not a date
        field), so Elasticsearch cannot sort it natively.  This method fetches
        up to 1 000 docs that have a ``date_str`` value, parses dates in Python,
        sorts descending, and returns the ``_id`` strings of the top *max_n*.

        Returns:
            List of ``_id`` strings sorted by date descending (newest first).
            Returns ``[]`` on any error so the caller can fall back gracefully.
        """
        try:
            resp = self.client.search(
                index=self.index_name,
                size=1000,
                query={"exists": {"field": "date_str"}},
                source=["date_str"],
            )
        except Exception:
            logger.warning(
                "get_latest_chunk_ids_by_date: ES query failed for '%s'",
                self.index_name,
                exc_info=True,
            )
            return []

        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return []

        # Parse D/M/YYYY and sort descending (newest first)
        from datetime import datetime as _dt  # local import to avoid shadowing

        dated: List[Tuple[Any, str]] = []
        for hit in hits:
            raw = (hit.get("_source") or {}).get("date_str", "")
            try:
                parts = str(raw).split("/")
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                dated.append((_dt(y, m, d), hit["_id"]))
            except Exception:
                # Malformed or missing date_str — skip this doc
                continue

        dated.sort(key=lambda x: x[0], reverse=True)
        return [doc_id for _, doc_id in dated[:max_n]]

    def resolve_chunk_ids_for_qdrant(
        self,
        ids: List[Any],
        max_results: int = 10000,
    ) -> List[str]:
        """Resolve arbitrary metadata IDs to ES ``_id`` chunk IDs.

        This guards against ID-level mismatch between metadata filtering and
        vector search. In the normal path, *ids* already contains ES ``_id``
        values and this method returns them unchanged. If not, it attempts a
        second-stage mapping via payload fields (``chunk_id`` / ``doc_id``)
        and returns the corresponding ES ``_id`` values for Qdrant filtering.

        Args:
            ids: Raw IDs produced by metadata filtering logic.
            max_results: Upper bound for mapping search results.

        Returns:
            Deduplicated ES ``_id`` list that can be passed to
            ``HasIdCondition`` in Qdrant.
        """
        if not ids:
            return []

        # Keep only non-empty scalar values and normalise to string once.
        raw_ids: List[str] = []
        for value in ids:
            if value is None:
                continue
            s = str(value).strip()
            if s:
                raw_ids.append(s)

        if not raw_ids:
            return []

        # 1) Fast path: treat input as ES _id (the expected chunk-level ID).
        try:
            resp = self.client.search(
                index=self.index_name,
                size=min(max_results, len(raw_ids)),
                query={"ids": {"values": raw_ids}},
                source=False,
            )
            matched_ids = [hit["_id"] for hit in resp["hits"]["hits"]]
        except Exception:
            logger.warning(
                "resolve_chunk_ids_for_qdrant ids-query failed for index '%s'",
                self.index_name,
                exc_info=True,
            )
            matched_ids = []

        if matched_ids:
            if len(matched_ids) < len(raw_ids):
                logger.info(
                    "resolve_chunk_ids_for_qdrant[%s]: direct _id match %d/%d",
                    self.index_name,
                    len(matched_ids),
                    len(raw_ids),
                )
            return list(dict.fromkeys(matched_ids))

        # 2) Fallback path: input might be doc-level/chunk-label IDs.
        #    Map those values to ES _id values via payload fields.
        should_clauses: List[Dict[str, Any]] = [
            {"terms": {"chunk_id": raw_ids}},
            {"terms": {"chunk_id.keyword": raw_ids}},
            {"terms": {"doc_id.keyword": raw_ids}},
        ]

        int_doc_ids: List[int] = []
        for value in raw_ids:
            try:
                int_doc_ids.append(int(value))
            except Exception:
                continue
        if int_doc_ids:
            should_clauses.append({"terms": {"doc_id": int_doc_ids}})

        try:
            resp = self.client.search(
                index=self.index_name,
                size=max_results,
                query={
                    "bool": {
                        "should": should_clauses,
                        "minimum_should_match": 1,
                    }
                },
                source=False,
            )
            mapped_ids = [hit["_id"] for hit in resp["hits"]["hits"]]
        except Exception:
            logger.warning(
                "resolve_chunk_ids_for_qdrant fallback mapping failed for index '%s'",
                self.index_name,
                exc_info=True,
            )
            mapped_ids = []

        if mapped_ids:
            logger.warning(
                "resolve_chunk_ids_for_qdrant[%s]: ID-level mismatch detected. "
                "Mapped %d raw IDs -> %d chunk IDs.",
                self.index_name,
                len(raw_ids),
                len(mapped_ids),
            )
            return list(dict.fromkeys(mapped_ids))

        logger.warning(
            "resolve_chunk_ids_for_qdrant[%s]: cannot map %d IDs to chunk-level _id. "
            "sample=%s",
            self.index_name,
            len(raw_ids),
            raw_ids[:5],
        )
        return []

    # ------------------------------------------------------------------
    # Collection-specific keyword boosting
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_keyword_results(
        primary: List[Dict[str, Any]],
        fallback: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        seen: set[str] = set()
        merged: List[Dict[str, Any]] = []
        for item in [*primary, *fallback]:
            doc_id = str(item.get("id", ""))
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            merged.append(item)
            if len(merged) >= top_k:
                break
        return merged

    def _hits_to_keyword_results(
        self,
        hits: List[Dict[str, Any]],
        signals: Any,
        mode: str,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for hit in hits:
            source = dict(hit["_source"])
            text = source.pop("text", "")
            source.pop("search_text", None)
            table_hit = bool(signals.table_lookup and source.get("has_table"))
            score = float(hit["_score"] or 0.0)
            if table_hit:
                score *= 1.2
            source["_keyword_search_mode"] = mode
            source["_keyword_table_lookup_hit"] = table_hit
            results.append(
                {
                    "id": hit["_id"],
                    "text": text,
                    "metadata": source,
                    "score": score,
                }
            )
        return sorted(results, key=lambda item: item["score"], reverse=True)

    def keyword_search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
        exclude_terms: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """BM25 keyword search.

        Args:
            query: User query string.
            top_k: Number of results to return.
            filters: Optional Elasticsearch filter clauses
                     (e.g. ``{"term": {"type_doc": "QuyDinh"}}``).
            collection_name: Ignored in this version.
            exclude_terms: Explicit negation terms to place in ``must_not``.

        Returns:
            List of dicts sorted by BM25 score (descending):
            ``{"id", "text", "metadata", "score"}``
        """
        query_signals = analyze_query_signals(query)
        key_phrases = extract_key_phrases(query)

        segmented_query = query
        if not getattr(self, "uses_vietnamese_plugin", True):
            # Fallback-only path: add Python underscore segmentation when ES does
            # not have the CocCoc vi_tokenizer plugin.
            from utils.vietnamese_segmenter import segment_query as _segment_query

            segmented_query = _segment_query(query)

        must_clause: List[Dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": _KEYWORD_SEARCH_FIELDS,
                    "type": "best_fields",
                    "operator": "or",
                }
            }
        ]
        should_clause: List[Dict[str, Any]] = []

        # Boost segmented compound word matches
        if segmented_query != query:
            should_clause.append(
                {
                    "multi_match": {
                        "query": segmented_query,
                        "fields": _KEYWORD_SEARCH_FIELDS,
                        "type": "best_fields",
                        "operator": "or",
                        "boost": 1.5,
                    }
                }
            )
        for idx, phrase in enumerate(key_phrases):
            if _is_generic_policy_phrase(phrase):
                boost = 1.5
            else:
                boost = 10.0 if idx < 3 else 5.0
            for field, field_boost in (
                ("search_text", boost * 1.1),
                ("text", boost),
                ("title", boost * 0.8),
                ("doc_title", boost * 0.8),
                ("hierarchy_path", boost * 0.6),
                ("section_h1", boost * 0.6),
                ("section_h2", boost * 0.6),
                ("section_h3", boost * 0.5),
                ("section_h4", boost * 0.4),
            ):
                should_clause.append(
                    {
                        "match_phrase": {
                            field: {
                                "query": phrase,
                                "boost": round(field_boost, 3),
                            }
                        }
                    }
                )

        if query_signals.table_lookup:
            should_clause.append({"term": {"has_table": {"value": True, "boost": 2.5}}})

        filter_clauses: List[Dict[str, Any]] = []
        if filters:
            filter_clauses.append(filters)

        must_not_clauses = build_es_must_not_clauses(exclude_terms or [])
        # Exclude parent chunks from keyword search (search children only)
        must_not_clauses.append({"term": {"level": "parent"}})

        bool_query: Dict[str, Any] = {"must": must_clause}
        if should_clause:
            bool_query["should"] = should_clause
        if filter_clauses:
            bool_query["filter"] = filter_clauses
        if must_not_clauses:
            bool_query["must_not"] = must_not_clauses

        resp = self.client.search(
            index=self.index_name,
            size=top_k,
            query={"bool": bool_query},
        )
        hits = resp["hits"]["hits"]
        exact_results = self._hits_to_keyword_results(
            hits,
            signals=query_signals,
            mode="exact_phrase",
        )

        exact_mode = query_signals.exact_policy_lookup or query_signals.table_lookup
        should_fallback = (
            (not exact_results)
            or (not exact_mode and len(exact_results) < top_k)
        )
        if not should_fallback:
            return exact_results

        fuzzy_must_clause: List[Dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": _KEYWORD_SEARCH_FIELDS,
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]
        fuzzy_bool_query: Dict[str, Any] = {"must": fuzzy_must_clause}
        if filter_clauses:
            fuzzy_bool_query["filter"] = filter_clauses
        if must_not_clauses:
            fuzzy_bool_query["must_not"] = must_not_clauses

        fuzzy_resp = self.client.search(
            index=self.index_name,
            size=top_k,
            query={"bool": fuzzy_bool_query},
        )
        fuzzy_results = self._hits_to_keyword_results(
            fuzzy_resp["hits"]["hits"],
            signals=query_signals,
            mode="fuzzy_fallback",
        )
        return self._merge_keyword_results(exact_results, fuzzy_results, top_k)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_by_metadata(self, key: str, value: Any) -> int:
        """Delete all documents whose field ``key`` equals ``value``.

        Returns:
            Number of deleted documents.
        """
        resp = self.client.delete_by_query(
            index=self.index_name,
            query={"term": {key: value}},
        )
        deleted = resp.get("deleted", 0)
        self.client.indices.refresh(index=self.index_name)
        logger.info(
            "Deleted %d docs where %s='%s' from '%s'.",
            deleted,
            key,
            value,
            self.index_name,
        )
        return deleted

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the number of documents in the index."""
        self.client.indices.refresh(index=self.index_name)
        resp = self.client.count(index=self.index_name)
        return resp["count"]

    def delete_index(self) -> None:
        """Drop the entire index (irreversible)."""
        try:
            self.client.indices.delete(index=self.index_name)
        except Exception:  # noqa: BLE001
            pass
        logger.info("Deleted index '%s'.", self.index_name)

    def recreate_index(self) -> None:
        """Drop and recreate the index with the current analyzer/mapping."""
        self.delete_index()
        self._ensure_index()
