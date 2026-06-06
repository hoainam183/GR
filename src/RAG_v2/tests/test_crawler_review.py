from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from models.crawler import (
    CRAWLER_STATUS_INDEX_FAILED,
    CRAWLER_STATUS_INDEXED,
    CRAWLER_STATUS_PENDING_REVIEW,
)
from models.database import CRAWLER_CHUNKS_COLLECTION, CRAWLER_RUNS_COLLECTION


def _matches(doc: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class _SyncCursor(list):
    def sort(self, key: str, direction: int):
        reverse = direction < 0
        return _SyncCursor(sorted(self, key=lambda item: item.get(key, 0), reverse=reverse))

    def limit(self, value: int):
        return _SyncCursor(self[:value])


class _SyncCollection:
    def __init__(self, docs: list[dict] | None = None):
        self.docs = list(docs or [])

    def insert_one(self, doc: dict):
        self.docs.append(dict(doc))
        return SimpleNamespace(inserted_id=len(self.docs))

    def insert_many(self, docs: list[dict]):
        start = len(self.docs)
        self.docs.extend(dict(doc) for doc in docs)
        return SimpleNamespace(inserted_ids=list(range(start, len(self.docs))))

    def find_one(self, query: dict):
        for doc in self.docs:
            if _matches(doc, query):
                return doc
        return None

    def find(self, query: dict):
        return _SyncCursor([doc for doc in self.docs if _matches(doc, query)])

    def update_one(self, query: dict, update: dict):
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    def update_many(self, query: dict, update: dict):
        matched = 0
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                matched += 1
        return SimpleNamespace(matched_count=matched)


class _SyncDB:
    def __init__(self):
        self.collections = {
            CRAWLER_RUNS_COLLECTION: _SyncCollection(),
            CRAWLER_CHUNKS_COLLECTION: _SyncCollection(),
        }

    def __getitem__(self, name: str):
        return self.collections[name]


class _MongoClientFactory:
    def __init__(self, db: _SyncDB):
        self.db = db

    def __call__(self, _uri: str):
        return self

    def __getitem__(self, _name: str):
        return self.db

    def close(self):
        pass


class _AsyncCursor:
    def __init__(self, docs: list[dict]):
        self.docs = docs

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self.docs = sorted(self.docs, key=lambda item: item.get(key, 0), reverse=reverse)
        return self

    def limit(self, value: int):
        self.docs = self.docs[:value]
        return self

    async def to_list(self, length=None):
        return list(self.docs if length is None else self.docs[:length])


class _AsyncCollection(_SyncCollection):
    async def find_one(self, query: dict):
        return super().find_one(query)

    def find(self, query: dict):
        return _AsyncCursor([doc for doc in self.docs if _matches(doc, query)])

    async def update_one(self, query: dict, update: dict):
        return super().update_one(query, update)

    async def update_many(self, query: dict, update: dict):
        return super().update_many(query, update)


class _AsyncDB:
    def __init__(self, runs: list[dict], chunks: list[dict]):
        self.collections = {
            CRAWLER_RUNS_COLLECTION: _AsyncCollection(runs),
            CRAWLER_CHUNKS_COLLECTION: _AsyncCollection(chunks),
        }

    def __getitem__(self, name: str):
        return self.collections[name]


def _settings(tmp_path):
    return SimpleNamespace(
        mongodb_enabled=True,
        mongodb_uri="mongodb://test",
        mongodb_database="test",
        crawler_delay=0,
        crawler_retention_months=6,
        crawler_tags="",
        qdrant_host="localhost",
        qdrant_port=6333,
        elasticsearch_host="localhost",
        elasticsearch_port=9200,
        redis_enabled=False,
        use_redis_cache=False,
        post_index_eval_enabled=False,
        chunks_file=str(tmp_path / "chunks.json"),
    )


def test_auto_crawler_stages_chunks_without_indexing(monkeypatch, tmp_path):
    from scripts import auto_crawler

    db = _SyncDB()
    monkeypatch.setattr(auto_crawler, "MongoClient", _MongoClientFactory(db))

    class FakeCrawler:
        def __init__(self, **_kwargs):
            pass

        def crawl_new(self):
            return [{"baiviet_id": 1, "title": "Article"}]

        def save_to_file(self, _articles):
            pass

    class FakeChunkProcessor:
        def __init__(self, **_kwargs):
            pass

        def chunk_articles(self, _articles):
            return [{
                "chunk_id": "chunk-1",
                "content": "Original content",
                "metadata": {"title": "Article", "url": "https://example.test/a"},
            }]

        def save_chunks(self, _chunks):
            raise AssertionError("crawl must not append chunk archive before review")

    class FakeRetentionManager:
        def __init__(self, **_kwargs):
            pass

        def cleanup(self, indexer=None):
            assert indexer is None
            return 0

    monkeypatch.setattr(auto_crawler, "GenericCrawler", FakeCrawler)
    monkeypatch.setattr(auto_crawler, "ChunkProcessor", FakeChunkProcessor)
    monkeypatch.setattr(auto_crawler, "RetentionManager", FakeRetentionManager)

    pipeline = auto_crawler.AutoCrawlPipeline(settings=_settings(tmp_path))
    monkeypatch.setattr(
        pipeline,
        "_make_indexer",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("crawl must not index")),
    )

    result = pipeline._run_single_pipeline(
        pipeline_name="baiviet",
        crawlers_config=[{"list_path": "/", "id_param": "baiviet", "label": "BaiViet"}],
        output_file=tmp_path / "raw.json",
        chunks_file=tmp_path / "chunks.json",
        collection="kehoach",
        source_label="kehoach",
        retention_months=6,
    )

    assert result["status"] == CRAWLER_STATUS_PENDING_REVIEW
    assert result["indexed"] == 0
    assert result["review_run_id"]
    assert db[CRAWLER_RUNS_COLLECTION].docs[0]["status"] == CRAWLER_STATUS_PENDING_REVIEW
    assert db[CRAWLER_CHUNKS_COLLECTION].docs[0]["content"] == "Original content"


