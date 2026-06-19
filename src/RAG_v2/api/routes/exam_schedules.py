"""Admin endpoint for uploading exam-schedule (lịch thi) files.

Unlike ``/admin/documents`` (a convert→clean→chunk→embed state machine for
prose PDFs), exam schedules are parsed synchronously into structured rows and
replace prior rows in Mongo + Elasticsearch. Accepts the institution's PDF
timetable and Excel exports of the same 13-column schema. Returns **201 + a
ParseReport** so the admin sees immediately how many rows were stored / skipped.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.rbac import require_admin
from config.settings import Settings
from models.database import EXAM_SCHEDULES_COLLECTION, get_database
from models.user import UserDocument
from schemas.exam_schedule import (
    ExamScheduleSourceSummary,
    ExamScheduleSummary,
    ExamScheduleUploadResponse,
)
from services.exam_schedule_service import (
    delete_exam_schedule_source,
    ingest_exam_schedule,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_ALLOWED_SUFFIXES = (".pdf", ".xlsx", ".xlsm")


def _save_upload(
    content: bytes, upload_dir: str, doc_id: str, suffix: str
) -> str:
    """Persist the uploaded file to disk and return the absolute path."""
    dest_dir = Path(upload_dir) / "exam_schedules"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{doc_id}{suffix}"
    dest.write_bytes(content)
    return str(dest)


@router.post(
    "/exam-schedules",
    status_code=status.HTTP_201_CREATED,
    response_model=ExamScheduleUploadResponse,
)
async def upload_exam_schedule(
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    file: UploadFile = File(...),
) -> ExamScheduleUploadResponse:
    """Upload one exam-schedule ``.pdf``/``.xlsx``; parse, replace, and index its rows."""
    settings = Settings()

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only {', '.join(_ALLOWED_SUFFIXES)} files are allowed. "
                f"Got: {file.filename!r}"
            ),
        )

    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    doc_id = str(ObjectId())
    saved_path = _save_upload(content, settings.upload_dir, doc_id, suffix)

    try:
        return await ingest_exam_schedule(
            path=saved_path,
            settings=settings,
            db=db,
            source_file=file.filename or f"{doc_id}{suffix}",
            source_doc_id=doc_id,
            uploaded_by=str(user.id),
        )
    except ValueError as exc:
        # Unreadable / not a recognisable exam file (no header row, etc.).
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _aggregate_sources(
    collection: Any,
) -> list[ExamScheduleSourceSummary]:
    """Return per-source-file counts + latest upload time, newest first."""
    pipeline = [
        {
            "$group": {
                "_id": "$source_file",
                "row_count": {"$sum": 1},
                "latest_uploaded_at": {"$max": "$created_at"},
            }
        },
        {"$sort": {"latest_uploaded_at": -1, "_id": 1}},
    ]
    sources: list[ExamScheduleSourceSummary] = []
    async for doc in collection.aggregate(pipeline):
        sources.append(
            ExamScheduleSourceSummary(
                source_file=doc["_id"] or "(unknown)",
                row_count=int(doc.get("row_count") or 0),
                latest_uploaded_at=doc.get("latest_uploaded_at"),
            )
        )
    return sources


@router.get(
    "/exam-schedules/summary",
    response_model=ExamScheduleSummary,
)
async def get_exam_schedule_summary(
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ExamScheduleSummary:
    """Snapshot of the current ``exam_schedules`` collection.

    Lets the admin UI confirm — after an upload — that rows actually landed in
    MongoDB (the source of truth). Read-only, no side effects.
    """
    del user  # auth-only dependency
    collection = db[EXAM_SCHEDULES_COLLECTION]

    total_rows = await collection.count_documents({})
    if total_rows == 0:
        return ExamScheduleSummary(
            total_rows=0,
            distinct_subjects=0,
            distinct_exam_dates=0,
            sources=[],
        )

    subjects = await collection.distinct("subject_code")
    exam_dates = await collection.distinct("exam_date")
    sources = await _aggregate_sources(collection)

    return ExamScheduleSummary(
        total_rows=total_rows,
        distinct_subjects=len([s for s in subjects if s]),
        distinct_exam_dates=len([d for d in exam_dates if d is not None]),
        sources=sources,
    )


@router.delete(
    "/exam-schedules",
    status_code=status.HTTP_200_OK,
)
async def delete_exam_schedule(
    user: Annotated[UserDocument, Depends(require_admin)],
    source_file: Annotated[
        str,
        Query(min_length=1, description="Original file name as shown in the DB panel"),
    ],
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    """Remove all rows for one uploaded exam-schedule file (Mongo + ES + disk).

    Idempotent: deleting a non-existent ``source_file`` returns zero counts
    instead of 404 so the admin UI can stay simple.
    """
    del user  # auth-only dependency
    settings = Settings()
    counts = await delete_exam_schedule_source(
        source_file=source_file,
        settings=settings,
        db=db,
    )
    return {
        "detail": "Exam schedule deleted",
        "source_file": source_file,
        **counts,
    }
