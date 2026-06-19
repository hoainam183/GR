"""Unit tests for ExamScheduleRecord transforms (from_parsed_row/to_mongo/to_es)."""

from __future__ import annotations

from datetime import datetime

from models.exam_schedule import ExamScheduleRecord


def _fields() -> dict:
    return {
        "subject_code": "CH1012",
        "subject_name": "Hóa học 1",
        "mgmt_class_code": "CK166692",
        "exam_class_code": "200985",
        "note": "Vật liệu",
        "group": "02,04-K70C",
        "cohort": "K70C",
        "exam_week": "Tuần 35",
        "weekday": "Thứ bảy",
        "exam_date": datetime(2026, 5, 9),
        "exam_date_str": "09/05/2026",
        "exam_session": "Kíp 1",
        "start_time": "07:00",
        "exam_room": "D3-201",
        "student_count": 15,
        "exam_batch": "AB",
    }


def test_from_parsed_row_populates_record() -> None:
    rec = ExamScheduleRecord.from_parsed_row(
        _fields(), row_index=3, source_file="ck.pdf", uploaded_by="u1"
    )
    assert rec.subject_code == "CH1012"
    assert rec.row_index == 3
    assert rec.source_file == "ck.pdf"
    assert rec.cohort == "K70C"
    assert rec.student_count == 15


def test_from_parsed_row_ignores_unknown_keys() -> None:
    fields = _fields()
    fields["totally_unknown"] = "x"
    rec = ExamScheduleRecord.from_parsed_row(fields, row_index=0, source_file="f.pdf")
    assert not hasattr(rec, "totally_unknown")


def test_to_es_emits_iso_date_and_search_text() -> None:
    rec = ExamScheduleRecord.from_parsed_row(_fields(), row_index=0, source_file="f.pdf")
    es = rec.to_es()
    assert es["exam_date"] == "2026-05-09"  # ISO, not display
    assert es["exam_date_str"] == "09/05/2026"
    assert "CH1012" in es["search_text"] and "Hóa học 1" in es["search_text"]
    assert "raw" not in es and "created_at" not in es


def test_to_es_omits_date_when_unparsed() -> None:
    fields = _fields()
    fields["exam_date"] = None
    rec = ExamScheduleRecord.from_parsed_row(fields, row_index=0, source_file="f.pdf")
    assert "exam_date" not in rec.to_es()


def test_raw_default_is_not_shared_between_instances() -> None:
    a = ExamScheduleRecord.from_parsed_row(_fields(), row_index=0, source_file="f.pdf")
    b = ExamScheduleRecord.from_parsed_row(_fields(), row_index=1, source_file="f.pdf")
    a.raw["x"] = 1
    assert b.raw == {}  # no mutable-default aliasing


def test_to_mongo_keeps_native_datetime() -> None:
    rec = ExamScheduleRecord.from_parsed_row(_fields(), row_index=0, source_file="f.pdf")
    doc = rec.to_mongo()
    assert isinstance(doc["exam_date"], datetime)
    assert doc["source_file"] == "f.pdf"
