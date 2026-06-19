"""Unit tests for ingest_exam_schedule ordering + empty-file guard (mocked I/O)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from models.exam_schedule import ExamScheduleRecord
from schemas.exam_schedule import ParseReport, SkippedRow
from services import exam_schedule_service as svc


def _record(i: int) -> ExamScheduleRecord:
    return ExamScheduleRecord.from_parsed_row(
        {"subject_code": "CH1012", "subject_name": "Hóa học 1"},
        row_index=i,
        source_file="exam.pdf",
    )


def _db(deleted: int = 2):
    collection = MagicMock()
    collection.delete_many = AsyncMock(return_value=MagicMock(deleted_count=deleted))
    collection.insert_many = AsyncMock(return_value=MagicMock())
    db = MagicMock()
    db.__getitem__.return_value = collection
    return db, collection


@pytest.mark.asyncio
async def test_replace_then_index_ordering(monkeypatch) -> None:
    records = [_record(0), _record(1)]
    report = ParseReport(total_rows=2, valid_rows=2)
    monkeypatch.setattr(
        svc, "parse_exam_workbook_async", AsyncMock(return_value=(records, report))
    )
    store = MagicMock()
    store.delete_by_source_file.return_value = 2
    store.index_records.return_value = 2
    db, collection = _db(deleted=2)

    resp = await svc.ingest_exam_schedule(
        path="x.pdf", settings=MagicMock(), db=db,
        source_file="exam.pdf", es_store=store,
    )

    assert resp.parsed == 2
    assert resp.records_indexed == 2
    assert resp.replaced_existing is True
    store.delete_by_source_file.assert_called_once_with("exam.pdf")
    collection.delete_many.assert_awaited_once_with({"source_file": "exam.pdf"})
    collection.insert_many.assert_awaited_once()
    store.index_records.assert_called_once()


@pytest.mark.asyncio
async def test_empty_file_preserves_existing_data(monkeypatch) -> None:
    report = ParseReport(
        total_rows=1, valid_rows=0,
        skipped_rows=[SkippedRow(row_index=0, reason="no_subject")],
    )
    monkeypatch.setattr(
        svc, "parse_exam_workbook_async", AsyncMock(return_value=([], report))
    )
    store = MagicMock()
    db, collection = _db()

    resp = await svc.ingest_exam_schedule(
        path="x.pdf", settings=MagicMock(), db=db,
        source_file="exam.pdf", es_store=store,
    )

    assert resp.parsed == 0
    assert resp.replaced_existing is False
    assert resp.invalid == 1
    store.delete_by_source_file.assert_not_called()
    collection.delete_many.assert_not_awaited()
    collection.insert_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_store_writes_mongo_only(monkeypatch) -> None:
    monkeypatch.setattr(
        svc, "parse_exam_workbook_async",
        AsyncMock(return_value=([_record(0)], ParseReport(total_rows=1, valid_rows=1))),
    )
    db, collection = _db(deleted=0)

    resp = await svc.ingest_exam_schedule(
        path="x.pdf", settings=MagicMock(), db=db,
        source_file="exam.pdf", es_store=None,
    )

    assert resp.parsed == 1
    assert resp.records_indexed == 0
    collection.insert_many.assert_awaited_once()
