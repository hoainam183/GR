"""Elasticsearch BM25 Store — keyword search with Vietnamese-friendly analysis."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from elasticsearch import Elasticsearch, helpers

from query.signals import analyze_query_signals, extract_key_phrases, fold_vietnamese_text
from query.structured_query import build_es_must_not_clauses

logger = logging.getLogger(__name__)

DEFAULT_INDEX = "stsv"

_KEYWORD_SEARCH_FIELDS = [
    "text^2.0",
    "title^1.8",
    "doc_title^1.6",
    "hierarchy_path^1.4",
    "section_h2^1.3",
    "section_h3^1.2",
    "section_context^1.1",
    "item_label^1.1",
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

# Index mapping with Vietnamese-friendly analysis (legacy constant — new indices
# are created via ``_make_settings()`` which includes synonyms and BM25 tuning).
INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "vietnamese_analyzer": {
                    "type": "custom",
                    "tokenizer": "icu_tokenizer",
                    "filter": ["lowercase", "icu_folding"],
                },
                "fallback_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                },
            }
        },
    },
    "mappings": {
        "properties": {
            "text": {"type": "text", "analyzer": "fallback_analyzer"},
            "doc_id": {"type": "integer"},
            "title": {
                "type": "text",
                "analyzer": "fallback_analyzer",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "type_doc": {"type": "keyword"},
            "time_create": {"type": "keyword"},
            "section_context": {"type": "keyword"},
            "section_h2": {"type": "text", "analyzer": "fallback_analyzer"},
            "section_h3": {"type": "text", "analyzer": "fallback_analyzer"},
            "item_label": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "total_chunks": {"type": "integer"},
            "chunk_size": {"type": "integer"},
            "has_links": {"type": "boolean"},
            "has_table": {"type": "boolean"},
            "major_code": {"type": "keyword"},
            "applicable_cohort": {"type": "keyword"},
            "applicable_major": {"type": "keyword"},
            "date_str": {"type": "keyword"},
            "document_type": {"type": "keyword"},
        }
    },
}


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
            return

        # Try ICU analyzer first; fall back to standard if ICU plugin is missing
        try:
            settings = self._make_settings(use_icu=True)
            self.client.indices.create(
                index=self.index_name,
                settings=settings["settings"],
                mappings=settings["mappings"],
            )
            logger.info(
                "Created index '%s' with ICU analyzer.", self.index_name
            )
        except Exception:
            logger.warning(
                "ICU plugin not available; falling back to standard analyzer."
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

    @staticmethod
    def _make_settings(use_icu: bool) -> Dict[str, Any]:
        """Build index settings, optionally using ICU analysis."""
        # Vietnamese synonym mappings for common abbreviations
        vietnamese_synonyms = [
            "CTDT,ctdt,chương trình đào tạo",
            "STSV,stsv,sổ tay sinh viên",
            "CNTT,cntt,công nghệ thông tin",
            "SV,sv,sinh viên",
            "GV,gv,giảng viên",
            "ĐHQN,đhqn,đại học quy nhơn",
            "QNU,qnu,đại học quy nhơn",
            "HP,hp,học phần",
            "TC,tc,tín chỉ",
            "GPA,gpa,điểm trung bình tích lũy",
            "NCKH,nckh,nghiên cứu khoa học",
            "KLTN,kltn,khóa luận tốt nghiệp",
            "ĐATN,đatn,đồ án tốt nghiệp",
            "HK,hk,học kỳ",
            "NH,nh,năm học",
            "ĐRL,đrl,điểm rèn luyện",
            "TBCTL,tbctl,trung bình chung tích lũy",
            "TBC,tbc,trung bình chung",
        ]

        # Vietnamese stopwords (function words with low retrieval value)
        vietnamese_stopwords = [
            "và", "hoặc", "của", "trong", "là", "có", "được", "cho",
            "với", "về", "từ", "theo", "đến", "các", "những", "một",
            "này", "đó", "khi", "nếu", "thì", "để", "do", "bởi",
            "vì", "như", "tại", "bằng", "qua", "trên", "dưới",
        ]

        if use_icu:
            filter_cfg = {
                "vietnamese_synonym": {
                    "type": "synonym",
                    "synonyms": vietnamese_synonyms,
                    "lenient": True,
                },
                "vietnamese_stop": {
                    "type": "stop",
                    "stopwords": vietnamese_stopwords,
                },
            }
            analyzer_cfg = {
                "vietnamese_analyzer": {
                    "type": "custom",
                    "tokenizer": "icu_tokenizer",
                    "filter": [
                        "lowercase",
                        "icu_folding",
                        "vietnamese_synonym",
                        "vietnamese_stop",
                    ],
                }
            }
            text_analyzer = "vietnamese_analyzer"
        else:
            filter_cfg = {
                "vietnamese_synonym": {
                    "type": "synonym",
                    "synonyms": vietnamese_synonyms,
                    "lenient": True,
                },
                "vietnamese_stop": {
                    "type": "stop",
                    "stopwords": vietnamese_stopwords,
                },
            }
            analyzer_cfg = {
                "vietnamese_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "asciifolding",
                        "vietnamese_synonym",
                        "vietnamese_stop",
                    ],
                }
            }
            text_analyzer = "vietnamese_analyzer"

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
                    "text": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "similarity": "custom_bm25",
                    },
                    "doc_id": {"type": "integer"},
                    "title": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "similarity": "custom_bm25",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "type_doc": {"type": "keyword"},
                    "time_create": {"type": "keyword"},
                    "section_context": {"type": "keyword"},
                    # Curriculum section headings — used for keyword boosting on
                    # "kỳ / đăng ký" queries to surface curriculum tables.
                    "section_h2": {"type": "text", "analyzer": text_analyzer, "similarity": "custom_bm25"},
                    "section_h3": {"type": "text", "analyzer": text_analyzer, "similarity": "custom_bm25"},
                    "item_label": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "total_chunks": {"type": "integer"},
                    "chunk_size": {"type": "integer"},
                    "has_links": {"type": "boolean"},
                    # Boolean flag — True when chunk contains an HTML/markdown table
                    "has_table": {"type": "boolean"},
                    # Metadata filter fields — must be keyword for exact term queries
                    "major_code": {"type": "keyword"},
                    "applicable_cohort": {"type": "keyword"},
                    "applicable_major": {"type": "keyword"},
                    "date_str": {"type": "keyword"},
                    "document_type": {"type": "keyword"},
                    "major_name": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "similarity": "custom_bm25",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    # ctdt-specific boosting fields
                    "course_code": {
                        "type": "keyword",
                    },
                    "course_name": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "similarity": "custom_bm25",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    # kehoach-specific boosting field
                    # Values: "Học kỳ I", "Học kỳ II", "năm học 2025-2026", …
                    "semester": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "similarity": "custom_bm25",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                }
            },
        }

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

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
    def _source_contains_phrase(
        text: str,
        metadata: Dict[str, Any],
        phrases: List[str],
    ) -> bool:
        haystack = " ".join(
            [
                text or "",
                str(metadata.get("title", "") or ""),
                str(metadata.get("doc_title", "") or ""),
                str(metadata.get("hierarchy_path", "") or ""),
                str(metadata.get("section_h2", "") or ""),
                str(metadata.get("section_h3", "") or ""),
                str(metadata.get("section_context", "") or ""),
                str(metadata.get("item_label", "") or ""),
            ]
        )
        folded_haystack = fold_vietnamese_text(haystack)
        return any(fold_vietnamese_text(phrase) in folded_haystack for phrase in phrases)

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
        phrases: List[str],
        signals: Any,
        mode: str,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for hit in hits:
            source = dict(hit["_source"])
            text = source.pop("text", "")
            phrase_hit = self._source_contains_phrase(text, source, phrases)
            table_hit = bool(signals.table_lookup and source.get("has_table"))
            score = float(hit["_score"] or 0.0)
            if phrase_hit:
                score *= 1.35
            if table_hit:
                score *= 1.2
            source["_keyword_search_mode"] = mode
            source["_keyword_exact_phrase_hit"] = phrase_hit
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
        pin_phrases = [
            phrase for phrase in key_phrases if not _is_generic_policy_phrase(phrase)
        ] or key_phrases

        # Vietnamese word segmentation: add segmented query variant for compound matching
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
                ("text", boost),
                ("title", boost * 0.8),
                ("doc_title", boost * 0.8),
                ("hierarchy_path", boost * 0.6),
                ("section_h2", boost * 0.6),
                ("section_h3", boost * 0.5),
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
            phrases=pin_phrases,
            signals=query_signals,
            mode="exact_phrase",
        )

        phrase_hit_count = sum(
            1
            for item in exact_results
            if (item.get("metadata") or {}).get("_keyword_exact_phrase_hit")
        )
        exact_mode = query_signals.exact_policy_lookup or query_signals.table_lookup
        should_fallback = (
            (not exact_results)
            or (not exact_mode and len(exact_results) < top_k)
            or (exact_mode and phrase_hit_count == 0 and len(exact_results) < min(top_k, 5))
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
            phrases=pin_phrases,
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
