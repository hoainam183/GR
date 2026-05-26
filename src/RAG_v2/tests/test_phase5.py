"""Test Phase 5 — Settings, Schemas, Flows, and API app creation.

Refactored from script-style to proper pytest module.
"""

from __future__ import annotations

import pytest


class TestSettings:
    def test_settings_import(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert s is not None

    def test_chat_model_default(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert s.chat_model == "gemini-3.1-flash-lite"

    def test_api_port_default(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert s.api_port == 8000

    def test_collections_is_list(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert isinstance(s.collections, list)

    def test_cors_origins_is_list(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert isinstance(s.cors_origins, list)

    def test_self_eval_enabled_is_bool(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert isinstance(s.self_eval_enabled, bool)


class TestAPISchemas:
    def test_schemas_import(self) -> None:
        from schemas.chat import ChatRequest, ChatResponse, HealthResponse, HistoryMessage, RetrievedDocument
        assert ChatRequest is not None

    def test_chat_request_defaults(self) -> None:
        from schemas.chat import ChatRequest
        req = ChatRequest(question="Xin chào")
        assert req.top_k == 5
        assert req.history is None

    def test_chat_request_with_history(self) -> None:
        from schemas.chat import ChatRequest, HistoryMessage
        req = ChatRequest(
            question="Test?",
            top_k=3,
            history=[HistoryMessage(role="user", content="Hi")],
        )
        assert len(req.history) == 1

    def test_chat_request_rejects_empty_question(self) -> None:
        from schemas.chat import ChatRequest
        with pytest.raises(Exception):
            ChatRequest(question="")

    def test_health_response(self) -> None:
        from schemas.chat import HealthResponse
        hr = HealthResponse(status="healthy", rag_initialized=True)
        assert hr.status == "healthy"

    def test_chat_response(self) -> None:
        from schemas.chat import ChatResponse
        cr = ChatResponse(
            question="Q",
            answer="A",
            retrieved_documents=[],
            num_documents=0,
            model_name="test",
            intent="chitchat",
            session_id="test-session",
        )
        assert cr.answer == "A"


class TestFlows:
    def test_flows_import(self) -> None:
        from pipeline.flows import (
            chitchat_flow,
            chitchat_flow_stream,
            rag_flow,
            rag_flow_stream,
            _format_context,
            _trim_history,
        )
        assert chitchat_flow is not None

    def test_format_context(self) -> None:
        from pipeline.flows import _format_context
        docs = [
            {"text": "Content 1", "metadata": {"title": "Doc A"}},
            {"text": "Content 2", "metadata": {"source": "file.pdf"}},
        ]
        ctx = _format_context(docs)
        assert "Doc A" in ctx
        assert "Content 1" in ctx

    def test_trim_history(self) -> None:
        from pipeline.flows import _trim_history
        history = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        trimmed = _trim_history(history, limit=3)
        assert len(trimmed) == 3
        assert trimmed[0]["content"] == "msg7"

    def test_trim_history_none(self) -> None:
        from pipeline.flows import _trim_history
        assert _trim_history(None) == []

    def test_chitchat_flow(self) -> None:
        from pipeline.flows import chitchat_flow

        class MockChatModel:
            model = "mock-model"

            def generate(self, query, history=None, mode="rag", context=None):
                return f"Mock answer for: {query}"

        mock = MockChatModel()
        result = chitchat_flow(question="Hello!", history=None, chat_model=mock)
        assert result["intent"] == "chitchat"
        assert "Hello!" in result["answer"]
        assert result["num_sources"] == 0

    def test_chitchat_flow_stream(self) -> None:
        from pipeline.flows import chitchat_flow_stream

        class MockChatModel:
            model = "mock-model"

            def generate_stream(self, query, history=None, mode="rag", context=None):
                yield "Mock "
                yield "stream"

        mock = MockChatModel()
        chunks = list(chitchat_flow_stream(question="Hi", history=None, chat_model=mock))
        assert chunks == ["Mock ", "stream"]


class TestAPIApp:
    def test_create_app_import(self) -> None:
        from api.main import create_app
        assert create_app is not None

    def test_create_app_returns_fastapi(self) -> None:
        from api.main import create_app
        app = create_app()
        assert app is not None
        assert app.title == "RAG v2 Chatbot API"

    def test_required_routes_exist(self) -> None:
        from api.main import create_app
        app = create_app()
        route_paths = [r.path for r in app.routes]
        assert "/chat" in route_paths
        assert "/chat/stream" in route_paths
        assert "/health" in route_paths


class TestPipelineSyntax:
    def test_rag_pipeline_parses(self) -> None:
        import ast
        from pathlib import Path
        src = (Path(__file__).parent.parent / "pipeline" / "rag_pipeline.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        assert tree is not None

    def test_pipeline_has_required_imports(self) -> None:
        import ast
        from pathlib import Path
        src = (Path(__file__).parent.parent / "pipeline" / "rag_pipeline.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        import_names = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        ]
        assert "SelfEvaluator" in import_names
        assert "QueryReflector" in import_names
        assert "chitchat_flow" in import_names
        assert "rag_flow" in import_names

    def test_pipeline_class_has_required_methods(self) -> None:
        import ast
        from pathlib import Path
        src = (Path(__file__).parent.parent / "pipeline" / "rag_pipeline.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        pipeline_cls = [c for c in classes if c.name == "RAGPipeline"]
        assert len(pipeline_cls) == 1
        methods = [n.name for n in ast.walk(pipeline_cls[0]) if isinstance(n, ast.FunctionDef)]
        assert "query" in methods
        assert "query_stream" in methods
