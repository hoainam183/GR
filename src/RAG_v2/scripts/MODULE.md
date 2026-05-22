# Module: `scripts`

Source-verified: 2026-05-20 from `scripts/*.py` and GitNexus ingestion/indexing flow queries.

## Purpose

`scripts` contains operational CLIs for crawling, indexing, metadata updates, model downloads, and utility search/index maintenance. These scripts are not the FastAPI runtime, but they define important ingestion and maintenance workflows.

## File Map

```text
scripts/
  auto_crawler.py         Crawl -> chunk -> embed -> Qdrant/ES index -> retention.
  index_kehoach.py        Standalone indexing for kehoach chunks.
  index_quydinh.py        Standalone indexing for quydinh chunks.
  index_stsv.py           Standalone indexing for stsv chunks.
  index_to_es.py          Reindex Qdrant collection payloads into Elasticsearch.
  update_data.py          Ingest one document, sync metadata, trigger validity reload.
  update_metadata.py      Bulk metadata update across existing Qdrant points.
  setup_mongo_indexes.py  Ensure Mongo indexes for agent traces/logging.
  search_multi.py         Local multi-collection search utility.
  download_models.py      Model download helper.
```

## Auto Crawler

`auto_crawler.py` is the largest script and contains:

- `GenericCrawler`
- `ChunkProcessor`
- `DualIndexer`
- `RetentionManager`
- `AutoCrawlPipeline`

Flow:

```text
crawl official sources
  -> save JSON
  -> chunk content
  -> embed with BGE/E5
  -> index Qdrant + Elasticsearch
  -> retention cleanup
```

FastAPI lifespan may schedule this script daily when `crawler_enabled=True`.

`AutoCrawlPipeline` per-pipeline summaries include the target `collection` and a bounded `saved_chunks` preview for newly indexed chunks. Admin crawler status uses this summary payload to show what was saved after a manual crawl without querying the vector stores directly.

Supported crawler targets in source include:

- `kehoach` through HUST display-list/detail pages.
- `quydinh` through regulation display pages.

## Index Scripts

Standalone indexers generally:

1. Load chunks from `data/.../chunks`.
2. Filter already indexed chunks where implemented.
3. Embed in batches.
4. Upsert into Qdrant through `QdrantStore`.
5. Index into Elasticsearch where the script supports dual indexing.

GitNexus ingestion flows identify:

- `index_kehoach.py:index_chunks() -> QdrantStore.index_documents()`
- `index_quydinh.py:index_chunks() -> QdrantStore.index_documents()`
- `index_stsv.py:index_chunks() -> QdrantStore.index_documents()`

## Metadata Maintenance

`update_metadata.py`:

- loads chunks for a target collection
- builds id/metadata pairs
- normalizes target selection
- updates Qdrant payload metadata by id or batch

`update_data.py`:

- ingests a document path into a target collection
- syncs metadata
- can trigger validity reload through API

## Maintenance Notes

- Scripts may assume local services at configured Qdrant/ES/Mongo hosts; verify `.env` before running destructive index operations.
- Keep script metadata output aligned with `retrieval/metadata_filters.py`.
- After crawling/indexing changes, run current policy eval or post-index eval.
- Treat `delete_collection()` helpers as destructive and do not call them unless explicitly requested.

## Useful Checks

```bash
python -m py_compile scripts/*.py
python -m evaluation.two_layer_eval current --max-cases 20
```
