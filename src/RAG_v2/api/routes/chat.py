"""Chat API routes — non-streaming and SSE streaming endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Annotated, Any

import anyio
import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from api.dependencies import (
    parse_history,
    resolve_session,
    sync_redis_session_from_mongo,
    user_context_from_user,
    user_id_from_user,
)
from api.response_mapper import ChatResponseMapper
from auth.jwt_handler import get_optional_current_user
from models.user import UserDocument
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
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
) -> ChatResponse:
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
    resolved_user_id = user_id_from_user(current_user) or body.user_id
    session_id = await anyio.to_thread.run_sync(
        lambda: resolve_session(
            session_id=body.session_id,
            user_id=resolved_user_id,
            mongo_logger=mongo_logger,
            redis_session=redis_session,
        )
    )
    history = parse_history(body.history)
    mode = (body.mode or RouteMode.AUTO).lower()
    logger.info("/chat mode=%s question=%r", mode, body.question[:80])

    user_context_payload = user_context_from_user(current_user) or (
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
            await anyio.to_thread.run_sync(
                lambda: _log_legacy_turn_for_agent_response(
                    mongo_logger=mongo_logger,
                    session_id=session_id,
                    question=body.question,
                    result=result,
                    request_started_at=request_t0,
                )
            )
        await anyio.to_thread.run_sync(
            lambda: sync_redis_session_from_mongo(
                redis_session=redis_session,
                mongo_logger=mongo_logger,
                session_id=session_id,
            )
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
async def chat_v3(
    request: Request,
    body: ChatRequest,
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
) -> dict[str, Any]:
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
    resolved_user_id = user_id_from_user(current_user) or body.user_id
    session_id = await anyio.to_thread.run_sync(
        lambda: resolve_session(
            session_id=body.session_id,
            user_id=resolved_user_id,
            mongo_logger=mongo_logger,
            redis_session=redis_session,
        )
    )
    history = parse_history(body.history)
    mode = (body.mode or RouteMode.AUTO).lower()
    user_context_payload = user_context_from_user(current_user) or (
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
            await anyio.to_thread.run_sync(
                lambda: sync_redis_session_from_mongo(
                    redis_session=redis_session,
                    mongo_logger=mongo_logger,
                    session_id=session_id,
                )
            )
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
                await anyio.to_thread.run_sync(
                    lambda: sync_redis_session_from_mongo(
                        redis_session=redis_session,
                        mongo_logger=mongo_logger,
                        session_id=session_id,
                    )
                )
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
            await anyio.to_thread.run_sync(
                lambda: sync_redis_session_from_mongo(
                    redis_session=redis_session,
                    mongo_logger=mongo_logger,
                    session_id=session_id,
                )
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
        await anyio.to_thread.run_sync(
            lambda: sync_redis_session_from_mongo(
                redis_session=redis_session,
                mongo_logger=mongo_logger,
                session_id=session_id,
            )
        )
        return ChatResponseMapper.normalize_v3_result(result, session_id or "")

    except Exception as exc:
        logger.error("/chat/v3 error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/chat/suggest")
async def suggest_questions(
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
    cohort: str | None = Query(default=None),
    major: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return lightweight suggested questions personalized by profile hints."""
    resolved_cohort = cohort or (current_user.cohort if current_user else None)
    resolved_major = major or (current_user.major if current_user else None)
    base = [
        ("Điều kiện xét học bổng kỳ này là gì?", "quydinh", 0.95),
        ("Quy định chuẩn ngoại ngữ tốt nghiệp hiện tại?", "quydinh", 0.93),
        ("Lịch đăng ký học phần kỳ tới khi nào?", "kehoach", 0.9),
        ("Thủ tục xin xác nhận sinh viên thực hiện thế nào?", "stsv", 0.86),
    ]
    if resolved_major:
        base.insert(
            0,
            (
                f"Chương trình đào tạo ngành {resolved_major} gồm những học phần nào?",
                "ctdt",
                0.98,
            ),
        )
    if resolved_cohort:
        base.insert(
            0,
            (
                f"Quy định tốt nghiệp áp dụng cho {resolved_cohort} là gì?",
                "quydinh",
                0.99,
            ),
        )
    return {
        "suggestions": [
            {"question": question, "category": category, "popularity": popularity}
            for question, category, popularity in base[:6]
        ]
    }


