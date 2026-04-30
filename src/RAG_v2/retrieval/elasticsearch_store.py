"""Elasticsearch BM25 Store — keyword search with Vietnamese-friendly analysis."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch, helpers

logger = logging.getLogger(__name__)

DEFAULT_INDEX = "stsv"

# Index mapping with Vietnamese-friendly analysis
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
        if use_icu:
            analyzer_cfg = {
                "vietnamese_analyzer": {
                    "type": "custom",
                    "tokenizer": "icu_tokenizer",
                    "filter": ["lowercase", "icu_folding"],
                }
            }
            text_analyzer = "vietnamese_analyzer"
        else:
            analyzer_cfg = {
                "vietnamese_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                }
            }
            text_analyzer = "vietnamese_analyzer"

        return {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {"analyzer": analyzer_cfg},
            },
            "mappings": {
                "properties": {
                    "text": {"type": "text", "analyzer": text_analyzer},
                    "doc_id": {"type": "integer"},
                    "title": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "type_doc": {"type": "keyword"},
                    "time_create": {"type": "keyword"},
                    "section_context": {"type": "keyword"},
                    # Curriculum section headings — used for keyword boosting on
                    # "kỳ / đăng ký" queries to surface curriculum tables.
                    "section_h2": {"type": "text", "analyzer": text_analyzer},
                    "section_h3": {"type": "text", "analyzer": text_analyzer},
                    "item_label": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "total_chunks": {"type": "integer"},
                    "chunk_size": {"type": "integer"},
                    "has_links": {"type": "boolean"},
                    # Boolean flag — True when chunk contains an HTML/markdown table
                    "has_table": {"type": "boolean"},
                    # Metadata filter fields — must be keyword for exact term queries
                    "major_code": {"type": "keyword"},
                    "applicable_major": {"type": "keyword"},
                    "date_str": {"type": "keyword"},
                    "document_type": {"type": "keyword"},
                    "major_name": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    # ctdt-specific boosting fields
                    "course_code": {
                        "type": "keyword",
                    },
                    "course_name": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    # kehoach-specific boosting field
                    # Values: "Học kỳ I", "Học kỳ II", "năm học 2025-2026", …
                    "semester": {
                        "type": "text",
                        "analyzer": text_analyzer,
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
        if ids is None:
            ids = [None] * n

        indexed = 0
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            actions = []
            for i in range(start, end):
                doc = {**metadatas[i], "text": texts[i]}
                action = {"_index": self.index_name, "_source": doc}
                if ids[i] is not None:
                    action["_id"] = ids[i]
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
        (major_code, date_str, applicable_major …), collect the matching
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

    def keyword_search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """BM25 keyword search.

        Args:
            query: User query string.
            top_k: Number of results to return.
            filters: Optional Elasticsearch filter clauses
                     (e.g. ``{"term": {"type_doc": "QuyDinh"}}``).
            collection_name: Ignored in this version.

        Returns:
            List of dicts sorted by BM25 score (descending):
            ``{"id", "text", "metadata", "score"}``
        """
        must_clause: List[Dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["text^1.0", "title^1.5"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]

        filter_clauses: List[Dict[str, Any]] = []
        if filters:
            filter_clauses.append(filters)

        search_body: Dict[str, Any] = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": must_clause,
                    **({"filter": filter_clauses} if filter_clauses else {}),
                }
            },
        }

        resp = self.client.search(
            index=self.index_name,
            size=search_body["size"],
            query=search_body["query"],
        )
        hits = resp["hits"]["hits"]

        results: List[Dict[str, Any]] = []
        for hit in hits:
            source = hit["_source"]
            text = source.pop("text", "")
            results.append(
                {
                    "id": hit["_id"],
                    "text": text,
                    "metadata": source,
                    "score": hit["_score"],
                }
            )
        return results

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
        self.client.indices.delete(index=self.index_name, ignore=[404])
        logger.info("Deleted index '%s'.", self.index_name)
