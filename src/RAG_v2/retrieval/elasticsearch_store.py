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
            "item_label": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "total_chunks": {"type": "integer"},
            "chunk_size": {"type": "integer"},
            "has_links": {"type": "boolean"},
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
                    "item_label": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "total_chunks": {"type": "integer"},
                    "chunk_size": {"type": "integer"},
                    "has_links": {"type": "boolean"},
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

    def keyword_search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """BM25 keyword search.

        Args:
            query: User query string.
            top_k: Number of results to return.
            filters: Optional Elasticsearch filter clauses
                     (e.g. ``{"term": {"type_doc": "QuyDinh"}}``).

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
