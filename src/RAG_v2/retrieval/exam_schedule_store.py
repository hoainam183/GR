"""Elasticsearch store for exam schedules (lịch thi) — structured + BM25.

Separate from ``ElasticsearchStore`` (the document/chunk index) because exam
rows have a fixed tabular shape queried with structured filters: keyword terms
for codes/rooms/sessions, a real ``date`` field for day/range filters, and a
small free-text ``search_text`` for subject-name matching.

The Vietnamese analyzer + CocCoc-plugin/standard-tokenizer fallback mirrors
``ElasticsearchStore`` so the index builds in CI without the plugin.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from elasticsearch import Elasticsearch, helpers

from retrieval.elasticsearch_store import (
    VIETNAMESE_STOPWORDS,
    VIETNAMESE_SYNONYMS,
)

logger = logging.getLogger(__name__)

DEFAULT_EXAM_INDEX = "exam_schedules"

# Date column accepts ISO (what we write), display dd/MM/yyyy, and epoch millis.
_EXAM_DATE_FORMAT = "yyyy-MM-dd||dd/MM/yyyy||epoch_millis"

_KEYWORD_FIELDS = (
    "subject_code",
    "exam_type",
    "exam_room",
    "exam_session",
    "start_time",
    "group",
    "cohort",
    "exam_week",
    "weekday",
    "exam_batch",
    "mgmt_class_code",
    "exam_class_code",
    "exam_date_str",
    "source_file",
)


def build_exam_index_settings(use_vietnamese_plugin: bool) -> dict[str, Any]:
    """Index settings + mappings for the exam index (plugin or fallback)."""
    tokenizer = "vi_tokenizer" if use_vietnamese_plugin else "standard"
    analyzer = "vietnamese_analyzer"

    text_field = {
        "type": "text",
        "analyzer": analyzer,
        "search_analyzer": analyzer,
        "similarity": "custom_bm25",
        "fields": {"keyword": {"type": "keyword"}},
    }
    properties: dict[str, Any] = {
        "subject_name": text_field,
        "note": text_field,
        "search_text": {
            "type": "text",
            "analyzer": analyzer,
            "search_analyzer": analyzer,
            "similarity": "custom_bm25",
        },
        "exam_date": {"type": "date", "format": _EXAM_DATE_FORMAT},
        "row_index": {"type": "integer"},
        "student_count": {"type": "integer"},
    }
    for field in _KEYWORD_FIELDS:
        properties[field] = {"type": "keyword"}

    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    analyzer: {
                        "type": "custom",
                        "tokenizer": tokenizer,
                        "filter": [
                            "lowercase",
                            "vietnamese_synonym",
                            "vietnamese_stop",
                            "vietnamese_ascii_folding",
                        ],
                    }
                },
                "filter": {
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
                },
            },
            "index": {
                "similarity": {
                    "custom_bm25": {"type": "BM25", "k1": 1.5, "b": 0.5}
                }
            },
        },
        "mappings": {"properties": properties},
    }


class ExamScheduleESStore:
    """Manages the Elasticsearch index used for exam-schedule lookups."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        index_name: str = DEFAULT_EXAM_INDEX,
    ) -> None:
        self.index_name = index_name
        self.client = Elasticsearch(hosts=[f"http://{host}:{port}"])
        if not self.client.ping():
            raise ConnectionError(
                f"Cannot connect to Elasticsearch at {host}:{port}"
            )
        logger.info("Connected to Elasticsearch (exam) at %s:%d", host, port)
        self._ensure_index()

    # ── index management ─────────────────────────────────────────────────────

    def _ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index_name):
            logger.info("Exam index '%s' already exists.", self.index_name)
            return
        try:
            settings = build_exam_index_settings(use_vietnamese_plugin=True)
            self.client.indices.create(
                index=self.index_name,
                settings=settings["settings"],
                mappings=settings["mappings"],
            )
            logger.info(
                "Created exam index '%s' with vi_tokenizer.", self.index_name
            )
        except Exception:
            if not self._is_missing_vietnamese_plugin_error():
                raise
            logger.warning(
                "Vietnamese plugin missing; creating exam index '%s' with the "
                "standard tokenizer fallback.",
                self.index_name,
            )
            settings = build_exam_index_settings(use_vietnamese_plugin=False)
            self.client.indices.create(
                index=self.index_name,
                settings=settings["settings"],
                mappings=settings["mappings"],
            )

    @staticmethod
    def _is_missing_vietnamese_plugin_error() -> bool:
        exc = sys.exc_info()[1]
        msg = str(exc or "").lower()
        return ("vi_tokenizer" in msg or "vi_analyzer" in msg) and (
            "unknown" in msg
            or "not found" in msg
            or "failed to find" in msg
            or "failed to load" in msg
        )

    # ── write ────────────────────────────────────────────────────────────────

    def index_records(self, records: list[dict[str, Any]]) -> int:
        """Bulk-index ES docs. ``_id = f"{source_file}:{row_index}"``."""
        if not records:
            return 0
        actions = [
            {
                "_index": self.index_name,
                "_id": f"{doc['source_file']}:{doc['row_index']}",
                "_source": doc,
            }
            for doc in records
        ]
        success, errors = helpers.bulk(
            self.client, actions, raise_on_error=False
        )
        if errors:
            logger.warning("Exam bulk index errors: %s", errors[:1])
        self.client.indices.refresh(index=self.index_name)
        logger.info("Indexed %d exam rows into '%s'.", success, self.index_name)
        return success

    def delete_by_source_file(self, source_file: str) -> int:
        """Delete all rows previously indexed from ``source_file``."""
        resp = self.client.delete_by_query(
            index=self.index_name,
            query={"term": {"source_file": source_file}},
        )
        deleted = resp.get("deleted", 0)
        self.client.indices.refresh(index=self.index_name)
        logger.info(
            "Deleted %d exam rows for source_file='%s' from '%s'.",
            deleted,
            source_file,
            self.index_name,
        )
        return deleted

    # ── read ─────────────────────────────────────────────────────────────────

    @staticmethod
    def build_query(
        *,
        subject_code: str | None = None,
        subject_name: str | None = None,
        exam_date: str | None = None,
        exam_date_from: str | None = None,
        exam_date_to: str | None = None,
        exam_room: str | None = None,
        group: str | None = None,
        cohort: str | None = None,
        exam_type: str | None = None,
    ) -> dict[str, Any]:
        """Build the ES bool query for the given filters (testable in isolation).

        ``exam_date`` matches one exact day; ``exam_date_from``/``exam_date_to``
        give an inclusive range (e.g. "lịch thi tuần tới"). ``cohort`` uses a
        ``prefix`` so "K70" still matches a stored "K70C".
        """
        filter_clauses: list[dict[str, Any]] = []
        must_clauses: list[dict[str, Any]] = []

        if subject_code:
            filter_clauses.append(
                {"term": {"subject_code": subject_code.upper()}}
            )
        if exam_type:
            filter_clauses.append({"term": {"exam_type": exam_type}})
        if exam_room:
            filter_clauses.append({"term": {"exam_room": exam_room}})
        if group:
            filter_clauses.append({"term": {"group": group}})
        if cohort:
            filter_clauses.append({"prefix": {"cohort": cohort.upper()}})
        if exam_date:
            filter_clauses.append(
                {"range": {"exam_date": {"gte": exam_date, "lte": exam_date}}}
            )
        elif exam_date_from or exam_date_to:
            bounds: dict[str, str] = {}
            if exam_date_from:
                bounds["gte"] = exam_date_from
            if exam_date_to:
                bounds["lte"] = exam_date_to
            filter_clauses.append({"range": {"exam_date": bounds}})
        should_clauses: list[dict[str, Any]] = []
        if subject_name:
            name_clause = {
                "multi_match": {
                    "query": subject_name,
                    "fields": ["subject_name^2", "search_text"],
                    "type": "best_fields",
                    "operator": "or",
                }
            }
            # Only downgrade name to an optional booster when subject_code (the
            # primary key) is present — there it tolerates typos. Otherwise the
            # name IS the discriminator: leaving it in `should` lets broad
            # filters like exam_type alone return arbitrary rows date-sorted,
            # truncating the requested subject out of the top-K.
            if subject_code:
                should_clauses.append(name_clause)
            else:
                must_clauses.append(name_clause)

        bool_query: dict[str, Any] = {}
        if filter_clauses:
            bool_query["filter"] = filter_clauses
        if must_clauses:
            bool_query["must"] = must_clauses
        if should_clauses:
            bool_query["should"] = should_clauses
        # No constraint at all → match everything (caller usually passes ≥1 filter).
        if not bool_query:
            return {"match_all": {}}
        return {"bool": bool_query}

    def search(
        self,
        *,
        subject_code: str | None = None,
        subject_name: str | None = None,
        exam_date: str | None = None,
        exam_date_from: str | None = None,
        exam_date_to: str | None = None,
        exam_room: str | None = None,
        group: str | None = None,
        cohort: str | None = None,
        exam_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return matching exam rows (``_source`` dicts) sorted by date then slot."""
        query = self.build_query(
            subject_code=subject_code,
            subject_name=subject_name,
            exam_date=exam_date,
            exam_date_from=exam_date_from,
            exam_date_to=exam_date_to,
            exam_room=exam_room,
            group=group,
            cohort=cohort,
            exam_type=exam_type,
        )
        sort: list[dict[str, Any]] = []
        # When name is the discriminator (no precise date pin), let BM25 rank
        # first so the requested subject isn't truncated by chronological order.
        if subject_name and not (exam_date or exam_date_from or exam_date_to):
            sort.append({"_score": {"order": "desc"}})
        sort.extend(
            [
                {"exam_date": {"order": "asc", "missing": "_last"}},
                {"start_time": {"order": "asc", "missing": "_last"}},
            ]
        )
        resp = self.client.search(
            index=self.index_name,
            size=max(1, limit),
            query=query,
            sort=sort,
        )
        return [hit["_source"] for hit in resp["hits"]["hits"]]

    def count(self) -> int:
        self.client.indices.refresh(index=self.index_name)
        return self.client.count(index=self.index_name)["count"]

    def delete_index(self) -> None:
        try:
            self.client.indices.delete(index=self.index_name)
        except Exception:  # noqa: BLE001
            pass
