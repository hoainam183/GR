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
from models.database import get_database
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


# ═══════════════════════════════════════════════════════════════════════════════
# Request/Response schemas
# ═══════════════════════════════════════════════════════════════════════════════


class UserStatusBody(BaseModel):
    is_active: bool


class ConfigToggleBody(BaseModel):
    key: str
    value: bool


class LLMConfigBody(BaseModel):
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
        _last_manual_crawl = {
            "status": "success",
            "pipeline": pipeline_target,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            **(result if isinstance(result, dict) else {"details": str(result)}),
        }
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


# ═══════════════════════════════════════════════════════════════════════════════
# EP10: Crawler status
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/crawler/status")
async def get_crawler_status(
    _user: Annotated[UserDocument, Depends(require_admin)],
):
    """Return current crawler running state and last result."""
    return {
        "is_running": _crawl_running,
        "last_result": _last_manual_crawl,
        "cooldown_seconds": _CRAWL_COOLDOWN_SECONDS,
    }


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


@router.put("/config/llm")
async def update_llm_config(
    request: Request,
    body: LLMConfigBody,
    _user: Annotated[UserDocument, Depends(require_admin)],
):
    """Update LLM configuration at runtime (non-null fields only)."""
    settings = request.app.state.settings
    updated: dict[str, Any] = {}

    for field_name, value in body.model_dump(exclude_none=True).items():
        if hasattr(settings, field_name):
            setattr(settings, field_name, value)
            # Mask sensitive keys in response
            if "key" in field_name:
                display_val = value[:4] + "***" if len(value) > 4 else "***"
            else:
                display_val = value
            updated[field_name] = display_val

    if not updated:
        raise HTTPException(400, "No fields to update")

    logger.info("Admin updated LLM config: %s", list(updated.keys()))
    return {"ok": True, "updated": updated}

