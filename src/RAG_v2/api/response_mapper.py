"""Response mapping utilities for chat API endpoints.

Migrated from api/routes/chat.py to separate concerns:
  - chat.py  → HTTP routing & orchestration only
  - response_mapper.py → dict → Pydantic model conversion

All methods are @staticmethod so ChatResponseMapper can be used
without instantiation while still being logically grouped.
"""

from __future__ import annotations

from typing import Any

from schemas.chat import (
    AgentToolCall,
    AgentTracePayload,
    ChatResponse,
    CollectionResult,
    FilterInfo,
    RetrievedDocument,
)


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


class ChatResponseMapper:
    """Static helpers that convert raw pipeline dicts → Pydantic response models."""

    # ─── Public API ───────────────────────────────────────────────────────────

    @staticmethod
    def to_chat_response(
        result: dict[str, Any],
        *,
        fallback_question: str,
        session_id: str,
    ) -> ChatResponse:
        """Convert a pipeline result dict to a ``ChatResponse`` Pydantic model."""
        normalized = ChatResponseMapper.normalize_v3_result(result, session_id)

        raw_docs = normalized.get("retrieved_documents")
        if not isinstance(raw_docs, list):
            raw_docs = ChatResponseMapper._to_retrieved_documents(
                normalized.get("sources")
            )

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
        tool_calls = ChatResponseMapper.to_tool_call_models(normalized.get("tool_calls"))
        agent_trace = ChatResponseMapper.to_agent_trace_model(normalized.get("agent_trace"))

        if tools_used is None and agent_trace and agent_trace.tool_names_sequence:
            tools_used = list(agent_trace.tool_names_sequence)
        if tool_calls is None and agent_trace and agent_trace.tool_calls:
            tool_calls = list(agent_trace.tool_calls)

        return ChatResponse(
            question=str(normalized.get("question") or fallback_question),
            answer=str(normalized.get("answer") or ""),
            retrieved_documents=retrieved_docs,
            num_documents=int(num_documents),
            model_name=str(
                normalized.get("model_name") or normalized.get("mode") or "unknown"
            ),
            intent=str(normalized.get("intent") or normalized.get("route") or "rag"),
            target_collections=normalized.get("target_collections"),
            collection_scores=normalized.get("collection_scores"),
            reflected_question=normalized.get("reflected_question"),
            timings_ms=normalized.get("timings_ms"),
            session_id=str(normalized.get("session_id") or session_id),
            routing_probabilities=normalized.get("routing_probabilities"),
            reflection_prompt=normalized.get("reflection_prompt"),
            llm_prompt=normalized.get("llm_prompt"),
            applied_filters=ChatResponseMapper.to_filter_models(
                normalized.get("applied_filters")
            ),
            collection_results=ChatResponseMapper.to_collection_result_models(
                normalized.get("collection_results")
            ),
            mode=mode,
            route=route,
            tools_used=tools_used,
            tool_calls=tool_calls,
            iterations=_optional_int(normalized.get("iterations")),
            error=(
                str(normalized.get("error"))
                if normalized.get("error") is not None
                else None
            ),
            agent_error=(
                str(normalized.get("agent_error"))
                if normalized.get("agent_error") is not None
                else None
            ),
            agent_trace=agent_trace,
        )

    @staticmethod
    def normalize_v3_result(
        result: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        """Ensure /chat/v3 returns a stable shape for UI trace/debug rendering."""
        normalized = dict(result)
        normalized.setdefault("session_id", session_id)

        if "retrieved_documents" not in normalized:
            normalized["retrieved_documents"] = (
                ChatResponseMapper._to_retrieved_documents(normalized.get("sources"))
            )

        normalized.setdefault(
            "num_documents",
            normalized.get(
                "num_sources", len(normalized.get("retrieved_documents", []))
            ),
        )
        normalized.setdefault("tools_used", [])
        normalized.setdefault("tool_calls", [])
        normalized.setdefault("iterations", 0)
        normalized.setdefault("agent_trace", None)

        # Backfill tool_calls from agent_trace when top-level is empty
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

    @staticmethod
    def to_tool_call_models(raw_calls: Any) -> list[AgentToolCall] | None:
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

    @staticmethod
    def to_agent_trace_model(raw_trace: Any) -> AgentTracePayload | None:
        if not isinstance(raw_trace, dict):
            return None

        tool_calls = ChatResponseMapper.to_tool_call_models(raw_trace.get("tool_calls"))
        return AgentTracePayload(
            query=(
                str(raw_trace.get("query"))
                if raw_trace.get("query") is not None
                else None
            ),
            session_id=(
                str(raw_trace.get("session_id"))
                if raw_trace.get("session_id") is not None
                else None
            ),
            route=(
                str(raw_trace.get("route"))
                if raw_trace.get("route") is not None
                else None
            ),
            iterations=_optional_int(raw_trace.get("iterations")),
            tool_calls=tool_calls,
            tool_names_sequence=_to_string_list(raw_trace.get("tool_names_sequence")),
            final_answer_length=_optional_int(raw_trace.get("final_answer_length")),
            latency_ms=_optional_float(raw_trace.get("latency_ms")),
            error=(
                str(raw_trace.get("error"))
                if raw_trace.get("error") is not None
                else None
            ),
        )

    @staticmethod
    def to_filter_models(raw_filters: Any) -> list[FilterInfo] | None:
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

    @staticmethod
    def to_collection_result_models(
        raw_counts: Any,
    ) -> list[CollectionResult] | None:
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

    # ─── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _to_retrieved_documents(sources: Any) -> list[dict[str, Any]]:
        """Convert pipeline ``sources`` payload into ChatResponse-compatible dicts."""
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
