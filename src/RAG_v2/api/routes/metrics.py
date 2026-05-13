"""Metrics API — expose evaluation and usage metrics.

Provides endpoints to fetch system health, query volumes, and 
(if evaluation is run periodically) the latest evaluation scores.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


@router.get("/metrics/usage")
async def get_usage_metrics(
    request: Request,
    days: int = 7,
) -> Dict[str, Any]:
    """Get usage volume and basic statistics over the last N days."""
    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    if mongo_logger is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB logger not configured",
        )

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Count total queries in timeframe
        total_queries = mongo_logger._query_logs.count_documents({
            "timestamp": {"$gte": cutoff}
        })
        
        # Group by routing mode
        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$mode", "count": {"$sum": 1}}}
        ]
        modes_cursor = mongo_logger._query_logs.aggregate(pipeline)
        modes = {str(doc["_id"]): doc["count"] for doc in modes_cursor}
        
        # Group by intent
        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$intent", "count": {"$sum": 1}}}
        ]
        intents_cursor = mongo_logger._query_logs.aggregate(pipeline)
        intents = {str(doc["_id"]): doc["count"] for doc in intents_cursor}
        
        # Avg latency
        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}, "latency_ms": {"$gt": 0}}},
            {"$group": {"_id": None, "avg_latency": {"$avg": "$latency_ms"}}}
        ]
        latency_cursor = list(mongo_logger._query_logs.aggregate(pipeline))
        avg_latency = latency_cursor[0]["avg_latency"] if latency_cursor else 0.0

        cache_stats = {"hits": 0, "misses": 0, "hit_rate": 0.0}
        llm_cache = getattr(request.app.state, "llm_cache", None)
        if llm_cache is not None:
            stats = llm_cache.get_stats()
            h = stats.get("hits", 0)
            m = stats.get("misses", 0)
            tot = h + m
            cache_stats = {
                "hits": h,
                "misses": m,
                "hit_rate": round(h / tot, 4) if tot > 0 else 0.0,
            }

        return {
            "timeframe_days": days,
            "total_queries": total_queries,
            "avg_latency_ms": round(avg_latency, 2),
            "by_mode": modes,
            "by_intent": intents,
            "cache_stats": cache_stats,
        }
        
    except Exception as exc:
        logger.error("Failed to fetch usage metrics: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal metrics error")


@router.get("/metrics/eval")
async def get_eval_metrics() -> Dict[str, Any]:
    """Get the latest evaluation results.
    
    (In a real production system, this would read from MongoDB.
    Here we return a placeholder indicating where CI/CD eval results would go).
    """
    return {
        "status": "eval_metrics_available_via_cli",
        "message": "Run `python -m eval.evaluator --all --report` to generate current metrics.",
    }