@pytest.mark.anyio
async def test_crawler_status_returns_pending_previews():
    from api.routes.admin_stats import get_crawler_status

    now = datetime.now(timezone.utc)
    db = _AsyncDB(
        runs=[{
            "run_id": "run-1",
            "pipeline": "baiviet",
            "collection": "kehoach",
            "status": CRAWLER_STATUS_PENDING_REVIEW,
            "new_articles": 1,
            "new_chunks": 1,
            "indexed": 0,
            "expired_removed": 0,
            "created_at": now,
            "updated_at": now,
        }],
        chunks=[{
            "run_id": "run-1",
            "chunk_id": "chunk-1",
            "chunk_index": 0,
            "content": "Preview content",
            "metadata": {"title": "Article", "url": "https://example.test/a"},
            "edited": False,
            "index_status": "pending",
        }],
    )

    response = await get_crawler_status(_user=SimpleNamespace(), db=db)

    assert response["pending_runs"][0]["review_run_id"] == "run-1"
    assert response["pending_runs"][0]["saved_chunks"][0]["content_preview"] == "Preview content"


def test_crawl_notification_summary_counts_nested_all_result():
    from api.routes.admin_stats import (
        _build_crawl_notification_article_links,
        _build_crawl_notification_summary,
    )

    crawl_result = {
        "kehoach": {
            "baiviet": {
                "pipeline": "baiviet",
                "collection": "kehoach",
                "new_articles": 5,
                "saved_chunks": [
                    {"title": "Ke hoach A", "url": "https://example.test/a"},
                ],
            },
            "kehoach_list": {
                "pipeline": "kehoach_list",
                "collection": "kehoach",
                "new_articles": 3,
                "saved_chunks": [],
            },
        },
        "quydinh": {
            "pipeline": "quydinh",
            "collection": "quydinh",
            "new_articles": 2,
            "saved_chunks": [
                {
                    "metadata": {
                        "title": "Quy dinh B",
                        "url": "https://example.test/b",
                    },
                },
            ],
        },
    }

    summary = _build_crawl_notification_summary(crawl_result)
    links = _build_crawl_notification_article_links(summary["saved_chunks"])

    assert summary["new_articles"] == 10
    assert summary["pipelines"] == ["baiviet", "kehoach_list", "quydinh"]
    assert summary["collections"] == ["kehoach", "quydinh"]
    assert links == [
        {"title": "Ke hoach A", "url": "https://example.test/a"},
        {"title": "Quy dinh B", "url": "https://example.test/b"},
    ]


def test_crawl_notification_body_omits_pipeline_target():
    from api.routes.admin_stats import (
        _build_crawl_notification_body,
        _format_crawl_source_label,
    )

    source_label = _format_crawl_source_label(["kehoach", "quydinh"])
    assert source_label == "Kế hoạch, Quy định"

    assert (
        _build_crawl_notification_body(2, source_label)
        == "Có 2 bài viết mới từ nguồn Kế hoạch, Quy định."
    )
    assert _build_crawl_notification_body(0, "all") == (
        "Không có bài viết mới sau lần cập nhật dữ liệu."
    )


@pytest.mark.anyio
async def test_manual_crawl_notification_skips_when_no_new_data():
    from api.routes.admin_stats import _create_crawl_notifications

    result = await _create_crawl_notifications(
        {
            "pipeline": "kehoach",
            "collection": "kehoach",
            "new_articles": 0,
            "saved_chunks": [],
        },
        "kehoach",
    )

    assert result == {
        "created_count": 0,
        "target_user_ids": [],
        "push_sent_count": 0,
        "push_error_count": 0,
        "skipped_reason": "no_new_crawl_data",
    }


