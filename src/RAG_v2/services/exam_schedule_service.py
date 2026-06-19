"""Ingestion orchestration for exam schedules (lịch thi).

Flow: parse → (replace ES) → (replace Mongo) → (index ES) → ParseReport.
Re-uploading the same ``source_file`` is idempotent: prior rows in both stores
are removed first. A file that parses to **zero** valid rows leaves existing
data untouched (so a bad upload cannot wipe a good schedule).

Blocking Elasticsearch calls use the sync client and are offloaded with
``anyio.to_thread.run_sync``; MongoDB calls use the async Motor driver.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import anyio
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.database import EXAM_SCHEDULES_COLLECTION
from retrieval.exam_schedule_store import ExamScheduleESStore
from schemas.exam_schedule import ExamScheduleUploadResponse
from services.exam_schedule_parser import parse_exam_workbook_async

logger = logging.getLogger(__name__)

# Lazy module-level singleton, mirroring api.routes.upload._get_storage. This is
# an interim pattern (flagged in the plan) to be migrated to lifespan + Depends.
_exam_es_store: ExamScheduleESStore | None = None


def get_exam_es_store(settings: Any) -> ExamScheduleESStore | None:
    """Return the shared exam ES store, or ``None`` when ES is unreachable."""
    global _exam_es_store
    if _exam_es_store is not None:
        return _exam_es_store
    try:
        _exam_es_store = ExamScheduleESStore(
            host=settings.elasticsearch_host,
            port=settings.elasticsearch_port,
            index_name=settings.exam_schedule_es_index,
        )
    except Exception:
        logger.warning(
            "Exam ES store unavailable; ingestion will write Mongo only.",
            exc_info=True,
        )
        return None
    return _exam_es_store


def reset_exam_es_store() -> None:
    """Reset the cached store (used by tests)."""
    global _exam_es_store
    _exam_es_store = None


async def ingest_exam_schedule(
    *,
    path: str,
    settings: Any,
    db: AsyncIOMotorDatabase,
    source_file: str,
    source_doc_id: str | None = None,
    uploaded_by: str | None = None,
    es_store: ExamScheduleESStore | None = None,
) -> ExamScheduleUploadResponse:
    """Parse and ingest one exam-schedule file idempotently."""
    records, report = await parse_exam_workbook_async(
        path,
        settings,
        source_file=source_file,
        source_doc_id=source_doc_id,
        uploaded_by=uploaded_by,
    )

    # Guard: never wipe existing data when the upload yields nothing usable.
    if not records:
        logger.warning(
            "Exam file '%s' produced 0 valid rows — existing data preserved.",
            source_file,
        )
        return ExamScheduleUploadResponse(
            source_file=source_file,
            parsed=0,
            skipped=len(report.skipped_rows),
            invalid=len(report.skipped_rows),
            replaced_existing=False,
            records_indexed=0,
            report=report,
        )

    store = es_store if es_store is not None else get_exam_es_store(settings)
    collection = db[EXAM_SCHEDULES_COLLECTION]

    # 1) Remove prior rows for this source_file from both stores.
    es_deleted = 0
    if store is not None:
        es_deleted = await anyio.to_thread.run_sync(
            store.delete_by_source_file, source_file
        )
    mongo_deleted = (
        await collection.delete_many({"source_file": source_file})
    ).deleted_count
    replaced_existing = bool(es_deleted or mongo_deleted)

    # 2) Insert the freshly parsed rows.
    await collection.insert_many([r.to_mongo() for r in records])

    records_indexed = 0
    if store is not None:
        es_docs = [r.to_es() for r in records]
        records_indexed = await anyio.to_thread.run_sync(store.index_records, es_docs)

    return ExamScheduleUploadResponse(
        source_file=source_file,
        parsed=len(records),
        skipped=len(report.skipped_rows),
        invalid=len(report.skipped_rows),
        replaced_existing=replaced_existing,
        records_indexed=records_indexed,
        report=report,
    )


async def delete_exam_schedule_source(
    *,
    source_file: str,
    settings: Any,
    db: AsyncIOMotorDatabase,
    es_store: ExamScheduleESStore | None = None,
) -> dict[str, int]:
    """Remove all exam-schedule rows for ``source_file`` from Mongo, ES, and disk.

    Returns counts so the caller (HTTP endpoint) can surface a useful response.
    Missing rows in either store are not an error — delete is idempotent.
    """
    collection = db[EXAM_SCHEDULES_COLLECTION]

    # Collect the on-disk file ids first so we can clean up after row removal.
    disk_doc_ids: set[str] = set()
    async for doc in collection.find(
        {"source_file": source_file},
        projection={"source_doc_id": 1},
    ):
        doc_id = doc.get("source_doc_id")
        if doc_id:
            disk_doc_ids.add(str(doc_id))

    mongo_deleted = (
        await collection.delete_many({"source_file": source_file})
    ).deleted_count

    store = es_store if es_store is not None else get_exam_es_store(settings)
    es_deleted = 0
    if store is not None:
        es_deleted = await anyio.to_thread.run_sync(
            store.delete_by_source_file, source_file
        )

    files_deleted = await anyio.to_thread.run_sync(
        _delete_disk_files, settings.upload_dir, disk_doc_ids
    )

    return {
        "mongo_deleted": int(mongo_deleted),
        "es_deleted": int(es_deleted),
        "files_deleted": int(files_deleted),
    }


def _delete_disk_files(upload_dir: str, doc_ids: set[str]) -> int:
    """Best-effort removal of ``uploads/exam_schedules/{doc_id}.*`` files."""
    if not doc_ids:
        return 0
    base = Path(upload_dir) / "exam_schedules"
    if not base.exists():
        return 0
    deleted = 0
    for doc_id in doc_ids:
        for path in base.glob(f"{doc_id}.*"):
            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                logger.warning("Failed to delete exam file %s: %s", path, exc)
    return deleted
