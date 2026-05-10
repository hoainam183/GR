"""Chat API routes — non-streaming and SSE streaming endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import anyio
import anyio.to_thread
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.dependencies import parse_history, resolve_session
from api.response_mapper import ChatResponseMapper
from schemas.chat import (
    ChatRequest,
    ChatResponse,
)
from schemas.constants import AgentRoute, PipelineMode, RouteMode

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# ─── Legacy turn logging helper ───────────────────────────────────────────────


def _log_legacy_turn_for_agent_response(
    *,
    mongo_logger: Any,
    session_id: str | None,
    question: str,
    result: dict[str, Any],
    request_started_at: float,
) -> None:
    """Persist agent answers into legacy turns/query_logs collections.

    ``pipeline.query_v3`` records agent traces, but successful agent answers do
    not automatically create session turns. This helper keeps /chat history
    behavior consistent with classic ``pipeline.query`` logging.
    """
    if not session_id:
        return
    if not str(result.get("mode", "")).lower().startswith(PipelineMode.AGENT):
        return
    if not hasattr(mongo_logger, "log_turn"):
        return

    legacy_result = dict(result)
    legacy_result.setdefault("intent", str(result.get("route") or AgentRoute.COMPLEX))
    legacy_result.setdefault("model_name", str(result.get("mode") or PipelineMode.AGENT))
    if not isinstance(legacy_result.get("sources"), list):
        legacy_result["sources"] = []
    legacy_result.setdefault("num_sources", len(legacy_result["sources"]))

    latency_ms = int((time.perf_counter() - request_started_at) * 1000)
    agent_trace = legacy_result.get("agent_trace")
    if isinstance(agent_trace, dict):
        try:
            latency_ms = int(float(agent_trace.get("latency_ms") or latency_ms))
        except (TypeError, ValueError):
            pass

    try:
        mongo_logger.log_turn(
            session_id=session_id,
            question=question,
            result=legacy_result,
            reflected_question=legacy_result.get("reflected_question"),
            latency_ms=latency_ms,
            timings_ms=legacy_result.get("timings_ms"),
        )
    except Exception:
        logger.warning(
            "Failed to log legacy turn for agent response",
            exc_info=True,
        )


# ------------------------------------------------------------------
# POST /chat — non-streaming
# ------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Process a question and return the full answer.

    Routing:
      - mode='agent': force LangGraph ReAct agent (slow, multi-step).
      - mode='rag':   force classic RAG v2 pipeline.
      - mode='auto' or absent: smart routing via complexity_router
        (chitchat → canned reply, simple → RAG v2, complex → agent).
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")

    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    redis_session = getattr(request.app.state, "redis_session", None)
    session_id = resolve_session(
        session_id=body.session_id,
        user_id=body.user_id,
        mongo_logger=mongo_logger,
        redis_session=redis_session,
    )
    history = parse_history(body.history)
    mode = (body.mode or RouteMode.AUTO).lower()
    logger.info("/chat mode=%s question=%r", mode, body.question[:80])

    user_context_payload = (
        body.user_context.model_dump() if body.user_context else None
    )
    request_t0 = time.perf_counter()

    try:
        # ── Explicit agent mode ───────────────────────────────────────────────
        if mode == RouteMode.AGENT:
            if getattr(pipeline, "agent", None) is None:
                raise HTTPException(
                    status_code=503,
                    detail="Agent is required for mode=agent but is disabled",
                )
            result = await anyio.to_thread.run_sync(
                lambda: pipeline.query_agent(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=user_context_payload,
                    route_label=AgentRoute.AGENT_FORCED,
                    require_agent=True,
                ),
            )

        # ── Explicit RAG mode ─────────────────────────────────────────────────
        elif mode == RouteMode.RAG:
            result = await anyio.to_thread.run_sync(
                lambda: pipeline.query(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=user_context_payload,
                ),
            )
            result.setdefault("mode", PipelineMode.RAG_V2)
            result.setdefault("route", AgentRoute.SIMPLE)

        # ── Auto / smart routing (default) ────────────────────────────────────
        else:
            result = await anyio.to_thread.run_sync(
                lambda: pipeline.query_v3(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=user_context_payload,
                ),
            )

        if mongo_logger is not None:
            _log_legacy_turn_for_agent_response(
                mongo_logger=mongo_logger,
                session_id=session_id,
                question=body.question,
                result=result,
                request_started_at=request_t0,
            )

        return ChatResponseMapper.to_chat_response(
            result,
            fallback_question=body.question,
            session_id=session_id or "",
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.error("/chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# POST /chat/v3 — smart routing (auto | rag | agent)
# ------------------------------------------------------------------


@router.post("/chat/v3")
@router.post("/api/chat/v3")
async def chat_v3(request: Request, body: ChatRequest) -> dict[str, Any]:
    """Week 3 endpoint with explicit mode control.

    Modes:
      - auto: pipeline.query_v3 (chitchat/simple/complex routing)
      - rag:  force classic RAG v2 pipeline
      - agent: force LangGraph agent path
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")

    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    redis_session = getattr(request.app.state, "redis_session", None)
    session_id = resolve_session(
        session_id=body.session_id,
        user_id=body.user_id,
        mongo_logger=mongo_logger,
        redis_session=redis_session,
    )
    history = parse_history(body.history)
    mode = (body.mode or RouteMode.AUTO).lower()
    user_context_payload = (
        body.user_context.model_dump() if body.user_context else None
    )

    try:
        if mode == RouteMode.RAG:
            result = await anyio.to_thread.run_sync(
                lambda: pipeline.query(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=user_context_payload,
                ),
            )
            result.setdefault("mode", PipelineMode.RAG_V2)
            result.setdefault("route", AgentRoute.SIMPLE)
            result.setdefault("tools_used", [])
            result.setdefault("iterations", 0)
            return ChatResponseMapper.normalize_v3_result(result, session_id or "")

        if mode == RouteMode.AGENT:
            if getattr(pipeline, "agent", None) is None:
                # Agent explicitly disabled — return RAG fallback with clear signal
                result = await anyio.to_thread.run_sync(
                    lambda: pipeline.query(
                        question=body.question,
                        history=history,
                        top_k=body.top_k,
                        session_id=session_id,
                        user_context=user_context_payload,
                    ),
                )
                result["mode"] = PipelineMode.RAG_V2_FALLBACK
                result["route"] = AgentRoute.COMPLEX
                result["tools_used"] = []
                result["iterations"] = 0
                result["agent_error"] = "Agent is disabled"
                result["tool_calls"] = []
                result["agent_trace"] = {
                    "query": body.question,
                    "session_id": session_id or "",
                    "route": AgentRoute.COMPLEX,
                    "iterations": 0,
                    "tool_calls": [],
                    "tool_names_sequence": [],
                    "final_answer_length": 0,
                    "error": "Agent is disabled",
                }
                return ChatResponseMapper.normalize_v3_result(result, session_id or "")

            result = await anyio.to_thread.run_sync(
                lambda: pipeline.query_agent(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=user_context_payload,
                    route_label=AgentRoute.COMPLEX,
                    require_agent=False,
                ),
            )
            return ChatResponseMapper.normalize_v3_result(result, session_id or "")

        # Auto mode
        result = await anyio.to_thread.run_sync(
            lambda: pipeline.query_v3(
                question=body.question,
                history=history,
                top_k=body.top_k,
                session_id=session_id,
                user_context=user_context_payload,
            ),
        )
        return ChatResponseMapper.normalize_v3_result(result, session_id or "")

    except Exception as exc:
        logger.error("/chat/v3 error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# POST /chat/stream — SSE streaming
# ------------------------------------------------------------------


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """Server-Sent Events streaming endpoint.

        Emits JSON payloads as SSE ``data`` frames:
            - ``{"type":"session","session_id":"..."}``
            - ``{"type":"token","delta":"..."}``
            - ``{"type":"done"}``
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")

    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    redis_session = getattr(request.app.state, "redis_session", None)
    session_id = resolve_session(
        session_id=body.session_id,
        user_id=body.user_id,
        mongo_logger=mongo_logger,
        redis_session=redis_session,
    )
    history = parse_history(body.history)
    user_context_payload = (
        body.user_context.model_dump() if body.user_context else None
    )

    async def event_generator():
        # Send session_id as first SSE event
        if session_id:
            yield (
                "data: "
                + json.dumps(
                    {"type": "session", "session_id": session_id},
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        loop = asyncio.get_running_loop()  # S-4: fixed from deprecated get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _produce():
            try:
                for chunk in pipeline.query_stream(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=user_context_payload,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _produce)

        while True:
            chunk = await queue.get()
            if chunk is None:
                # ── Emit metadata SSE event before done ──────────────────────
                try:
                    meta_payload: dict[str, Any] = {
                        "type": "metadata",
                        "mode": getattr(pipeline, "last_mode", "rag_v2"),
                        "route": getattr(pipeline, "last_intent", "rag"),
                        "intent": getattr(pipeline, "last_intent", "rag"),
                        "num_sources": len(getattr(pipeline, "last_sources", [])),
                        "retrieved_documents": getattr(pipeline, "last_sources", []),
                        "timings_ms": getattr(pipeline, "last_timings", {}),
                        "reflected_question": getattr(
                            pipeline, "last_reflected_question", None
                        ),
                        "target_collections": getattr(
                            pipeline, "last_target_collections", None
                        ),
                        "collection_scores": getattr(
                            pipeline, "last_collection_scores", None
                        ),
                        "routing_probabilities": getattr(
                            pipeline, "last_routing_probabilities", None
                        ),
                        "applied_filters": getattr(
                            pipeline, "last_applied_filters", None
                        ),
                        "collection_results": getattr(
                            pipeline, "last_collection_results", None
                        ),
                        "agent_trace": getattr(pipeline, "last_agent_trace", None),
                        "tools_used": getattr(pipeline, "last_tools_used", []),
                        "iterations": getattr(pipeline, "last_iterations", 0),
                    }
                    yield (
                        "data: "
                        + json.dumps(meta_payload, ensure_ascii=False)
                        + "\n\n"
                    )
                except Exception as meta_err:
                    logger.warning("Failed to emit metadata SSE event: %s", meta_err)
                # ── Done event ───────────────────────────────────────────────
                yield (
                    "data: "
                    + json.dumps({"type": "done"}, ensure_ascii=False)
                    + "\n\n"
                )
                break
            yield (
                "data: "
                + json.dumps(
                    {"type": "token", "delta": str(chunk)},
                    ensure_ascii=False,
                )
                + "\n\n"
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
