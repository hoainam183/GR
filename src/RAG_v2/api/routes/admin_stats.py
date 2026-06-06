"""Admin Observability Center — statistics and management endpoints.

Provides dashboards data for:
- System overview (KPIs)
- User management (list, search, deactivate)
- Query analytics (volumes, latency, routing)
- Agent analytics (tool usage, iterations)
- Feedback topics
- System status (config, cache, documents, crawler)

All endpoints require admin role via ``require_admin``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from auth.rbac import require_admin
from models.crawler import (
    CRAWLER_EDITABLE_STATUSES,
    CRAWLER_INDEXABLE_STATUSES,
    CRAWLER_STATUS_INDEX_FAILED,
    CRAWLER_STATUS_INDEXED,
    CRAWLER_STATUS_INDEXING,
    CRAWLER_STATUS_PENDING_REVIEW,
)
from models.database import (
    CRAWLER_CHUNKS_COLLECTION,
    CRAWLER_RUNS_COLLECTION,
    get_database,
)
from models.system_config import (
    API_KEY_SETTING_FIELDS,
    ApiKeyRegistryError,
    activate_api_key,
    create_api_key,
    filter_llm_config_updates,
    get_api_key_record,
    list_api_keys,
    merge_llm_config_into_settings,
    upsert_llm_config,
)
from models.user import UserDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-stats"])

# ═══════════════════════════════════════════════════════════════════════════════
# MongoDB version check (for $percentile support)
# ═══════════════════════════════════════════════════════════════════════════════

_MONGO_SUPPORTS_PERCENTILE: bool = False


async def check_mongo_version(db: AsyncIOMotorDatabase):
    """Check MongoDB version at startup for feature gating."""
    global _MONGO_SUPPORTS_PERCENTILE
    try:
        info = await db.command("buildInfo")
        major = int(info["versionArray"][0])
        _MONGO_SUPPORTS_PERCENTILE = major >= 7
        logger.info("MongoDB version %s — $percentile support: %s",
                    info.get("version"), _MONGO_SUPPORTS_PERCENTILE)
    except Exception:
        _MONGO_SUPPORTS_PERCENTILE = False


# ═══════════════════════════════════════════════════════════════════════════════
# Crawler management state
# ═══════════════════════════════════════════════════════════════════════════════

_crawl_lock = threading.Lock()
_crawl_running = False
_last_manual_crawl: dict | None = None
_CRAWL_TIMEOUT_SECONDS = 600  # 10 minutes max
_last_trigger_time: float = 0
_CRAWL_COOLDOWN_SECONDS = 60  # minimum 1 minute between triggers

_crawl_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="crawl")


def _jsonify_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _has_pending_review(value: Any) -> bool:
    if isinstance(value, dict):
        status = value.get("review_status") or value.get("status")
        if status in {CRAWLER_STATUS_PENDING_REVIEW, CRAWLER_STATUS_INDEX_FAILED}:
            return True
        return any(_has_pending_review(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_pending_review(item) for item in value)
    return False


def _has_crawler_error(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("status") in {"error", "timeout"}:
            return True
        return any(_has_crawler_error(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_crawler_error(item) for item in value)
    return False


def _crawl_result_status(result: Any) -> str:
    if _has_pending_review(result):
        return "pending_review"
    if _has_crawler_error(result):
        return "error"
    return "success"


def _serialize_crawler_chunk(doc: dict[str, Any], *, include_content: bool = True) -> dict[str, Any]:
    metadata = doc.get("metadata") or {}
    content = str(doc.get("content") or "")
    payload = {
        "run_id": str(doc.get("run_id") or ""),
        "chunk_id": str(doc.get("chunk_id") or ""),
        "chunk_index": int(doc.get("chunk_index") or 0),
        "title": str(metadata.get("title") or ""),
        "source": str(metadata.get("source") or ""),
        "url": str(metadata.get("url") or ""),
        "section_label": str(metadata.get("section_label") or ""),
        "metadata": metadata,
        "content_preview": " ".join(content.split())[:280],
        "content_length": len(content),
        "edited": bool(doc.get("edited", False)),
        "index_status": str(doc.get("index_status") or "pending"),
        "created_at": _jsonify_datetime(doc.get("created_at")),
        "updated_at": _jsonify_datetime(doc.get("updated_at")),
    }
    if include_content:
        payload["content"] = content
    return payload


def _serialize_crawler_run(doc: dict[str, Any], saved_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    status = str(doc.get("status") or "unknown")
    return {
        "review_run_id": str(doc.get("run_id") or ""),
        "run_id": str(doc.get("run_id") or ""),
        "collection": str(doc.get("collection") or ""),
        "pipeline": str(doc.get("pipeline") or ""),
        "status": status,
        "review_status": status,
        "can_edit": status in CRAWLER_EDITABLE_STATUSES,
        "can_index": status in CRAWLER_INDEXABLE_STATUSES,
        "new_articles": int(doc.get("new_articles") or 0),
        "new_chunks": int(doc.get("new_chunks") or 0),
        "indexed": int(doc.get("indexed") or 0),
        "expired_removed": int(doc.get("expired_removed") or 0),
        "saved_chunks": saved_chunks,
        "created_at": _jsonify_datetime(doc.get("created_at")),
        "updated_at": _jsonify_datetime(doc.get("updated_at")),
        "indexed_at": _jsonify_datetime(doc.get("indexed_at")),
        "error_message": doc.get("error_message"),
    }


async def _crawler_run_with_preview(
    db: AsyncIOMotorDatabase,
    run_doc: dict[str, Any],
    *,
    chunk_limit: int = 5,
) -> dict[str, Any]:
    cursor = (
        db[CRAWLER_CHUNKS_COLLECTION]
        .find({"run_id": run_doc["run_id"]})
        .sort("chunk_index", 1)
        .limit(chunk_limit)
    )
    chunk_docs = await cursor.to_list(length=chunk_limit)
    previews = [
        _serialize_crawler_chunk(doc, include_content=False)
        for doc in chunk_docs
    ]
    return _serialize_crawler_run(run_doc, previews)


async def _list_crawler_runs(
    db: AsyncIOMotorDatabase,
    *,
    statuses: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if statuses:
        query["status"] = {"$in": statuses}
    cursor = (
        db[CRAWLER_RUNS_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [
        await _crawler_run_with_preview(db, doc)
        for doc in docs
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Request/Response schemas
# ═══════════════════════════════════════════════════════════════════════════════


class UserStatusBody(BaseModel):
    is_active: bool


class ConfigToggleBody(BaseModel):
    key: str
    value: bool


class LLMConfigBody(BaseModel):
    llm_provider: str | None = None
    deepseek_api_key: str | None = None
    google_api_key: str | None = None
    chat_model: str | None = None
    chat_temperature: float | None = None
    chat_max_tokens: int | None = None
    agent_enabled: bool | None = None
    agent_model: str | None = None
    self_eval_enabled: bool | None = None
    tavily_fallback_enabled: bool | None = None
    tavily_api_key: str | None = None
    reflection_enabled: bool | None = None
    reflection_model: str | None = None


class ApiKeyCreateBody(BaseModel):
    provider: str
    name: str
    key: str


class CrawlerChunkUpdateBody(BaseModel):
    content: str


_LLM_CACHE_INVALIDATION_FIELDS = {
    "llm_provider",
    "chat_model",
    "chat_temperature",
    "chat_max_tokens",
}


# ═══════════════════════════════════════════════════════════════════════════════
# EP1: Overview stats
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/stats/overview")
async def get_overview_stats(
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Return high-level KPI stats for the admin dashboard."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    total_users, total_sessions, total_queries, active_users_7d, total_feedback, avg_satisfaction = (
        await asyncio.gather(
            db.users.count_documents({}),
            db.sessions.count_documents({}),
            db.query_logs.count_documents({}),
            db.users.count_documents({"last_login_at": {"$gte": seven_days_ago}}),
            db.feedback.count_documents({}),
            _get_satisfaction_rate(db),
        )
    )

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_queries": total_queries,
        "active_users_7d": active_users_7d,
        "total_feedback": total_feedback,
        "satisfaction_rate": avg_satisfaction,
    }


async def _get_satisfaction_rate(db: AsyncIOMotorDatabase) -> float | None:
    """Calculate satisfaction rate as % of 'up' ratings."""
    pipeline = [
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "up": {"$sum": {"$cond": [{"$eq": ["$rating", "up"]}, 1, 0]}},
        }},
    ]
    result = await db.feedback.aggregate(pipeline).to_list(1)
    if not result or result[0]["total"] == 0:
        return None
    return round(result[0]["up"] / result[0]["total"] * 100, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# EP2: User list with session/query counts
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/stats/users")
async def get_admin_users(
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    days: int | None = Query(None, ge=1, le=365),
):
    """Return paginated user list with session and query counts."""
    # Build match filter
    match_filter: dict[str, Any] = {}
    if search:
        match_filter["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"student_id": {"$regex": search, "$options": "i"}},
        ]
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        match_filter["last_login_at"] = {"$gte": cutoff}

    # Sort direction
    sort_dir = -1 if order == "desc" else 1
    allowed_sorts = {"created_at", "last_login_at", "full_name", "email", "session_count", "query_count"}
    if sort_by not in allowed_sorts:
        sort_by = "created_at"

    pipeline: list[dict] = []

    # Match stage
    if match_filter:
        pipeline.append({"$match": match_filter})

    # Convert ObjectId to string for $lookup join
    pipeline.append({"$addFields": {"_id_str": {"$toString": "$_id"}}})

    # Lookup session count
    pipeline.append({
        "$lookup": {
            "from": "sessions",
            "localField": "_id_str",
            "foreignField": "user_id",
            "pipeline": [{"$count": "n"}],
            "as": "_sessions",
        }
    })

    # Lookup query count
    pipeline.append({
        "$lookup": {
            "from": "query_logs",
            "localField": "_id_str",
            "foreignField": "user_id",
            "pipeline": [{"$count": "n"}],
            "as": "_queries",
        }
    })

    # Compute counts
    pipeline.append({
        "$addFields": {
            "session_count": {"$ifNull": [{"$first": "$_sessions.n"}, 0]},
            "query_count": {"$ifNull": [{"$first": "$_queries.n"}, 0]},
        }
    })

    # Clean up temp fields
    pipeline.append({"$project": {"_id_str": 0, "_sessions": 0, "_queries": 0, "password_hash": 0}})

    # Use $facet for pagination + total count
    pipeline.append({
        "$facet": {
            "data": [
                {"$sort": {sort_by: sort_dir}},
                {"$skip": (page - 1) * limit},
                {"$limit": limit},
            ],
            "total": [{"$count": "count"}],
        }
    })

    result = await db.users.aggregate(pipeline).to_list(1)
    if not result:
        return {"users": [], "total": 0, "page": page, "limit": limit}

    facet = result[0]
    users = facet.get("data", [])
    total_count = facet["total"][0]["count"] if facet.get("total") else 0

    # Serialize ObjectId
    for u in users:
        if "_id" in u:
            u["_id"] = str(u["_id"])

    return {"users": users, "total": total_count, "page": page, "limit": limit}


# ═══════════════════════════════════════════════════════════════════════════════
# EP3: User breakdown (role, registration trend)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/stats/users/breakdown")
async def get_user_breakdown(
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    days: int = Query(30, ge=1, le=365),
):
    """Return user role distribution and daily registration trend."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Role distribution
    role_pipeline = [
        {"$group": {"_id": "$role", "count": {"$sum": 1}}},
    ]

    # Daily registrations
    reg_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": {"$dateToString": {"date": "$created_at", "format": "%Y-%m-%d"}},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]

    roles, registrations = await asyncio.gather(
        db.users.aggregate(role_pipeline).to_list(10),
        db.users.aggregate(reg_pipeline).to_list(365),
    )

    return {
        "by_role": {r["_id"]: r["count"] for r in roles if r["_id"]},
        "registrations": [{"date": r["_id"], "count": r["count"]} for r in registrations],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EP4: Query analytics
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/stats/queries")
async def get_query_analytics(
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    days: int = Query(30, ge=1, le=365),
    top_questions_limit: int = Query(15, ge=5, le=50),
):
    """Return query volume, latency, routing breakdown, and top questions."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    base_match = {"timestamp": {"$gte": cutoff}}

    # Daily query volume
    volume_pipeline = [
        {"$match": base_match},
        {"$group": {
            "_id": {"$dateToString": {"date": "$timestamp", "format": "%Y-%m-%d"}},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]

    # Latency trend
    latency_group: dict[str, Any] = {
        "_id": {"$dateToString": {"date": "$timestamp", "format": "%Y-%m-%d"}},
        "avg_ms": {"$avg": "$latency_ms"},
    }
    if _MONGO_SUPPORTS_PERCENTILE:
        latency_group["p95_ms"] = {
            "$percentile": {"input": "$latency_ms", "p": [0.95], "method": "approximate"}
        }

    latency_pipeline = [
        {"$match": {**base_match, "latency_ms": {"$exists": True, "$ne": None}}},
        {"$group": latency_group},
        {"$sort": {"_id": 1}},
    ]

    # Intent/route distribution
    route_pipeline = [
        {"$match": base_match},
        {"$group": {"_id": "$route", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]

    mode_pipeline = [
        {"$match": base_match},
        {"$group": {"_id": "$mode", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]

    # Top questions
    top_q_pipeline = [
        {"$match": base_match},
        {"$group": {"_id": "$question", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": top_questions_limit},
    ]

    # Error count
    error_pipeline = [
        {"$match": {**base_match, "error": {"$exists": True, "$ne": None}}},
        {"$count": "count"},
    ]

    volume, latency, routes, modes, top_questions, errors = await asyncio.gather(
        db.query_logs.aggregate(volume_pipeline).to_list(365),
        db.query_logs.aggregate(latency_pipeline).to_list(365),
        db.query_logs.aggregate(route_pipeline).to_list(20),
        db.query_logs.aggregate(mode_pipeline).to_list(10),
        db.query_logs.aggregate(top_q_pipeline).to_list(top_questions_limit),
        db.query_logs.aggregate(error_pipeline).to_list(1),
    )

    # Process latency (p95 is array from $percentile)
    for entry in latency:
        if "p95_ms" in entry and isinstance(entry["p95_ms"], list):
            entry["p95_ms"] = entry["p95_ms"][0] if entry["p95_ms"] else None
        if "avg_ms" in entry and entry["avg_ms"] is not None:
            entry["avg_ms"] = round(entry["avg_ms"], 1)
        if "p95_ms" in entry and entry["p95_ms"] is not None:
            entry["p95_ms"] = round(entry["p95_ms"], 1)

    return {
        "volume": [{"date": v["_id"], "count": v["count"]} for v in volume],
        "latency": [
            {"date": l["_id"], "avg_ms": l.get("avg_ms"), "p95_ms": l.get("p95_ms")}
            for l in latency
        ],
        "by_route": [{"route": r["_id"] or "unknown", "count": r["count"]} for r in routes],
        "by_mode": [{"mode": m["_id"] or "unknown", "count": m["count"]} for m in modes],
        "top_questions": [{"question": q["_id"], "count": q["count"]} for q in top_questions],
        "error_count": errors[0]["count"] if errors else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EP5: Agent analytics
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/stats/agent")
async def get_agent_analytics(
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    days: int = Query(30, ge=1, le=365),
):
    """Return agent usage statistics."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    base_match = {"created_at": {"$gte": cutoff}}

    # Overall agent stats
    stats_pipeline = [
        {"$match": base_match},
        {"$group": {
            "_id": None,
            "total_calls": {"$sum": 1},
            "avg_iterations": {"$avg": "$iterations"},
            "errors": {"$sum": {"$cond": [{"$ne": [{"$ifNull": ["$error", None]}, None]}, 1, 0]}},
            "tavily_uses": {"$sum": {"$cond": [{"$in": ["web_search", {"$ifNull": ["$tool_names_sequence", []]}]}, 1, 0]}},
        }},
    ]

    # Tool frequency
    tool_pipeline = [
        {"$match": base_match},
        {"$unwind": {"path": "$tool_names_sequence", "preserveNullAndEmptyArrays": False}},
        {"$group": {"_id": "$tool_names_sequence", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]

    # Daily usage
    daily_pipeline = [
        {"$match": base_match},
        {"$group": {
            "_id": {"$dateToString": {"date": "$created_at", "format": "%Y-%m-%d"}},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]

    stats, tools, daily = await asyncio.gather(
        db.agent_traces.aggregate(stats_pipeline).to_list(1),
        db.agent_traces.aggregate(tool_pipeline).to_list(20),
        db.agent_traces.aggregate(daily_pipeline).to_list(365),
    )

    s = stats[0] if stats else {}
    total_calls = s.get("total_calls", 0)

    return {
        "total_calls": total_calls,
        "avg_iterations": round(s.get("avg_iterations", 0), 1) if s.get("avg_iterations") else 0,
        "error_rate": round(s.get("errors", 0) / total_calls * 100, 1) if total_calls > 0 else 0,
        "tavily_triggers": s.get("tavily_uses", 0),
        "tool_frequency": [{"tool": t["_id"], "count": t["count"]} for t in tools],
        "daily_usage": [{"date": d["_id"], "count": d["count"]} for d in daily],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EP6: Feedback topics
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/stats/feedback/topics")
async def get_feedback_topics(
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=5, le=50),
):
    """Return disliked question topics grouped by category."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"rating": "down", "created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": {"question": "$question", "category": "$category"},
            "count": {"$sum": 1},
            "last_at": {"$max": "$created_at"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]

    results = await db.feedback.aggregate(pipeline).to_list(limit)

    return {
        "topics": [
            {
                "question": r["_id"]["question"],
                "category": r["_id"].get("category"),
                "count": r["count"],
                "last_at": r["last_at"].isoformat() if r.get("last_at") else None,
            }
            for r in results
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EP7: System status
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/stats/system")
async def get_system_stats(
    request: Request,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Return system configuration and resource status."""
    settings = request.app.state.settings

    # Document counts by status
    doc_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]

    # Document counts by collection
    doc_collection_pipeline = [
        {"$group": {"_id": "$collection", "count": {"$sum": 1}}},
    ]

    doc_status, doc_collections = await asyncio.gather(
        db.documents.aggregate(doc_pipeline).to_list(20),
        db.documents.aggregate(doc_collection_pipeline).to_list(10),
    )

    # Redis cache info
    cache_info = None
    llm_cache = getattr(request.app.state, "llm_cache", None)
    if llm_cache and hasattr(llm_cache, "stats"):
        try:
            cache_info = await llm_cache.stats()
        except Exception:
            pass

    return {
        "config": {
            "agent_enabled": settings.agent_enabled,
            "self_eval_enabled": settings.self_eval_enabled,
            "tavily_fallback_enabled": settings.tavily_fallback_enabled,
            "crawler_enabled": settings.crawler_enabled,
            "redis_enabled": settings.redis_enabled,
            "mongodb_enabled": settings.mongodb_enabled,
        },
        "mongo_status": getattr(request.app.state, "mongo_status", "unknown"),
        "redis_status": getattr(request.app.state, "redis_status", "unknown"),
        "documents_by_status": {d["_id"]: d["count"] for d in doc_status if d["_id"]},
        "documents_by_collection": {d["_id"]: d["count"] for d in doc_collections if d["_id"]},
        "cache": cache_info,
        "crawler": {
            "enabled": settings.crawler_enabled,
            "schedule_hour": settings.crawler_schedule_hour,
            "schedule_minute": settings.crawler_schedule_minute,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EP8: Toggle user active status
# ═══════════════════════════════════════════════════════════════════════════════


@router.patch("/users/{user_id}/status")
async def toggle_user_status(
    user_id: str,
    body: UserStatusBody,
    current_user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Activate or deactivate a user account with audit logging."""
    if not ObjectId.is_valid(user_id):
        raise HTTPException(400, "Invalid user ID")

    # Prevent self-deactivation
    if str(current_user.id) == user_id and not body.is_active:
        raise HTTPException(400, "Không thể vô hiệu hóa tài khoản của chính mình")

    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "is_active": body.is_active,
                "updated_at": datetime.now(timezone.utc),
            },
            "$push": {
                "audit_log": {
                    "action": "deactivate" if not body.is_active else "activate",
                    "by": str(current_user.id),
                    "at": datetime.now(timezone.utc),
                }
            },
        },
    )

    if result.matched_count == 0:
        raise HTTPException(404, "User not found")

    return {"ok": True, "is_active": body.is_active}


# ═══════════════════════════════════════════════════════════════════════════════
# EP9: Trigger manual crawl
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/crawler/trigger")
async def trigger_crawl(
    request: Request,
    _user: Annotated[UserDocument, Depends(require_admin)],
    pipeline_target: str = Query("all", regex="^(all|kehoach|quydinh)$"),
):
    """Manually trigger a crawl pipeline run."""
    global _crawl_running, _last_trigger_time, _last_manual_crawl

    settings = request.app.state.settings
    if not settings.crawler_enabled:
        raise HTTPException(400, "Crawler is disabled in settings")

    now = time.time()
    if _crawl_running:
        raise HTTPException(409, "Crawl đang chạy, vui lòng đợi")
    if now - _last_trigger_time < _CRAWL_COOLDOWN_SECONDS:
        remaining = int(_CRAWL_COOLDOWN_SECONDS - (now - _last_trigger_time))
        raise HTTPException(429, f"Vui lòng đợi {remaining}s trước khi trigger lại")

    _last_trigger_time = now

    # Get crawl pipeline from app state
    pipe = request.app.state.pipeline
    bge = getattr(getattr(pipe, "retrieval_service", None) or getattr(pipe, "_retrieval_service", None), "bge_embedder", None)
    e5 = getattr(getattr(pipe, "retrieval_service", None) or getattr(pipe, "_retrieval_service", None), "e5_embedder", None)

    try:
        from scripts.auto_crawler import AutoCrawlPipeline
        crawl_pipeline = AutoCrawlPipeline(settings=settings, bge=bge, e5=e5)
    except ImportError:
        raise HTTPException(500, "Auto-crawler module not available")

    # Launch background task
    asyncio.create_task(_run_crawl_with_timeout(crawl_pipeline, pipeline_target))

    return {"ok": True, "message": f"Crawl '{pipeline_target}' started", "timeout_seconds": _CRAWL_TIMEOUT_SECONDS}


async def _run_crawl_with_timeout(crawl_pipeline, pipeline_target: str):
    """Run crawl in background thread with timeout protection."""
    global _crawl_running, _last_manual_crawl
    _crawl_running = True
    try:
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            _crawl_executor,
            _do_crawl, crawl_pipeline, pipeline_target,
        )
        result = await asyncio.wait_for(future, timeout=_CRAWL_TIMEOUT_SECONDS)
        status = _crawl_result_status(result)
        _last_manual_crawl = {
            **(result if isinstance(result, dict) else {"details": str(result)}),
            "status": status,
            "pipeline": pipeline_target,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if status in {"success", "pending_review"}:
            try:
                notification_result = await _create_crawl_notifications(
                    result,
                    pipeline_target,
                )
                target_user_ids = notification_result.get("target_user_ids") or []
                _last_manual_crawl["notification"] = {
                    key: value
                    for key, value in notification_result.items()
                    if key != "target_user_ids"
                }
                _last_manual_crawl["notification"]["target_user_count"] = len(target_user_ids)
            except Exception as exc:
                _last_manual_crawl["notification"] = {"error": str(exc)}
                logger.warning("Failed to create manual crawl notifications", exc_info=True)
    except asyncio.TimeoutError:
        _last_manual_crawl = {
            "status": "timeout",
            "pipeline": pipeline_target,
            "error": f"Crawl exceeded {_CRAWL_TIMEOUT_SECONDS}s",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.error("Manual crawl timed out after %ds", _CRAWL_TIMEOUT_SECONDS)
    except Exception as e:
        _last_manual_crawl = {
            "status": "error",
            "pipeline": pipeline_target,
            "error": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.error("Manual crawl failed: %s", e, exc_info=True)
    finally:
        _crawl_running = False


def _do_crawl(crawl_pipeline, pipeline_target: str) -> dict:
    """Sync function that runs in thread."""
    if pipeline_target == "kehoach":
        return crawl_pipeline.run_kehoach()
    elif pipeline_target == "quydinh":
        return crawl_pipeline.run_quydinh()
    else:
        return crawl_pipeline.run()


def _iter_crawl_summary_leaves(crawl_result: Any):
    if isinstance(crawl_result, dict):
        if "new_articles" in crawl_result or "saved_chunks" in crawl_result:
            yield crawl_result
            return
        for value in crawl_result.values():
            yield from _iter_crawl_summary_leaves(value)
    elif isinstance(crawl_result, list):
        for value in crawl_result:
            yield from _iter_crawl_summary_leaves(value)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _build_crawl_notification_summary(crawl_result: Any) -> dict[str, Any]:
    summaries = list(_iter_crawl_summary_leaves(crawl_result))
    saved_chunks: list[dict[str, Any]] = []
    pipelines: list[str] = []
    collections: list[str] = []

    for summary in summaries:
        pipeline = str(summary.get("pipeline") or "").strip()
        collection = str(summary.get("collection") or "").strip()
        if pipeline and pipeline not in pipelines:
            pipelines.append(pipeline)
        if collection and collection not in collections:
            collections.append(collection)

        chunks = summary.get("saved_chunks")
        if isinstance(chunks, list):
            saved_chunks.extend(chunk for chunk in chunks if isinstance(chunk, dict))

    return {
        "new_articles": sum(_safe_int(summary.get("new_articles")) for summary in summaries),
        "saved_chunks": saved_chunks,
        "pipelines": pipelines,
        "collections": collections,
    }


def _build_crawl_notification_article_links(
    saved_chunks: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for chunk in saved_chunks:
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        url = str(chunk.get("url") or metadata.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title = str(chunk.get("title") or metadata.get("title") or "").strip() or "Bài viết mới"
        links.append({"title": title, "url": url})
        if len(links) >= limit:
            break
    return links


_CRAWL_SOURCE_LABELS = {
    "baiviet": "Kế hoạch",
    "kehoach": "Kế hoạch",
    "kehoach_list": "Kế hoạch",
    "quydinh": "Quy định",
}


def _format_crawl_source_label(sources: list[str]) -> str:
    labels: list[str] = []
    for source in sources:
        clean_source = source.strip()
        if not clean_source:
            continue
        label = _CRAWL_SOURCE_LABELS.get(clean_source.lower(), clean_source)
        if label not in labels:
            labels.append(label)
    return ", ".join(labels)


def _build_crawl_notification_body(new_articles: int, source_label: str) -> str:
    clean_source = source_label.strip()
    if new_articles == 0:
        return "Không có bài viết mới sau lần cập nhật dữ liệu."

    source_suffix = f" từ nguồn {clean_source}" if clean_source else ""
    return f"Có {new_articles} bài viết mới{source_suffix}."


async def _create_crawl_notifications(
    crawl_result: Any,
    pipeline_target: str,
) -> dict[str, Any]:
    """Broadcast a manual crawl completion notification to all users."""
    from api.services.notification_delivery import broadcast_user_notification
    from models.database import _get_settings, get_motor_client

    notification_summary = _build_crawl_notification_summary(crawl_result)
    new_articles = notification_summary["new_articles"]
    article_links = _build_crawl_notification_article_links(
        notification_summary["saved_chunks"]
    )
    pipelines = notification_summary["pipelines"]
    collections = notification_summary["collections"]
    source_label = _format_crawl_source_label(collections or pipelines)
    body = _build_crawl_notification_body(new_articles, source_label)

    _, db_name = _get_settings()
    db = get_motor_client()[db_name]
    return await broadcast_user_notification(
        db,
        title="Cập nhật dữ liệu đã hoàn tất",
        body=body,
        notification_type="crawler_update",
        metadata={
            "article_links": article_links,
            "new_articles": new_articles,
            "pipeline": pipeline_target,
            "pipelines": pipelines,
            "collections": collections,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# EP10: Crawler status
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/crawler/status")
async def get_crawler_status(
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    """Return current crawler running state, last result, and review runs."""
    pending_statuses = [
        CRAWLER_STATUS_PENDING_REVIEW,
        CRAWLER_STATUS_INDEXING,
        CRAWLER_STATUS_INDEX_FAILED,
    ]
    pending_runs = await _list_crawler_runs(db, statuses=pending_statuses, limit=20)
    indexed_runs = await _list_crawler_runs(db, statuses=[CRAWLER_STATUS_INDEXED], limit=10)
    return {
        "is_running": _crawl_running,
        "last_result": _last_manual_crawl,
        "cooldown_seconds": _CRAWL_COOLDOWN_SECONDS,
        "pending_runs": pending_runs,
        "indexed_runs": indexed_runs,
        "runs": pending_runs + indexed_runs,
    }


@router.get("/crawler/runs/{run_id}/chunks")
async def get_crawler_run_chunks(
    run_id: str,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    """Return full staged chunks for a crawler review run."""
    run_doc = await db[CRAWLER_RUNS_COLLECTION].find_one({"run_id": run_id})
    if not run_doc:
        raise HTTPException(404, "Crawler run not found")

    cursor = (
        db[CRAWLER_CHUNKS_COLLECTION]
        .find({"run_id": run_id})
        .sort("chunk_index", 1)
    )
    chunk_docs = await cursor.to_list(length=None)
    return {
        "run": _serialize_crawler_run(
            run_doc,
            [_serialize_crawler_chunk(doc, include_content=False) for doc in chunk_docs[:5]],
        ),
        "chunks": [_serialize_crawler_chunk(doc) for doc in chunk_docs],
    }


@router.patch("/crawler/runs/{run_id}/chunks/{chunk_id}")
async def update_crawler_run_chunk(
    run_id: str,
    chunk_id: str,
    body: CrawlerChunkUpdateBody,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    """Update staged crawler chunk content before indexing."""
    run_doc = await db[CRAWLER_RUNS_COLLECTION].find_one({"run_id": run_id})
    if not run_doc:
        raise HTTPException(404, "Crawler run not found")
    if run_doc.get("status") not in CRAWLER_EDITABLE_STATUSES:
        raise HTTPException(409, "Crawler run is not editable")

    content = body.content
    if not content.strip():
        raise HTTPException(400, "Chunk content cannot be empty")

    chunk_doc = await db[CRAWLER_CHUNKS_COLLECTION].find_one({
        "run_id": run_id,
        "chunk_id": chunk_id,
    })
    if not chunk_doc:
        raise HTTPException(404, "Crawler chunk not found")

    now = datetime.now(timezone.utc)
    edited = content != str(chunk_doc.get("original_content") or "")
    await db[CRAWLER_CHUNKS_COLLECTION].update_one(
        {"run_id": run_id, "chunk_id": chunk_id},
        {"$set": {
            "content": content,
            "edited": edited,
            "updated_at": now,
        }},
    )
    await db[CRAWLER_RUNS_COLLECTION].update_one(
        {"run_id": run_id},
        {"$set": {"updated_at": now}},
    )
    updated = await db[CRAWLER_CHUNKS_COLLECTION].find_one({
        "run_id": run_id,
        "chunk_id": chunk_id,
    })
    return _serialize_crawler_chunk(updated or chunk_doc)


@router.post("/crawler/runs/{run_id}/index")
async def index_crawler_run(
    run_id: str,
    request: Request,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    """Start background indexing for a reviewed crawler run."""
    run_doc = await db[CRAWLER_RUNS_COLLECTION].find_one({"run_id": run_id})
    if not run_doc:
        raise HTTPException(404, "Crawler run not found")
    if run_doc.get("status") not in CRAWLER_INDEXABLE_STATUSES:
        raise HTTPException(409, "Crawler run is not indexable")

    now = datetime.now(timezone.utc)
    result = await db[CRAWLER_RUNS_COLLECTION].update_one(
        {"run_id": run_id, "status": {"$in": list(CRAWLER_INDEXABLE_STATUSES)}},
        {"$set": {
            "status": CRAWLER_STATUS_INDEXING,
            "updated_at": now,
            "error_message": None,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(409, "Crawler run is already being indexed")

    await db[CRAWLER_CHUNKS_COLLECTION].update_many(
        {"run_id": run_id},
        {"$set": {"index_status": CRAWLER_STATUS_INDEXING, "updated_at": now}},
    )

    bge, e5 = _get_pipeline_embedders(request)
    asyncio.create_task(_index_crawler_run_background(request.app.state.settings, run_id, bge, e5))
    return {"ok": True, "run_id": run_id, "status": CRAWLER_STATUS_INDEXING}


def _get_pipeline_embedders(request: Request) -> tuple[Any, Any]:
    pipe = request.app.state.pipeline
    retrieval_service = (
        getattr(pipe, "retrieval_service", None)
        or getattr(pipe, "_retrieval_service", None)
    )
    return (
        getattr(retrieval_service, "bge_embedder", None),
        getattr(retrieval_service, "e5_embedder", None),
    )


async def _index_crawler_run_background(settings, run_id: str, bge=None, e5=None) -> None:
    try:
        from scripts.auto_crawler import index_staged_crawler_run

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _crawl_executor,
            index_staged_crawler_run,
            settings,
            run_id,
            bge,
            e5,
        )
        logger.info("Crawler review run %s indexed successfully.", run_id)
    except Exception:
        logger.error("Crawler review run %s failed during indexing.", run_id, exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EP11: Toggle system config
# ═══════════════════════════════════════════════════════════════════════════════

# Whitelist of boolean settings that admin can toggle at runtime
_TOGGLEABLE_KEYS = {
    "agent_enabled", "self_eval_enabled", "tavily_fallback_enabled",
    "crawler_enabled", "reflection_enabled", "domain_routing_enabled",
    "rate_limit_enabled",
}


@router.patch("/config")
async def toggle_config(
    request: Request,
    body: ConfigToggleBody,
    _user: Annotated[UserDocument, Depends(require_admin)],
):
    """Toggle a boolean system configuration at runtime."""
    if body.key not in _TOGGLEABLE_KEYS:
        raise HTTPException(400, f"Key '{body.key}' is not toggleable. Allowed: {sorted(_TOGGLEABLE_KEYS)}")

    settings = request.app.state.settings
    if not hasattr(settings, body.key):
        raise HTTPException(400, f"Unknown setting: {body.key}")

    setattr(settings, body.key, body.value)
    logger.info("Admin toggled %s = %s", body.key, body.value)

    return {"ok": True, "key": body.key, "value": body.value}


# ═══════════════════════════════════════════════════════════════════════════════
# EP12: Get/Update LLM configuration
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/config/llm")
async def get_llm_config(
    request: Request,
    _user: Annotated[UserDocument, Depends(require_admin)],
):
    """Return current LLM-related configuration (keys are masked)."""
    settings = request.app.state.settings

    def mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "***"
        return key[:4] + "***" + key[-4:]

    return {
        "llm_provider": settings.llm_provider,
        "deepseek_api_key": mask_key(settings.deepseek_api_key),
        "google_api_key": mask_key(settings.google_api_key),
        "tavily_api_key": mask_key(settings.tavily_api_key),
        "chat_model": settings.chat_model,
        "chat_temperature": settings.chat_temperature,
        "chat_max_tokens": settings.chat_max_tokens,
        "agent_enabled": settings.agent_enabled,
        "agent_model": settings.agent_model,
        "self_eval_enabled": settings.self_eval_enabled,
        "tavily_fallback_enabled": settings.tavily_fallback_enabled,
        "reflection_enabled": settings.reflection_enabled,
        "reflection_model": settings.reflection_model,
    }


async def _prepare_api_key_reload(
    request: Request,
    provider: str,
    secret: str,
):
    field_name = API_KEY_SETTING_FIELDS.get(provider)
    if not field_name:
        raise HTTPException(400, "Unsupported API key provider")

    settings = request.app.state.settings
    candidate_settings = settings.model_copy(deep=True)
    setattr(candidate_settings, field_name, secret)
    pipeline = request.app.state.pipeline
    loop = asyncio.get_running_loop()
    try:
        prepared_runtime = await loop.run_in_executor(
            None,
            pipeline.prepare_llm_config_reload,
            candidate_settings,
        )
    except Exception as exc:
        logger.warning("API key runtime prepare failed for %s", provider)
        raise HTTPException(400, "Unable to prepare API key runtime") from exc
    return candidate_settings, prepared_runtime


def _commit_api_key_reload(
    request: Request,
    candidate_settings,
    prepared_runtime,
    provider: str,
):
    field_name = API_KEY_SETTING_FIELDS[provider]
    rebuilt = request.app.state.pipeline.commit_llm_config_reload(
        candidate_settings,
        prepared_runtime,
    )
    setattr(request.app.state.settings, field_name, getattr(candidate_settings, field_name))
    return rebuilt


@router.get("/config/api-keys")
async def get_api_keys(
    request: Request,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Return secret-free managed API key rows."""
    keys = await list_api_keys(db)
    managed_providers = {key["provider"] for key in keys}
    settings = request.app.state.settings
    fallback_providers = [
        provider
        for provider, field_name in API_KEY_SETTING_FIELDS.items()
        if provider not in managed_providers and getattr(settings, field_name, "")
    ]
    return {"keys": keys, "fallback_providers": fallback_providers}


@router.post("/config/api-keys")
async def create_managed_api_key(
    request: Request,
    body: ApiKeyCreateBody,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Create and activate a managed API key without exposing the secret."""
    provider = body.provider.strip().lower()
    name = body.name.strip()
    secret = body.key.strip()
    if provider not in API_KEY_SETTING_FIELDS:
        raise HTTPException(400, "Unsupported API key provider")
    if not name:
        raise HTTPException(400, "API key name is required")
    if len(name) > 120:
        raise HTTPException(400, "API key name is too long")
    if not secret:
        raise HTTPException(400, "API key value is required")

    candidate_settings, prepared_runtime = await _prepare_api_key_reload(
        request,
        provider,
        secret,
    )

    try:
        key = await create_api_key(db, provider, name, secret)
    except ApiKeyRegistryError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to persist %s API key", provider, exc_info=True)
        raise HTTPException(503, "Failed to persist API key") from exc

    try:
        rebuilt = _commit_api_key_reload(
            request,
            candidate_settings,
            prepared_runtime,
            provider,
        )
    except Exception as exc:
        logger.error("API key persisted but runtime reload failed", exc_info=True)
        raise HTTPException(
            500,
            "API key persisted but runtime reload failed",
        ) from exc

    logger.info("Admin created and activated managed %s API key %s", provider, key["id"])
    return {"ok": True, "key": key, "rebuilt": rebuilt}


@router.post("/config/api-keys/{key_id}/activate")
async def activate_managed_api_key(
    request: Request,
    key_id: str,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Activate an existing managed API key and hot-swap runtime clients."""
    record = await get_api_key_record(db, key_id)
    if not record:
        raise HTTPException(404, "API key not found")

    provider = str(record.get("provider", ""))
    secret = str(record.get("secret", "")).strip()
    if not secret:
        raise HTTPException(400, "API key secret is unavailable")

    candidate_settings, prepared_runtime = await _prepare_api_key_reload(
        request,
        provider,
        secret,
    )
    try:
        key = await activate_api_key(db, key_id)
    except ApiKeyRegistryError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to activate managed %s API key", provider, exc_info=True)
        raise HTTPException(503, "Failed to activate API key") from exc

    try:
        rebuilt = _commit_api_key_reload(
            request,
            candidate_settings,
            prepared_runtime,
            provider,
        )
    except Exception as exc:
        logger.error("API key activation persisted but runtime reload failed", exc_info=True)
        raise HTTPException(
            500,
            "API key activation persisted but runtime reload failed",
        ) from exc

    logger.info("Admin activated managed %s API key %s", provider, key["id"])
    return {"ok": True, "key": key, "rebuilt": rebuilt}


@router.put("/config/llm")
async def update_llm_config(
    request: Request,
    body: LLMConfigBody,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Persist and hot-reload admin-managed LLM configuration."""
    settings = request.app.state.settings
    body_values = body.model_dump(exclude_none=True)
    updates = filter_llm_config_updates(body_values)
    api_key_inputs = {
        provider: str(body_values[field_name]).strip()
        for provider, field_name in API_KEY_SETTING_FIELDS.items()
        if field_name in body_values and str(body_values[field_name]).strip()
    }
    if not updates and not api_key_inputs:
        raise HTTPException(400, "No fields to update")

    candidate_settings = settings.model_copy(deep=True)
    merge_llm_config_into_settings(candidate_settings, updates)
    for provider, secret in api_key_inputs.items():
        setattr(candidate_settings, API_KEY_SETTING_FIELDS[provider], secret)
    pipeline = request.app.state.pipeline
    loop = asyncio.get_running_loop()

    try:
        prepared_runtime = await loop.run_in_executor(
            None,
            pipeline.prepare_llm_config_reload,
            candidate_settings,
        )
    except Exception as exc:
        logger.warning("LLM config prepare failed: %s", exc, exc_info=True)
        raise HTTPException(400, "Unable to prepare LLM config reload") from exc

    legacy_keys: dict[str, dict[str, Any]] = {}
    try:
        if updates:
            await upsert_llm_config(db, updates)
        for provider, secret in api_key_inputs.items():
            legacy_keys[provider] = await create_api_key(
                db,
                provider,
                f"Admin {provider.title()} key",
                secret,
            )
    except ApiKeyRegistryError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to persist LLM config: %s", exc, exc_info=True)
        raise HTTPException(503, "Failed to persist LLM config") from exc

    try:
        rebuilt = pipeline.commit_llm_config_reload(
            candidate_settings,
            prepared_runtime,
        )
        merge_llm_config_into_settings(settings, updates)
        for provider in api_key_inputs:
            field_name = API_KEY_SETTING_FIELDS[provider]
            setattr(settings, field_name, getattr(candidate_settings, field_name))
    except Exception as exc:
        logger.error("Pipeline LLM reload failed after persist: %s", exc, exc_info=True)
        raise HTTPException(
            500,
            "LLM config persisted but runtime reload failed",
        ) from exc

    invalidated_cache_keys = 0
    llm_cache = getattr(request.app.state, "llm_cache", None)
    if (
        llm_cache is not None
        and _LLM_CACHE_INVALIDATION_FIELDS.intersection(updates)
        and hasattr(llm_cache, "invalidate_all")
    ):
        try:
            invalidated_cache_keys = await loop.run_in_executor(
                None,
                llm_cache.invalidate_all,
            )
        except Exception:
            logger.warning("Failed to invalidate LLM response cache", exc_info=True)

    updated: dict[str, Any] = {}
    for field_name, value in updates.items():
        updated[field_name] = value
    for provider, key in legacy_keys.items():
        updated[API_KEY_SETTING_FIELDS[provider]] = key["fingerprint"]

    logger.info(
        "Admin updated persisted LLM config: %s; rebuilt=%s",
        list(updated.keys()),
        rebuilt,
    )
    return {
        "ok": True,
        "updated": updated,
        "rebuilt": rebuilt,
        "llm_cache_invalidated": invalidated_cache_keys,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EP13: Advanced Config (env settings editable from UI)
# ═══════════════════════════════════════════════════════════════════════════════

_ENV_CONFIG_WHITELIST: dict[str, dict[str, Any]] = {
    # Retrieval
    "top_k": {"type": "int", "label": "Top K (final)", "description": "Số documents cuối cùng sau reranking", "category": "Retrieval"},
    "vector_top_k": {"type": "int", "label": "Vector Top K", "description": "Số kết quả vector search mỗi collection", "category": "Retrieval"},
    "keyword_top_k": {"type": "int", "label": "Keyword Top K", "description": "Số kết quả keyword search mỗi collection", "category": "Retrieval"},
    "vector_weight": {"type": "float", "label": "Vector Weight", "description": "Trọng số vector trong RRF fusion (0-1)", "category": "Retrieval"},
    "keyword_weight": {"type": "float", "label": "Keyword Weight", "description": "Trọng số keyword trong RRF fusion (0-1)", "category": "Retrieval"},
    "reranker_top_k": {"type": "int", "label": "Reranker Top K", "description": "Số documents giữ lại sau reranking", "category": "Retrieval"},
    "reranker_score_threshold": {"type": "float", "label": "Reranker Threshold", "description": "Ngưỡng điểm reranker (raw logit)", "category": "Retrieval"},
    # Crawler
    "crawler_schedule_hour": {"type": "int", "label": "Giờ crawl", "description": "Giờ tự động crawl (0-23)", "category": "Crawler"},
    "crawler_schedule_minute": {"type": "int", "label": "Phút crawl", "description": "Phút tự động crawl (0-59)", "category": "Crawler"},
    "crawler_delay": {"type": "float", "label": "Delay (giây)", "description": "Delay giữa các request crawl", "category": "Crawler"},
    "crawler_retention_months": {"type": "int", "label": "Retention (tháng)", "description": "Số tháng giữ lại dữ liệu crawl", "category": "Crawler"},
    # Rate Limit
    "rate_limit_rpm": {"type": "int", "label": "RPM", "description": "Requests tối đa mỗi phút", "category": "Rate Limit"},
    "rate_limit_rpd": {"type": "int", "label": "RPD", "description": "Requests tối đa mỗi ngày", "category": "Rate Limit"},
    # Chat
    "chat_temperature": {"type": "float", "label": "Temperature", "description": "Nhiệt độ sampling (0-2)", "category": "Chat"},
    "chat_max_tokens": {"type": "int", "label": "Max Tokens", "description": "Số token tối đa cho câu trả lời", "category": "Chat"},
    "context_doc_char_limit": {"type": "int", "label": "Doc Char Limit", "description": "Giới hạn ký tự mỗi document context", "category": "Chat"},
    # Self Eval
    "self_eval_min_top_score": {"type": "float", "label": "Min Top Score", "description": "Ngưỡng score tối thiểu để skip self-eval", "category": "Self Eval"},
    # Tavily
    "tavily_max_results": {"type": "int", "label": "Max Results", "description": "Số kết quả Tavily fetch", "category": "Tavily"},
    "tavily_web_result_count": {"type": "int", "label": "Web Result Count", "description": "Số kết quả Tavily giữ lại", "category": "Tavily"},
    "tavily_search_depth": {"type": "str", "label": "Search Depth", "description": "Mức độ tìm kiếm: basic (1 credit) / advanced (2 credits)", "category": "Tavily"},
}

SYSTEM_CONFIG_COLLECTION = "system_config"


class EnvConfigUpdateBody(BaseModel):
    configs: dict[str, Any]


@router.get("/config/env")
async def get_env_config(
    request: Request,
    _user: Annotated[UserDocument, Depends(require_admin)],
):
    """Return editable environment configurations grouped by category."""
    settings = request.app.state.settings
    items = []
    for key, meta in _ENV_CONFIG_WHITELIST.items():
        value = getattr(settings, key, None)
        items.append({
            "key": key,
            "value": value,
            "type": meta["type"],
            "label": meta["label"],
            "description": meta["description"],
            "category": meta["category"],
        })
    return {"configs": items}


@router.put("/config/env")
async def update_env_config(
    request: Request,
    body: EnvConfigUpdateBody,
    _user: Annotated[UserDocument, Depends(require_admin)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    """Update whitelisted environment configs at runtime and persist to MongoDB."""
    settings = request.app.state.settings
    updated = {}

    for key, value in body.configs.items():
        if key not in _ENV_CONFIG_WHITELIST:
            raise HTTPException(400, f"Config '{key}' is not editable from UI")

        meta = _ENV_CONFIG_WHITELIST[key]
        # Type coercion
        try:
            if meta["type"] == "int":
                value = int(value)
            elif meta["type"] == "float":
                value = float(value)
            else:
                value = str(value)
        except (ValueError, TypeError):
            raise HTTPException(400, f"Invalid type for '{key}': expected {meta['type']}")

        setattr(settings, key, value)
        updated[key] = value

    # Persist to MongoDB system_config collection
    if updated:
        await db[SYSTEM_CONFIG_COLLECTION].update_one(
            {"_id": "env_config"},
            {"$set": {"configs": updated, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    logger.info("Admin updated env config: %s", list(updated.keys()))
    return {"ok": True, "updated": updated}

