"""ExamScheduleRecord — one parsed row of a HUST exam-schedule file.

Exam schedules are structured/tabular data. Each row becomes one
``ExamScheduleRecord`` (one exam slot) which is stored in the Mongo
``exam_schedules`` collection and indexed into a dedicated Elasticsearch index
for filtered/full-text lookups (see ``retrieval/exam_schedule_store.py``).

The model is pure data + pure transform helpers (``from_parsed_row``,
``to_mongo``, ``to_es``) — no I/O — so it is trivially unit-testable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ExamScheduleRecord(BaseModel):
    """A single exam slot parsed from one source row.

    Idempotency key is ``(source_file, row_index)``: re-uploading the same file
    replaces the prior rows rather than duplicating them.
    """

    # Provenance / idempotency
    source_file: str
    source_doc_id: str | None = None
    row_index: int

    # Subject identity
    subject_code: str  # Mã HP, e.g. "CH1012"
    subject_name: str = ""  # Tên học phần
    mgmt_class_code: str = ""  # Mã lớp QT
    exam_class_code: str = ""  # Mã lớp thi
    note: str = ""  # Ghi chú

    # Grouping / cohort
    group: str = ""  # Nhóm, e.g. "02,04-K70C"
    cohort: str | None = None  # extracted from group/note, e.g. "K70C"

    # When
    exam_week: str = ""  # Tuần thi, e.g. "Tuần 35"
    weekday: str = ""  # Thứ, e.g. "Thứ bảy"
    exam_date: datetime | None = None  # parsed date (date-only, midnight)
    exam_date_str: str = ""  # display "DD/MM/YYYY"
    exam_session: str = ""  # Kíp thi, e.g. "Kíp 1"
    start_time: str | None = None  # from the Kíp→time map

    # Where / how many
    exam_room: str = ""  # Phòng thi, e.g. "D3-201"
    student_count: int | None = None  # SL
    exam_batch: str = ""  # Đợt, e.g. "AB"

    # Original cell values for debugging / future fields
    raw: dict[str, Any] = Field(default_factory=dict)

    # Audit
    uploaded_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_parsed_row(
        cls,
        fields: dict[str, Any],
        *,
        row_index: int,
        source_file: str,
        source_doc_id: str | None = None,
        uploaded_by: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> "ExamScheduleRecord":
        """Build a record from a parser-produced canonical ``fields`` dict.

        ``fields`` uses the canonical field names (``subject_code``,
        ``exam_date``, ``start_time``, …) already normalised by the parser.
        Unknown keys are ignored; missing keys fall back to model defaults.
        """
        known = set(cls.model_fields.keys())
        payload = {key: value for key, value in fields.items() if key in known}
        payload.update(
            row_index=row_index,
            source_file=source_file,
            source_doc_id=source_doc_id,
            uploaded_by=uploaded_by,
            raw=dict(raw or {}),
        )
        return cls(**payload)

    def to_mongo(self) -> dict[str, Any]:
        """Serialise for MongoDB ``insert_many`` (keeps native datetime)."""
        return self.model_dump()

    def to_es(self) -> dict[str, Any]:
        """Serialise for the exam Elasticsearch index.

        ``exam_date`` is emitted as ISO ``yyyy-MM-dd`` (no time/zone) so the ES
        ``date`` field parses unambiguously; ``search_text`` concatenates the
        most useful free-text fields for BM25 fallback. ``raw`` and audit
        timestamps are dropped — they are not searchable.
        """
        doc: dict[str, Any] = {
            "source_file": self.source_file,
            "row_index": self.row_index,
            "subject_code": self.subject_code,
            "subject_name": self.subject_name,
            "mgmt_class_code": self.mgmt_class_code,
            "exam_class_code": self.exam_class_code,
            "note": self.note,
            "group": self.group,
            "cohort": self.cohort,
            "exam_week": self.exam_week,
            "weekday": self.weekday,
            "exam_date_str": self.exam_date_str,
            "exam_session": self.exam_session,
            "start_time": self.start_time,
            "exam_room": self.exam_room,
            "student_count": self.student_count,
            "exam_batch": self.exam_batch,
            "search_text": " ".join(
                part
                for part in (self.subject_name, self.subject_code, self.exam_room)
                if part
            ),
        }
        if self.exam_date is not None:
            doc["exam_date"] = self.exam_date.strftime("%Y-%m-%d")
        return doc
