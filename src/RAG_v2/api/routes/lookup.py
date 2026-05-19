"""Lookup API routes backed by existing retrieval stores."""

from __future__ import annotations

from typing import Annotated, Any

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth.jwt_handler import get_optional_current_user
from models.user import UserDocument

router = APIRouter(prefix="/lookup", tags=["lookup"])


def _get_retrieval_service(request: Request) -> Any | None:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        return None
    return getattr(pipeline, "retrieval_service", None) or getattr(
        pipeline, "_retrieval_service", None
    )


def _doc_title(doc: dict[str, Any]) -> str:
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    for key in ("title", "doc_title", "section_h2", "section_h1", "source"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Tài liệu liên quan"


def _serialize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    text = str(doc.get("text") or doc.get("content") or "")
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    return {
        "title": _doc_title(doc),
        "summary": text[:700],
        "source": metadata.get("source") or metadata.get("file_name"),
        "date": metadata.get("date_str") or metadata.get("date"),
        "url": metadata.get("url"),
        "collection": doc.get("collection"),
        "score": float(doc.get("rerank_score", doc.get("score", 0.0)) or 0.0),
        "metadata": metadata,
    }


async def _search(
    request: Request,
    query: str,
    *,
    collections: list[str],
    top_k: int,
    resolved_major: str | None = None,
    resolved_cohort: str | None = None,
) -> list[dict[str, Any]]:
    service = _get_retrieval_service(request)
    if service is None:
        return []
    try:
        docs = await anyio.to_thread.run_sync(
            lambda: service.search(
                query,
                collections=collections,
                top_k=top_k,
                resolved_major=resolved_major,
                resolved_cohort=resolved_cohort,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Lookup search failed: {exc}") from exc
    return [_serialize_doc(doc) for doc in docs]


@router.get("/ctdt/{major_code}")
async def lookup_ctdt(
    request: Request,
    major_code: str,
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
    cohort: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=30),
) -> dict[str, Any]:
    """Lookup curriculum documents for a major code."""
    resolved_cohort = cohort or (current_user.cohort if current_user else None)
    docs = await _search(
        request,
        f"chương trình đào tạo {major_code} các học phần tín chỉ",
        collections=["ctdt"],
        top_k=limit,
        resolved_major=major_code,
        resolved_cohort=resolved_cohort,
    )
    return {
        "major_code": major_code,
        "cohort": resolved_cohort,
        "program_name": docs[0]["title"] if docs else "",
        "documents": docs,
    }


@router.get("/regulations")
async def lookup_regulations(
    request: Request,
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
    category: str | None = Query(default=None),
    cohort: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=30),
) -> dict[str, Any]:
    """Lookup regulations by topic/category and optional cohort."""
    resolved_cohort = cohort or (current_user.cohort if current_user else None)
    topic = category or "quy định học vụ sinh viên"
    docs = await _search(
        request,
        f"quy định {topic} {resolved_cohort or ''}",
        collections=["quydinh"],
        top_k=limit,
        resolved_cohort=resolved_cohort,
    )
    return {"category": category, "cohort": resolved_cohort, "regulations": docs}


@router.get("/calendar")
async def lookup_calendar(
    request: Request,
    semester: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=30),
) -> dict[str, Any]:
    """Lookup academic calendar and deadline announcements."""
    query = f"lịch kế hoạch học tập deadline đăng ký {semester or ''}"
    docs = await _search(
        request,
        query,
        collections=["kehoach"],
        top_k=limit,
    )
    return {"semester": semester, "events": docs}


@router.get("/compare")
async def lookup_compare(
    request: Request,
    topic: str = Query(..., min_length=1),
    cohort1: str = Query(..., min_length=1),
    cohort2: str = Query(..., min_length=1),
) -> dict[str, Any]:
    """Compare a regulation topic between two cohorts using the RAG pipeline."""
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        return {
            "comparison": {
                "topic": topic,
                "cohort1": cohort1,
                "cohort2": cohort2,
                "answer": "",
                "sources": [],
            }
        }

    question = f"So sánh quy định về {topic} giữa {cohort1} và {cohort2}"
    result = await anyio.to_thread.run_sync(
        lambda: pipeline.query_v3(question=question, top_k=8)
    )
    return {
        "comparison": {
            "topic": topic,
            "cohort1": cohort1,
            "cohort2": cohort2,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
        }
    }
