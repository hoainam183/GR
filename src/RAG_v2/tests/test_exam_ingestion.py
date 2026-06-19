"""Integration: exam ingestion against real Mongo + Elasticsearch.

Exercises the service + stores end-to-end (the HTTP layer would require loading
the full RAG pipeline). The PDF loader is unit-tested separately with a mocked
pdfplumber; this round-trip uses a generated .xlsx fixture (format-agnostic from
the service's point of view). Skips when the backing services are unreachable.

    pytest src/RAG_v2/tests/test_exam_ingestion.py -m integration
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from openpyxl import Workbook

from config.settings import Settings
from models.database import EXAM_SCHEDULES_COLLECTION
from retrieval.exam_schedule_store import ExamScheduleESStore
from services.exam_schedule_service import ingest_exam_schedule

pytestmark = pytest.mark.integration

HEADERS = [
    "Mã lớp QT", "Mã HP", "Tên học phần", "Ghi chú", "Nhóm", "Tuần thi",
    "Thứ", "Ngày", "Kíp thi", "Phòng thi", "SL", "Đợt", "Mã lớp thi",
]
DATA = [
    ["CK166692", "CH1012", "Hóa học 1", "", "02-K70C", "Tuần 35", "Thứ bảy",
     "9/5/2026", "Kíp 1", "D3-201", 15, "AB", "200985"],
    ["CK166693", "MI1141", "Giải tích 1", "", "01-K70C", "Tuần 35", "Chủ nhật",
     "10/5/2026", "Kíp 2", "D5-101", 30, "AB", "200986"],
]


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def es_store(settings):
    idx = f"exam_schedules_test_{uuid.uuid4().hex[:8]}"
    try:
        store = ExamScheduleESStore(
            host=settings.elasticsearch_host,
            port=settings.elasticsearch_port,
            index_name=idx,
        )
    except Exception:
        pytest.skip("Elasticsearch not reachable")
    yield store
    store.delete_index()


@pytest.fixture
async def db(settings):
    from models.database import close_motor_client, get_motor_client

    client = get_motor_client()
    try:
        await client.admin.command("ping")
    except Exception:
        pytest.skip("MongoDB not reachable")
    database = client[settings.mongodb_database]
    yield database
    await database[EXAM_SCHEDULES_COLLECTION].delete_many(
        {"source_file": "itest_exam.xlsx"}
    )
    await close_motor_client()


def _workbook(path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for row in DATA:
        ws.append(row)
    wb.save(path)


@pytest.mark.asyncio
async def test_ingest_and_reupload_idempotent(tmp_path, settings, db, es_store) -> None:
    path = tmp_path / "itest_exam.xlsx"
    _workbook(path)

    resp = await ingest_exam_schedule(
        path=str(path), settings=settings, db=db,
        source_file="itest_exam.xlsx", es_store=es_store,
    )
    assert resp.parsed == 2
    assert resp.records_indexed == 2

    mongo_count = await db[EXAM_SCHEDULES_COLLECTION].count_documents(
        {"source_file": "itest_exam.xlsx"}
    )
    assert mongo_count == 2
    assert es_store.count() == 2

    # Re-upload: counts stay stable, replaced_existing flips True.
    resp2 = await ingest_exam_schedule(
        path=str(path), settings=settings, db=db,
        source_file="itest_exam.xlsx", es_store=es_store,
    )
    assert resp2.replaced_existing is True
    mongo_count2 = await db[EXAM_SCHEDULES_COLLECTION].count_documents(
        {"source_file": "itest_exam.xlsx"}
    )
    assert mongo_count2 == 2
    assert es_store.count() == 2

    rows = es_store.search(subject_code="CH1012")
    assert rows and rows[0]["exam_room"] == "D3-201"
    assert rows[0]["exam_date"] == "2026-05-09"
    assert datetime.strptime(rows[0]["exam_date"], "%Y-%m-%d")
