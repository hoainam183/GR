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
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.rbac import require_admin
from config.settings import Settings
from models.database import get_database
from models.user import UserDocument
from schemas.exam_schedule import ExamScheduleUploadResponse
from services.exam_schedule_service import ingest_exam_schedule

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_ALLOWED_SUFFIXES = (".pdf", ".xlsx", ".xlsm")


def _save_upload(content: bytes, upload_dir: str, doc_id: str, suffix: str) -> str:
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
