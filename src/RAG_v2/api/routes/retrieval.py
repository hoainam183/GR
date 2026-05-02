"""Retrieval diagnostic routes — direct access to search pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import anyio
import anyio.to_thread
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from schemas.chat import FilterInfo, CollectionResult, RetrievedDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RetrievalRequest(BaseModel):
    """Body for direct retrieval test."""
    query: str = Field(..., min_length=1)
    collections: List[str] = Field(default=["ctdt"])
    resolved_major: Optional[str] = None
    resolved_cohort: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    rerank: bool = True


class RetrievalResponse(BaseModel):
    """Response for direct retrieval test."""
    query: str
    results: List[RetrievedDocument]
    total_found: int
    applied_filters: List[FilterInfo]
    collection_results: List[CollectionResult]
    fusion_weights: Dict[str, Any]
    latency_ms: float


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/search", response_model=RetrievalResponse)
async def retrieval_search(request: Request, body: RetrievalRequest) -> RetrievalResponse:
    """Run retrieval search directly and return detailed doc list + trace."""
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")

    # Access the shared service from the pipeline
    service = getattr(pipeline, "service", None)
    if service is None:
        # Fallback to creating a service if pipeline doesn't expose it (unlikely)
        from retrieval.service import RetrievalService
        from config.settings import Settings
        service = RetrievalService.from_settings(Settings())

    t0 = time.perf_counter()
    
    try:
        # Run search with trace_out captured
        trace_out: Dict[str, Any] = {}
        
        # We use anyio.to_thread because retrieval involves heavy model work
        bge_vec, e5_vec = await anyio.to_thread.run_sync(
            lambda: service.embed_query(body.query)
        )
        
        raw_top_k = max(body.top_k * 4, 20)
        
        results = await anyio.to_thread.run_sync(
            lambda: service.searcher.search(
                query=body.query,
                bge_m3_query=bge_vec,
                e5_query=e5_vec,
                top_k=raw_top_k,
                active_collections=body.collections,
                resolved_major=body.resolved_major,
                resolved_cohort=body.resolved_cohort,
                trace_out=trace_out,
            )
        )

        # Reranking
        if body.rerank and service.reranker is not None:
            results = await anyio.to_thread.run_sync(
                lambda: service.reranker.rerank(
                    query=body.query,
                    documents=results,
                    top_k=body.top_k,
                )
            )
        else:
            results = results[:body.top_k]

        latency_ms = (time.perf_counter() - t0) * 1000

        # Map results to RetrievedDocument schema
        mapped_docs = []
        for i, r in enumerate(results):
            mapped_docs.append(RetrievedDocument(
                rank=i + 1,
                content=r.get("text", ""),
                score=r.get("score", 0.0),
                hybrid_score=r.get("score") if not body.rerank else r.get("hybrid_score"),
                rerank_score=r.get("rerank_score"),
                vector_score=r.get("vector_score"),
                keyword_score=r.get("keyword_score"),
                collection=r.get("collection"),
                metadata=r.get("metadata", {}),
            ))

        # Map filters and collection results
        filters = []
        for col, info in trace_out.get("filters", {}).items():
            filters.append(FilterInfo(
                collection=col,
                applied=info.get("applied", False),
                matched_ids=info.get("matched_ids", 0),
                filter_desc=info.get("filter_desc"),
            ))

        col_results = []
        for col, counts in trace_out.get("collection_counts", {}).items():
            col_results.append(CollectionResult(
                collection=col,
                vector_count=counts.get("vector", 0),
                keyword_count=counts.get("keyword", 0),
            ))

        return RetrievalResponse(
            query=body.query,
            results=mapped_docs,
            total_found=len(mapped_docs),
            applied_filters=filters,
            collection_results=col_results,
            fusion_weights=trace_out.get("fusion_weights", {}),
            latency_ms=latency_ms,
        )

    except Exception as exc:
        logger.error("Retrieval diagnostic API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
