"""Chat API routes — non-streaming and SSE streaming endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from schemas.chat import (
    AgentToolCall,
    AgentTracePayload,
    ChatRequest,
    ChatResponse,
    CollectionResult,
    FilterInfo,
    RetrievedDocument,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_string_list(raw_value: Any) -> list[str] | None:
    if not isinstance(raw_value, list):
        return None
    values = [str(item) for item in raw_value if item is not None]
    return values or None


def _to_tool_call_models(raw_calls: Any) -> list[AgentToolCall] | None:
    if not isinstance(raw_calls, list):
        return None

    models: list[AgentToolCall] = []
    for call in raw_calls:
        if isinstance(call, AgentToolCall):
            models.append(call)
            continue
        if not isinstance(call, dict):
            continue

        args = call.get("args")
        if not isinstance(args, dict):
            args = {}

        models.append(
            AgentToolCall(
                tool=str(call.get("tool") or "unknown"),
                args=args,
                result=str(call.get("result") or ""),
                iteration=int(call.get("iteration", 0) or 0),
                latency_ms=_optional_float(call.get("latency_ms")),
                timestamp=(
                    str(call.get("timestamp"))
                    if call.get("timestamp") is not None
                    else None
                ),
            )
        )

    return models or None


def _to_agent_trace_model(raw_trace: Any) -> AgentTracePayload | None:
    if not isinstance(raw_trace, dict):
        return None

    tool_calls = _to_tool_call_models(raw_trace.get("tool_calls"))
    return AgentTracePayload(
        query=(str(raw_trace.get("query")) if raw_trace.get("query") is not None else None),
        session_id=(
            str(raw_trace.get("session_id"))
            if raw_trace.get("session_id") is not None
            else None
        ),
        route=(str(raw_trace.get("route")) if raw_trace.get("route") is not None else None),
        iterations=_optional_int(raw_trace.get("iterations")),
        tool_calls=tool_calls,
        tool_names_sequence=_to_string_list(raw_trace.get("tool_names_sequence")),
        final_answer_length=_optional_int(raw_trace.get("final_answer_length")),
        latency_ms=_optional_float(raw_trace.get("latency_ms")),
        error=(str(raw_trace.get("error")) if raw_trace.get("error") is not None else None),
    )


def _to_filter_models(raw_filters: Any) -> list[FilterInfo] | None:
    if not raw_filters:
        return None

    if isinstance(raw_filters, dict):
        models = [
            FilterInfo(
                collection=str(col),
                applied=bool(info.get("applied")),
                matched_ids=int(info.get("matched_ids", 0)),
                filter_desc=info.get("filter_desc"),
            )
            for col, info in raw_filters.items()
            if isinstance(info, dict)
        ]
        return models or None

    if isinstance(raw_filters, list):
        models: list[FilterInfo] = []
        for item in raw_filters:
            if isinstance(item, FilterInfo):
                models.append(item)
                continue
            if isinstance(item, dict):
                models.append(
                    FilterInfo(
                        collection=str(item.get("collection", "")),
                        applied=bool(item.get("applied")),
                        matched_ids=int(item.get("matched_ids", 0)),
                        filter_desc=item.get("filter_desc"),
                    )
                )
        return models or None

    return None


def _to_collection_result_models(raw_counts: Any) -> list[CollectionResult] | None:
    if not raw_counts:
        return None

    if isinstance(raw_counts, dict):
        models = [
            CollectionResult(
                collection=str(col),
                vector_count=int(counts.get("vector", 0)),
                keyword_count=int(counts.get("keyword", 0)),
            )
            for col, counts in raw_counts.items()
            if isinstance(counts, dict)
        ]
        return models or None

    if isinstance(raw_counts, list):
        models: list[CollectionResult] = []
        for item in raw_counts:
            if isinstance(item, CollectionResult):
                models.append(item)
                continue
            if isinstance(item, dict):
                models.append(
                    CollectionResult(
                        collection=str(item.get("collection", "")),
                        vector_count=int(item.get("vector_count", 0)),
                        keyword_count=int(item.get("keyword_count", 0)),
                    )
                )
        return models or None

    return None


def _to_chat_response(
    result: dict[str, Any],
    *,
    fallback_question: str,
    session_id: str,
) -> ChatResponse:
    normalized = _normalize_v3_result(result, session_id)

    raw_docs = normalized.get("retrieved_documents")
    if not isinstance(raw_docs, list):
        raw_docs = _to_retrieved_documents(normalized.get("sources"))

    retrieved_docs: list[RetrievedDocument] = []
    for idx, doc in enumerate(raw_docs, 1):
        if isinstance(doc, RetrievedDocument):
            retrieved_docs.append(doc)
            continue
        if not isinstance(doc, dict):
            continue

        metadata = doc.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        retrieved_docs.append(
            RetrievedDocument(
                rank=int(doc.get("rank", idx) or idx),
                content=str(doc.get("content", "")),
                score=_safe_float(doc.get("score", 0.0)),
                hybrid_score=_optional_float(doc.get("hybrid_score")),
                rerank_score=_optional_float(doc.get("rerank_score")),
                vector_score=_optional_float(doc.get("vector_score")),
                keyword_score=_optional_float(doc.get("keyword_score")),
                collection=doc.get("collection"),
                metadata=metadata,
            )
        )

    num_documents = normalized.get("num_documents")
    if num_documents is None:
        num_documents = normalized.get("num_sources")
    if num_documents is None:
        num_documents = len(retrieved_docs)

    mode = str(normalized.get("mode")) if normalized.get("mode") is not None else None
    route = str(normalized.get("route")) if normalized.get("route") is not None else None
    tools_used = _to_string_list(normalized.get("tools_used"))
    tool_calls = _to_tool_call_models(normalized.get("tool_calls"))
    agent_trace = _to_agent_trace_model(normalized.get("agent_trace"))

    if tools_used is None and agent_trace and agent_trace.tool_names_sequence:
        tools_used = list(agent_trace.tool_names_sequence)
    if tool_calls is None and agent_trace and agent_trace.tool_calls:
        tool_calls = list(agent_trace.tool_calls)

    return ChatResponse(
        question=str(normalized.get("question") or fallback_question),
        answer=str(normalized.get("answer") or ""),
        retrieved_documents=retrieved_docs,
        num_documents=int(num_documents),
        model_name=str(normalized.get("model_name") or normalized.get("mode") or "unknown"),
        intent=str(normalized.get("intent") or normalized.get("route") or "rag"),
        target_collections=normalized.get("target_collections"),
        collection_scores=normalized.get("collection_scores"),
        reflected_question=normalized.get("reflected_question"),
        timings_ms=normalized.get("timings_ms"),
        session_id=str(normalized.get("session_id") or session_id),
        routing_probabilities=normalized.get("routing_probabilities"),
        reflection_prompt=normalized.get("reflection_prompt"),
        llm_prompt=normalized.get("llm_prompt"),
        applied_filters=_to_filter_models(normalized.get("applied_filters")),
        collection_results=_to_collection_result_models(normalized.get("collection_results")),
        mode=mode,
        route=route,
        tools_used=tools_used,
        tool_calls=tool_calls,
        iterations=_optional_int(normalized.get("iterations")),
        error=(str(normalized.get("error")) if normalized.get("error") is not None else None),
        agent_error=(
            str(normalized.get("agent_error"))
            if normalized.get("agent_error") is not None
            else None
        ),
        agent_trace=agent_trace,
    )


def _to_retrieved_documents(sources: Any) -> list[dict[str, Any]]:
    """Convert pipeline ``sources`` payload into ChatResponse-compatible docs."""
    if not isinstance(sources, list):
        return []

    converted: list[dict[str, Any]] = []
    for idx, doc in enumerate(sources, 1):
        if not isinstance(doc, dict):
            continue
        converted.append(
            {
                "rank": idx,
                "content": doc.get("text", ""),
                "score": doc.get("rerank_score", doc.get("score", 0.0)),
                "hybrid_score": doc.get("score"),
                "rerank_score": doc.get("rerank_score"),
                "vector_score": doc.get("vector_score"),
                "keyword_score": doc.get("keyword_score"),
                "collection": doc.get("collection"),
                "metadata": doc.get("metadata", {}),
            }
        )
    return converted


def _normalize_v3_result(result: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Ensure /chat/v3 returns a stable shape for UI trace/debug rendering."""
    normalized = dict(result)
    normalized.setdefault("session_id", session_id)

    if "retrieved_documents" not in normalized:
        normalized["retrieved_documents"] = _to_retrieved_documents(
            normalized.get("sources")
        )

    normalized.setdefault(
        "num_documents",
        normalized.get("num_sources", len(normalized.get("retrieved_documents", []))),
    )
    normalized.setdefault("tools_used", [])
    normalized.setdefault("tool_calls", [])
    normalized.setdefault("iterations", 0)
    normalized.setdefault("agent_trace", None)

    if (
        not normalized.get("tool_calls")
        and isinstance(normalized.get("agent_trace"), dict)
        and isinstance(normalized["agent_trace"].get("tool_calls"), list)
    ):
        normalized["tool_calls"] = normalized["agent_trace"]["tool_calls"]

    if (
        not normalized.get("tools_used")
        and isinstance(normalized.get("agent_trace"), dict)
        and isinstance(normalized["agent_trace"].get("tool_names_sequence"), list)
    ):
        normalized["tools_used"] = normalized["agent_trace"]["tool_names_sequence"]

    return normalized


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
    if not str(result.get("mode", "")).lower().startswith("agent"):
        return
    if not hasattr(mongo_logger, "log_turn"):
        return

    legacy_result = dict(result)
    legacy_result.setdefault("intent", str(result.get("route") or "complex"))
    legacy_result.setdefault("model_name", str(result.get("mode") or "agent"))
    if not isinstance(legacy_result.get("sources"), list):
        legacy_result["sources"] = []
    legacy_result.setdefault("num_sources", len(legacy_result["sources"]))

    latency_ms = int((time.perf_counter() - request_started_at) * 1000)
    agent_trace = legacy_result.get("agent_trace")
    if isinstance(agent_trace, dict):
        latency_ms = int(
            _safe_float(agent_trace.get("latency_ms"), float(latency_ms))
        )

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
    """Process a question and return the full answer."""
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")

    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    # Resolve session: create new if absent or stale
    session_id = body.session_id
    if mongo_logger is not None:
        if session_id is None or mongo_logger.get_session(session_id) is None:
            session_id = mongo_logger.new_session(user_id=body.user_id)

    history = (
        [{"role": m.role, "content": m.content} for m in body.history]
        if body.history
        else []
    )
    mode = (body.mode or "auto").lower()
    if mode != "agent":
        logger.info("/chat forces agent mode (requested=%s)", mode)

    user_context_payload = (
        body.user_context.model_dump() if body.user_context else None
    )
    request_t0 = time.perf_counter()

    try:
        loop = asyncio.get_event_loop()
        if hasattr(pipeline, "query_agent"):
            if getattr(pipeline, "agent", None) is None:
                raise HTTPException(
                    status_code=503,
                    detail="Agent is required for /chat but is disabled",
                )
            result = await loop.run_in_executor(
                None,
                lambda: pipeline.query_agent(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=user_context_payload,
                    route_label="agent_forced",
                    require_agent=True,
                ),
            )
        else:
            if getattr(pipeline, "agent", None) is None:
                raise HTTPException(
                    status_code=503,
                    detail="Agent is required for /chat but is disabled",
                )
            state = await loop.run_in_executor(
                None,
                lambda: pipeline.agent.run(
                    body.question,
                    session_id=session_id or "",
                    history=history,
                ),
            )
            tool_calls = [tr.to_dict() for tr in state.tool_results]
            agent_trace = state.to_log_dict()
            agent_trace["latency_ms"] = round(
                (time.perf_counter() - request_t0) * 1000,
                2,
            )
            result = {
                "question": body.question,
                "answer": state.final_answer or "",
                "mode": "agent",
                "route": "agent_forced",
                "intent": "agent_forced",
                "model_name": "agent",
                "tools_used": list(state.tool_call_history),
                "tool_calls": tool_calls,
                "iterations": state.iteration,
                "error": state.error,
                "agent_error": state.error,
                "agent_trace": agent_trace,
                "timings_ms": {
                    "agent_total": agent_trace["latency_ms"],
                    "pipeline_total": agent_trace["latency_ms"],
                },
            }

        if mongo_logger is not None:
            _log_legacy_turn_for_agent_response(
                mongo_logger=mongo_logger,
                session_id=session_id,
                question=body.question,
                result=result,
                request_started_at=request_t0,
            )

        return _to_chat_response(
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
    session_id = body.session_id
    if mongo_logger is not None:
        if session_id is None or mongo_logger.get_session(session_id) is None:
            session_id = mongo_logger.new_session(user_id=body.user_id)

    history = (
        [{"role": m.role, "content": m.content} for m in body.history]
        if body.history
        else []
    )
    mode = (body.mode or "auto").lower()

    try:
        loop = asyncio.get_event_loop()

        if mode == "rag":
            result = await loop.run_in_executor(
                None,
                lambda: pipeline.query(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=(
                        body.user_context.model_dump() if body.user_context else None
                    ),
                ),
            )
            result.setdefault("mode", "rag_v2")
            result.setdefault("route", "simple")
            result.setdefault("tools_used", [])
            result.setdefault("iterations", 0)
            return _normalize_v3_result(result, session_id or "")

        if mode == "agent":
            if hasattr(pipeline, "query_agent"):
                result = await loop.run_in_executor(
                    None,
                    lambda: pipeline.query_agent(
                        question=body.question,
                        history=history,
                        top_k=body.top_k,
                        session_id=session_id,
                        user_context=(
                            body.user_context.model_dump()
                            if body.user_context
                            else None
                        ),
                        route_label="complex",
                        require_agent=False,
                    ),
                )
                return _normalize_v3_result(result, session_id or "")

            if getattr(pipeline, "agent", None) is None:
                result = await loop.run_in_executor(
                    None,
                    lambda: pipeline.query(
                        question=body.question,
                        history=history,
                        top_k=body.top_k,
                        session_id=session_id,
                        user_context=(
                            body.user_context.model_dump()
                            if body.user_context
                            else None
                        ),
                    ),
                )
                result["mode"] = "rag_v2_fallback"
                result["route"] = "complex"
                result["tools_used"] = []
                result["iterations"] = 0
                result["agent_error"] = "Agent is disabled"
                result["tool_calls"] = []
                result["agent_trace"] = {
                    "query": body.question,
                    "session_id": session_id or "",
                    "route": "complex",
                    "iterations": 0,
                    "tool_calls": [],
                    "tool_names_sequence": [],
                    "final_answer_length": 0,
                    "error": "Agent is disabled",
                }
                return _normalize_v3_result(result, session_id or "")

            state = await loop.run_in_executor(
                None,
                lambda: pipeline.agent.run(
                    body.question,
                    session_id=session_id or "",
                    history=history,
                ),
            )
            tool_calls = [tr.to_dict() for tr in state.tool_results]
            return _normalize_v3_result({
                "question": body.question,
                "answer": state.final_answer or "",
                "mode": "agent",
                "route": "complex",
                "tools_used": list(state.tool_call_history),
                "tool_calls": tool_calls,
                "iterations": state.iteration,
                "error": state.error,
                "agent_error": state.error,
                "agent_trace": state.to_log_dict(),
            }, session_id or "")

        result = await loop.run_in_executor(
            None,
            lambda: pipeline.query_v3(
                question=body.question,
                history=history,
                top_k=body.top_k,
                session_id=session_id,
                user_context=(
                    body.user_context.model_dump() if body.user_context else None
                ),
            ),
        )
        return _normalize_v3_result(result, session_id or "")

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

    # Resolve session: create new if absent or stale
    session_id = body.session_id
    if mongo_logger is not None:
        if session_id is None or mongo_logger.get_session(session_id) is None:
            session_id = mongo_logger.new_session(user_id=body.user_id)

    history = (
        [{"role": m.role, "content": m.content} for m in body.history]
        if body.history
        else []
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

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _produce():
            try:
                for chunk in pipeline.query_stream(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                    user_context=(
                        body.user_context.model_dump()
                        if body.user_context
                        else None
                    ),
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _produce)

        while True:
            chunk = await queue.get()
            if chunk is None:
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
