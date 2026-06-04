"""Pydantic schemas for chat and health API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Request models
# ═══════════════════════════════════════════════════════════════════════════════


class HistoryMessage(BaseModel):
    """A single message in the chat history."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class UserContext(BaseModel):
    """Authenticated user profile forwarded with each chat request."""

    student_id: Optional[str] = None
    cohort: Optional[str] = None
    major: Optional[str] = None
    major_code: Optional[str] = None
    full_name: Optional[str] = None


class ChatRequest(BaseModel):
    """Body for ``POST /chat`` and ``POST /chat/stream``."""

    question: str = Field(..., min_length=1, max_length=4096)
    mode: str = Field(default="auto", pattern="^(auto|rag|agent)$")
    top_k: int = Field(default=7, ge=1, le=50)
    history: Optional[List[HistoryMessage]] = None
    session_id: Optional[str] = None
    user_context: Optional[UserContext] = None
    user_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Response models
# ═══════════════════════════════════════════════════════════════════════════════


class RetrievedDocument(BaseModel):
    """A single retrieved source document."""

    rank: int
    content: str
    score: float
    # Score breakdown (populated when trace data is available)
    hybrid_score: Optional[float] = None   # pre-rerank fusion score
    rerank_score: Optional[float] = None   # cross-encoder score
    vector_score: Optional[float] = None   # raw Qdrant cosine score
    keyword_score: Optional[float] = None  # raw BM25 score
    collection: Optional[str] = None       # source collection name
    metadata: Dict[str, Any]


class CollectionScore(BaseModel):
    """Router confidence score for a target collection."""

    collection: str
    score: float


class FilterInfo(BaseModel):
    """Metadata pre-filter applied to a single collection before hybrid search."""

    collection: str
    applied: bool                       # True if a filter narrowed the results
    matched_ids: int = 0                # number of doc IDs matched by the filter
    filter_desc: Optional[str] = None  # human-readable filter description


class CollectionResult(BaseModel):
    """Per-collection raw retrieval counts before global score fusion."""

    collection: str
    vector_count: int = 0
    keyword_count: int = 0


class AgentToolCall(BaseModel):
    """One agent tool invocation record."""

    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    result: str
    iteration: int = 0
    latency_ms: Optional[float] = None
    timestamp: Optional[str] = None


class AgentTracePayload(BaseModel):
    """Compact execution trace produced by the agent loop."""

    query: Optional[str] = None
    session_id: Optional[str] = None
    route: Optional[str] = None
    execution_path: Optional[str] = None
    complexity_subtype: Optional[str] = None
    sub_questions: Optional[List[str]] = None
    retrieval_plan: Optional[Dict[str, Any]] = None
    decompose_trace: Optional[Dict[str, Any]] = None
    planner_trace: Optional[Dict[str, Any]] = None
    executor_results: Optional[List[Dict[str, Any]]] = None
    synthesis_trace: Optional[Dict[str, Any]] = None
    iterations: Optional[int] = None
    tool_calls: Optional[List[AgentToolCall]] = None
    tool_names_sequence: Optional[List[str]] = None
    final_answer_length: Optional[int] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class ChatResponse(BaseModel):
    """Response body for ``POST /chat``."""

    question: str
    answer: str
    retrieved_documents: List[RetrievedDocument]
    num_documents: int
    model_name: str
    intent: str
    target_collections: Optional[List[str]] = None
    collection_scores: Optional[List[CollectionScore]] = None
    reflected_question: Optional[str] = None
    timings_ms: Optional[Dict[str, float]] = None
    session_id: str
    turn_id: Optional[int] = None
    # Extended trace fields
    routing_probabilities: Optional[Dict[str, float]] = None
    reflection_prompt: Optional[str] = None
    llm_prompt: Optional[str] = None
    applied_filters: Optional[List[FilterInfo]] = None
    collection_results: Optional[List[CollectionResult]] = None
    context_trace: Optional[Dict[str, Any]] = None
    rerank_trace: Optional[Dict[str, Any]] = None
    answer_quality_gate: Optional[Dict[str, Any]] = None
    fusion_weights: Optional[Dict[str, Any]] = None
    answer_status: Optional[str] = None
    # Agent + route telemetry
    mode: Optional[str] = None
    route: Optional[str] = None
    tools_used: Optional[List[str]] = None
    tool_calls: Optional[List[AgentToolCall]] = None
    iterations: Optional[int] = None
    error: Optional[str] = None
    agent_error: Optional[str] = None
    agent_trace: Optional[AgentTracePayload] = None


class HealthResponse(BaseModel):
    """Response body for ``GET /health``."""

    status: str
    rag_initialized: bool
    mongo_status: str = "unknown"  # ok | degraded | failed | disabled | unknown
    redis_status: str = "disabled"  # ok | failed | disabled | not_installed