# ------------------------------------------------------------------
# POST /chat/stream — SSE streaming
# ------------------------------------------------------------------


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
) -> StreamingResponse:
    """Server-Sent Events streaming endpoint.

        Emits JSON payloads as SSE ``data`` frames:
            - ``{"type":"session","session_id":"..."}``
            - ``{"type":"status","stage":"...","message":"..."}`` (progress, agent path)
            - ``{"type":"token","delta":"..."}``
            - ``{"type":"error","error":"..."}``
            - ``{"type":"metadata", ...}``
            - ``{"type":"done"}``
        Also emits ``: heartbeat`` SSE comment frames every ~15s of idle to keep
        proxies/load balancers from closing the connection during long requests.
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")

    mongo_logger = getattr(request.app.state, "mongo_logger", None)
    redis_session = getattr(request.app.state, "redis_session", None)
    resolved_user_id = user_id_from_user(current_user) or body.user_id
    session_id = await anyio.to_thread.run_sync(
        lambda: resolve_session(
            session_id=body.session_id,
            user_id=resolved_user_id,
            mongo_logger=mongo_logger,
            redis_session=redis_session,
        )
    )
    history = parse_history(body.history)
    user_context_payload = user_context_from_user(current_user) or (
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
        # Per-request metadata sink — avoids racing on the singleton pipeline's
        # self.last_* attrs when concurrent streams run (see query_stream docstring).
        request_metadata: dict[str, Any] = {}

        def _produce():
            try:
                for chunk in pipeline.query_stream(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=user_context_payload,
                    metadata_out=request_metadata,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as exc:
                logger.error("/chat/stream producer failed: %s", exc, exc_info=True)
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "error": str(exc)},
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _produce)
        producer_error = False

        while True:
            # Client gone? Stop forwarding. NOTE: the _produce thread runs a
            # synchronous generator that can't be force-killed mid-step, so any
            # in-flight LLM/agent call still finishes in the background — but we
            # stop draining the queue and free this response coroutine promptly.
            if await request.is_disconnected():
                logger.info("/chat/stream client disconnected; stopping forward")
                break
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    logger.info(
                        "/chat/stream client disconnected (idle); stopping"
                    )
                    break
                # Heartbeat comment frame — ignored by SSE clients, keeps the
                # connection alive through proxies during long agent runs.
                yield ": heartbeat\n\n"
                continue
            if isinstance(chunk, dict) and chunk.get("type") == "error":
                producer_error = True
                yield (
                    "data: "
                    + json.dumps(chunk, ensure_ascii=False)
                    + "\n\n"
                )
                continue
            if isinstance(chunk, dict) and chunk.get("type") == "status":
                # Progress event (e.g. agent retrieval/synthesis stages).
                yield (
                    "data: "
                    + json.dumps(chunk, ensure_ascii=False)
                    + "\n\n"
                )
                continue
            if chunk is None:
                await anyio.to_thread.run_sync(
                    lambda: sync_redis_session_from_mongo(
                        redis_session=redis_session,
                        mongo_logger=mongo_logger,
                        session_id=session_id,
                    )
                )
                # ── Emit metadata SSE event before done ──────────────────────
                if not producer_error:
                    try:
                        meta_payload: dict[str, Any] = {
                            "type": "metadata",
                            "mode": request_metadata.get("mode", "rag_v2"),
                            "route": request_metadata.get("route", "rag"),
                            "intent": request_metadata.get("intent", "rag"),
                            "num_sources": request_metadata.get("num_sources", 0),
                            "retrieved_documents": request_metadata.get(
                                "retrieved_documents", []
                            ),
                            "timings_ms": request_metadata.get("timings_ms", {}),
                            "reflected_question": request_metadata.get(
                                "reflected_question"
                            ),
                            "target_collections": request_metadata.get(
                                "target_collections"
                            ),
                            "collection_scores": request_metadata.get(
                                "collection_scores"
                            ),
                            "routing_probabilities": request_metadata.get(
                                "routing_probabilities"
                            ),
                            "applied_filters": request_metadata.get("applied_filters"),
                            "collection_results": request_metadata.get(
                                "collection_results"
                            ),
                            "context_trace": request_metadata.get("context_trace"),
                            "rerank_trace": request_metadata.get("rerank_trace"),
                            "answer_quality_gate": request_metadata.get(
                                "answer_quality_gate"
                            ),
                            "fusion_weights": request_metadata.get("fusion_weights"),
                            "agent_trace": request_metadata.get("agent_trace"),
                            "tools_used": request_metadata.get("tools_used", []),
                            "tool_calls": request_metadata.get("tool_calls", []),
                            "iterations": request_metadata.get("iterations", 0),
                            "turn_id": request_metadata.get("turn_id"),
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
            if not isinstance(chunk, str):
                # Defensive: only str chunks are answer tokens; drop anything else.
                continue
            yield (
                "data: "
                + json.dumps(
                    {"type": "token", "delta": chunk},
                    ensure_ascii=False,
                )
                + "\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # Keep tokens flowing token-by-token: stop reverse proxies (nginx)
            # and browsers from buffering the SSE body into chunks.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
