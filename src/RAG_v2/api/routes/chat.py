"""Chat API routes — non-streaming and SSE streaming endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest, ChatResponse, RetrievedDocument

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


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
            session_id = mongo_logger.new_session()

    history = (
        [{"role": m.role, "content": m.content} for m in body.history]
        if body.history
        else []
    )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: pipeline.query(
                question=body.question,
                history=history,
                top_k=body.top_k,
                session_id=session_id,
            ),
        )

        retrieved_docs = [
            RetrievedDocument(
                rank=i,
                content=doc.get("text", ""),
                score=doc.get("rerank_score", doc.get("score", 0.0)),
                metadata=doc.get("metadata", {}),
            )
            for i, doc in enumerate(result["sources"], 1)
        ]

        return ChatResponse(
            question=result["question"],
            answer=result["answer"],
            retrieved_documents=retrieved_docs,
            num_documents=result["num_sources"],
            model_name=result["model_name"],
            intent=result.get("intent", "rag"),
            session_id=session_id or "",
        )

    except Exception as exc:
        logger.error("/chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# POST /chat/stream — SSE streaming
# ------------------------------------------------------------------


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """Server-Sent Events streaming endpoint.

    Each chunk is sent as ``data: <text>\\n\\n``.  A final
    ``data: [DONE]\\n\\n`` signals end-of-stream.
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised")

    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    # Resolve session: create new if absent or stale
    session_id = body.session_id
    if mongo_logger is not None:
        if session_id is None or mongo_logger.get_session(session_id) is None:
            session_id = mongo_logger.new_session()

    history = (
        [{"role": m.role, "content": m.content} for m in body.history]
        if body.history
        else []
    )

    async def event_generator():
        # Send session_id as first SSE event
        if session_id:
            yield f'data: {{"session_id": "{session_id}"}}\n\n'

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _produce():
            try:
                for chunk in pipeline.query_stream(
                    question=body.question,
                    history=history,
                    top_k=body.top_k,
                    session_id=session_id,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _produce)

        while True:
            chunk = await queue.get()
            if chunk is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
