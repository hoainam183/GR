"""Pydantic DTOs for the exam-schedule (lịch thi) ingestion endpoint and tool.

Kept separate from ``models.exam_schedule`` (the storage record) so the HTTP
contract can evolve independently of the persisted shape.
"""

from __future__ import annotations

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


class ExamScheduleQuery(BaseModel):
    """Tool-internal structured query DTO (not part of the HTTP surface)."""

    model_config = ConfigDict(extra="forbid")

    subject_code: str | None = None
    subject_name: str | None = None
    exam_date: str | None = None  # ISO "yyyy-MM-dd" or display "dd/mm/yyyy"
    exam_room: str | None = None
    group: str | None = None
    limit: int | None = None