@pytest.mark.anyio
async def test_update_crawler_chunk_marks_edited():
    from api.routes.admin_stats import CrawlerChunkUpdateBody, update_crawler_run_chunk

    db = _AsyncDB(
        runs=[{"run_id": "run-1", "status": CRAWLER_STATUS_PENDING_REVIEW}],
        chunks=[{
            "run_id": "run-1",
            "chunk_id": "chunk-1",
            "chunk_index": 0,
            "content": "Original",
            "original_content": "Original",
            "metadata": {},
            "edited": False,
            "index_status": "pending",
        }],
    )

    updated = await update_crawler_run_chunk(
        "run-1",
        "chunk-1",
        CrawlerChunkUpdateBody(content="Edited"),
        _user=SimpleNamespace(),
        db=db,
    )

    assert updated["content"] == "Edited"
    assert updated["edited"] is True


def test_index_staged_run_uses_edited_content_and_marks_indexed(monkeypatch, tmp_path):
    from scripts import auto_crawler

    chunks_file = tmp_path / "chunks.json"
    chunks_file.write_text("[]", encoding="utf-8")
    db = _SyncDB()
    db[CRAWLER_RUNS_COLLECTION].docs.append({
        "run_id": "run-1",
        "pipeline": "baiviet",
        "collection": "kehoach",
        "status": CRAWLER_STATUS_PENDING_REVIEW,
        "new_articles": 1,
        "new_chunks": 1,
        "indexed": 0,
        "chunks_file": str(chunks_file),
        "summary": {},
    })
    db[CRAWLER_CHUNKS_COLLECTION].docs.append({
        "run_id": "run-1",
        "chunk_id": "chunk-1",
        "chunk_index": 0,
        "content": "Edited content",
        "original_content": "Original content",
        "metadata": {"title": "Article"},
        "edited": True,
        "index_status": "pending",
    })
    monkeypatch.setattr(auto_crawler, "MongoClient", _MongoClientFactory(db))

    captured: dict[str, list[dict]] = {}

    class FakeDualIndexer:
        def __init__(self, **_kwargs):
            pass

        def index_chunks(self, chunks):
            captured["chunks"] = chunks
            return len(chunks)

    monkeypatch.setattr(auto_crawler, "DualIndexer", FakeDualIndexer)
    monkeypatch.setattr(auto_crawler, "_invalidate_crawler_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auto_crawler, "_trigger_crawler_post_index_eval", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auto_crawler.AutoCrawlPipeline, "_notify", staticmethod(lambda _summary: None))

    summary = auto_crawler.index_staged_crawler_run(_settings(tmp_path), "run-1")

    assert captured["chunks"][0]["content"] == "Edited content"
    assert db[CRAWLER_RUNS_COLLECTION].docs[0]["status"] == CRAWLER_STATUS_INDEXED
    assert db[CRAWLER_CHUNKS_COLLECTION].docs[0]["index_status"] == CRAWLER_STATUS_INDEXED
    assert summary["indexed"] == 1
    assert "Edited content" in chunks_file.read_text(encoding="utf-8")


def test_index_failure_leaves_run_retryable(monkeypatch, tmp_path):
    from scripts import auto_crawler

    chunks_file = tmp_path / "chunks.json"
    chunks_file.write_text("[]", encoding="utf-8")
    db = _SyncDB()
    db[CRAWLER_RUNS_COLLECTION].docs.append({
        "run_id": "run-1",
        "pipeline": "baiviet",
        "collection": "kehoach",
        "status": CRAWLER_STATUS_PENDING_REVIEW,
        "new_articles": 1,
        "new_chunks": 1,
        "chunks_file": str(chunks_file),
        "summary": {},
    })
    db[CRAWLER_CHUNKS_COLLECTION].docs.append({
        "run_id": "run-1",
        "chunk_id": "chunk-1",
        "chunk_index": 0,
        "content": "Content",
        "metadata": {},
        "edited": False,
        "index_status": "pending",
    })
    monkeypatch.setattr(auto_crawler, "MongoClient", _MongoClientFactory(db))

    class FailingDualIndexer:
        def __init__(self, **_kwargs):
            pass

        def index_chunks(self, _chunks):
            raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr(auto_crawler, "DualIndexer", FailingDualIndexer)

    with pytest.raises(RuntimeError):
        auto_crawler.index_staged_crawler_run(_settings(tmp_path), "run-1")

    assert db[CRAWLER_RUNS_COLLECTION].docs[0]["status"] == CRAWLER_STATUS_INDEX_FAILED
    assert db[CRAWLER_CHUNKS_COLLECTION].docs[0]["index_status"] == CRAWLER_STATUS_INDEX_FAILED
