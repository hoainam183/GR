"""Health check route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from schemas.chat import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Return service health status.

    The ``mongo_status`` field reflects the MongoDB connection state:
    - ``"ok"``       — connected and indexes in place
    - ``"degraded"`` — connected but index creation failed
    - ``"failed"``   — connection failed at startup (logging disabled)
    - ``"disabled"`` — MongoDB logging is intentionally off via config
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")
    mongo_status: str = getattr(request.app.state, "mongo_status", "unknown")
    return HealthResponse(
        status="healthy",
        rag_initialized=True,
        mongo_status=mongo_status,
    )


@router.post("/api/admin/reload-validity")
async def reload_validity(request: Request) -> dict[str, str]:
    """Reload the ValidityFilter registry after a data update."""
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")
    
    try:
        # The filter is an attribute of the pipeline
        if hasattr(pipeline, "_validity_filter"):
            pipeline._validity_filter.reload()
            return {"status": "success", "message": "ValidityFilter registry reloaded."}
        else:
            return {"status": "skipped", "message": "ValidityFilter not configured."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reload: {exc}")
