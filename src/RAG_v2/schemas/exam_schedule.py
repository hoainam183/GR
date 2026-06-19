"""Pydantic DTOs for the exam-schedule (lịch thi) ingestion endpoint and tool.

Kept separate from ``models.exam_schedule`` (the storage record) so the HTTP
contract can evolve independently of the persisted shape.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SkippedRow(BaseModel):
    """A source row that was parsed but not stored, with the reason."""

    row_index: int
    reason: str  # "no_subject" | "invalid_date" | ...


class ParseReport(BaseModel):
    """Summary of a single file parse."""

    total_rows: int = 0
    valid_rows: int = 0
    skipped_rows: list[SkippedRow] = Field(default_factory=list)


class ExamScheduleUploadResponse(BaseModel):
    """Response for ``POST /admin/exam-schedules``."""

    source_file: str
    parsed: int  # rows that produced a valid record
    skipped: int  # rows skipped (see report.skipped_rows)
    invalid: int  # alias for skipped count (rows that failed validation)
    replaced_existing: bool  # True when prior rows for source_file were removed
    records_indexed: int  # docs written to Elasticsearch
    report: ParseReport


class ExamScheduleSourceSummary(BaseModel):
    """Per-source-file statistics in the current DB state."""

    source_file: str
    row_count: int
    latest_uploaded_at: datetime | None = None


class ExamScheduleSummary(BaseModel):
    """Snapshot of the ``exam_schedules`` Mongo collection.

    Returned by ``GET /admin/exam-schedules/summary`` so admins can verify a
    just-uploaded file actually landed in the database, independent of the
    upload response.
    """

    total_rows: int
    distinct_subjects: int
    distinct_exam_dates: int
    sources: list[ExamScheduleSourceSummary] = Field(default_factory=list)


class ExamScheduleQuery(BaseModel):
    """Tool-internal structured query DTO (not part of the HTTP surface)."""

    model_config = ConfigDict(extra="forbid")

    subject_code: str | None = None
    subject_name: str | None = None
    exam_date: str | None = None  # ISO "yyyy-MM-dd" or display "dd/mm/yyyy"
    exam_room: str | None = None
    group: str | None = None
    limit: int | None = None
