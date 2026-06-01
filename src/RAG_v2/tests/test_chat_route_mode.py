"""Tests for /chat route mode behavior and legacy turn logging."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.routes.chat import chat
from schemas.chat import ChatRequest


class _FakeToolResult:
    def __init__(self) -> None:
        self._payload = {
            "tool": "compare_cohorts",
            "args": {
                "topic": "môn mạng máy tính",
                "cohort_a": "IT-E6",
                "cohort_b": "IT-E7",
                "collection": "chuong_trinh",
            },
            "result": "ok",
            "iteration": 1,
        }

    def to_dict(self) -> dict:
        return dict(self._payload)


class _FakeAgentState:
    def __init__(self) -> None:
        self.final_answer = "Agent answer"
        self.tool_call_history = ["compare_cohorts"]
        self.tool_results = [_FakeToolResult()]
        self.iteration = 2
        self.error = None

    def to_log_dict(self) -> dict:
        return {
            "query": "sample",
            "session_id": "",
            "route": "complex",
            "iterations": self.iteration,
            "tool_calls": [tr.to_dict() for tr in self.tool_results],
            "tool_names_sequence": list(self.tool_call_history),
            "final_answer_length": len(self.final_answer),
            "error": self.error,
        }


class _FakeAgent:
    def __init__(self) -> None:
        self.calls = 0
        self.last_history: list[dict] | None = None
        self.last_complexity_subtype: str | None = None
        self.last_top_k: int | None = None

    def run(
        self,
        question: str,
        session_id: str = "",
        history: list[dict] | None = None,
        complexity_subtype: str | None = None,
        user_context: dict | None = None,
        top_k: int | None = None,
    ) -> _FakeAgentState:
        self.calls += 1
        self.last_history = history
        self.last_complexity_subtype = complexity_subtype
        self.last_top_k = top_k
        return _FakeAgentState()


class _FakePipeline:
    def __init__(self) -> None:
        self.query_calls = 0
        self.query_v3_calls = 0
        self.query_agent_calls = 0
        self.agent = _FakeAgent()
        self.last_query_history: list[dict] | None = None
        self.last_query_agent_route_label: str | None = None
        self.last_query_agent_complexity_subtype: str | None = None

    def query(
        self,
        question: str,
        history: list[dict] | None = None,
        top_k: int | None = None,
        session_id: str | None = None,
        user_context: dict | None = None,
    ) -> dict:
        self.query_calls += 1
        self.last_query_history = history
        return {
            "question": question,
            "answer": "RAG answer",
            "sources": [
                {
                    "text": "doc",
                    "score": 0.7,
                    "metadata": {"source": "unit-test"},
                }
            ],
            "num_sources": 1,
            "model_name": "gemini",
            "intent": "rag",
            "mode": "rag_v2",
            "route": "simple",
        }

    def query_v3(
        self,
        question: str,
        history: list[dict] | None = None,
        top_k: int | None = None,
        session_id: str | None = None,
        user_context: dict | None = None,
    ) -> dict:
        self.query_v3_calls += 1
        return {
            "question": question,
            "answer": "Auto agent answer",
            "mode": "agent",
            "route": "complex",
            "intent": "complex",
            "model_name": "agent",
            "tools_used": ["compare_cohorts"],
            "tool_calls": [],
            "iterations": 2,
        }

    def query_agent(
        self,
        question: str,
        history: list[dict] | None = None,
        top_k: int | None = None,
        session_id: str | None = None,
        user_context: dict | None = None,
        *,
        route_label: str = "complex",
        require_agent: bool = False,
        complexity_subtype: str | None = None,
    ) -> dict:
        self.query_agent_calls += 1
        self.last_query_agent_route_label = route_label
        self.last_query_agent_complexity_subtype = complexity_subtype
        if self.agent is None and require_agent:
            raise RuntimeError("Agent is disabled")

        state = self.agent.run(
            question,
            session_id=session_id or "",
            history=history,
            complexity_subtype=complexity_subtype,
            user_context=user_context,
            top_k=top_k,
        )
        return {
            "question": question,
            "answer": state.final_answer,
            "mode": "agent",
            "route": route_label,
            "intent": route_label,
            "model_name": "agent",
            "tools_used": list(state.tool_call_history),
            "tool_calls": [tr.to_dict() for tr in state.tool_results],
            "iterations": state.iteration,
            "agent_trace": state.to_log_dict(),
            "timings_ms": {
                "agent_total": 120.0,
                "pipeline_total": 120.0,
            },
        }


class _FakeMongoLogger:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}
        self.logged_turns: list[dict] = []
        self.logged_agent_traces: list[dict] = []
        self._counter = 0

    def new_session(self, user_id: str | None = None) -> str:
        self._counter += 1
        sid = f"session-{self._counter}"
        self._sessions[sid] = {"session_id": sid, "user_id": user_id}
        return sid

    def get_session(self, session_id: str):
        return self._sessions.get(session_id)

    def log_turn(
        self,
        session_id: str,
        question: str,
        result: dict,
        *,
        reflected_question: str | None = None,
        latency_ms: int = 0,
        timings_ms: dict | None = None,
    ) -> int:
        self.logged_turns.append(
            {
                "session_id": session_id,
                "question": question,
                "result": result,
                "reflected_question": reflected_question,
                "latency_ms": latency_ms,
                "timings_ms": timings_ms,
            }
        )
        return len(self.logged_turns)

    def log_agent_trace(self, session_id: str, trace_dict: dict) -> None:
        self.logged_agent_traces.append(
            {"session_id": session_id, "trace": trace_dict}
        )


def _make_request(pipeline: _FakePipeline, mongo_logger: _FakeMongoLogger | None = None):
    state = SimpleNamespace(pipeline=pipeline, mongo_logger=mongo_logger)
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app)


@pytest.mark.anyio
async def test_chat_auto_mode_uses_query_v3_and_logs_turn() -> None:
    pipeline = _FakePipeline()
    mongo_logger = _FakeMongoLogger()
    request = _make_request(pipeline, mongo_logger)
    body = ChatRequest(
        question="môn mạng máy tính ở chương trình IT-E6 và IT-E7 có gì khác nhau",
        mode="auto",
        user_id="user-1",
    )

    response = await chat(request, body)

    assert pipeline.query_calls == 0
    assert pipeline.query_v3_calls == 1
    assert pipeline.query_agent_calls == 0
    assert pipeline.agent.calls == 0
    assert response.answer == "Auto agent answer"
    assert response.session_id == "session-1"
    assert response.mode == "agent"
    assert response.route == "complex"
    assert response.iterations == 2

    assert len(mongo_logger.logged_turns) == 1
    logged_turn = mongo_logger.logged_turns[0]
    assert logged_turn["question"] == body.question
    assert logged_turn["result"]["route"] == "complex"


@pytest.mark.anyio
async def test_chat_rag_mode_uses_classic_rag() -> None:
    pipeline = _FakePipeline()
    mongo_logger = _FakeMongoLogger()
    request = _make_request(pipeline, mongo_logger)
    body = ChatRequest(question="điều kiện học bổng KKHT", mode="rag")

    response = await chat(request, body)

    assert pipeline.query_calls == 1
    assert pipeline.query_v3_calls == 0
    assert pipeline.query_agent_calls == 0
    assert pipeline.agent.calls == 0
    assert response.answer == "RAG answer"
    assert response.intent == "rag"
    assert response.model_name == "gemini"
    assert response.mode == "rag_v2"
    assert response.route == "simple"
    assert len(mongo_logger.logged_turns) == 0


@pytest.mark.anyio
async def test_chat_agent_mode_uses_agent_runner_and_logs_legacy_turn() -> None:
    pipeline = _FakePipeline()
    mongo_logger = _FakeMongoLogger()
    request = _make_request(pipeline, mongo_logger)
    body = ChatRequest(
        question="môn mạng máy tính ở chương trình IT-E6 và IT-E7 có gì khác nhau",
        mode="agent",
        user_id="user-2",
        history=[
            {
                "role": "user",
                "content": "so sánh môn lập trình mạng của ngành IT-E6 và",
            },
            {
                "role": "assistant",
                "content": "Bạn muốn so sánh với ngành nào?",
            },
        ],
    )

    response = await chat(request, body)

    assert pipeline.query_calls == 0
    assert pipeline.query_v3_calls == 0
    assert pipeline.query_agent_calls == 1
    assert pipeline.agent.calls == 1
    assert pipeline.last_query_agent_route_label == "agent_forced"
    assert pipeline.last_query_agent_complexity_subtype is None
    assert response.answer == "Agent answer"
    assert response.intent == "agent_forced"
    assert response.model_name == "agent"
    assert pipeline.agent.last_history == [
        {"role": "user", "content": "so sánh môn lập trình mạng của ngành IT-E6 và"},
        {"role": "assistant", "content": "Bạn muốn so sánh với ngành nào?"},
    ]
    assert len(mongo_logger.logged_turns) == 1
    assert len(mongo_logger.logged_agent_traces) == 0
