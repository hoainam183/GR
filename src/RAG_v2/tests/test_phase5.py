"""Test Phase 5 — Settings, Schemas, Flows, and API app creation."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure RAG_v2 root is on path
RAG_V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAG_V2_ROOT))

PASSED = 0
FAILED = 0


def report(name: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    status = "PASS" if ok else "FAIL"
    if ok:
        PASSED += 1
    else:
        FAILED += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Config / Settings
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 5.3 Config / Settings ===")

try:
    from config.settings import Settings

    s = Settings()
    report("Settings import", True)
    report(
        "Settings.chat_model", s.chat_model == "gemini-2.5-flash", s.chat_model
    )
    report("Settings.api_port", s.api_port == 8000, str(s.api_port))
    report(
        "Settings.collections",
        isinstance(s.collections, list),
        str(s.collections),
    )
    report("Settings.cors_origins", isinstance(s.cors_origins, list))
    report("Settings.self_eval_enabled", isinstance(s.self_eval_enabled, bool))
except Exception as exc:
    report("Settings import", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. API Schemas
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 5.2 API Schemas ===")

try:
    from api.schemas import (
        ChatRequest,
        ChatResponse,
        HealthResponse,
        HistoryMessage,
        RetrievedDocument,
    )

    report("Schemas import", True)

    # ChatRequest validation
    req = ChatRequest(question="Xin chào")
    report("ChatRequest defaults", req.top_k == 5 and req.history is None)

    req_with_history = ChatRequest(
        question="Test?",
        top_k=3,
        history=[HistoryMessage(role="user", content="Hi")],
    )
    report("ChatRequest with history", len(req_with_history.history) == 1)

    # Validation: empty question should fail
    try:
        ChatRequest(question="")
        report("ChatRequest empty q rejects", False, "should have raised")
    except Exception:
        report("ChatRequest empty q rejects", True)

    # HealthResponse
    hr = HealthResponse(status="healthy", rag_initialized=True)
    report("HealthResponse", hr.status == "healthy")

    # ChatResponse
    cr = ChatResponse(
        question="Q",
        answer="A",
        retrieved_documents=[],
        num_documents=0,
        model_name="test",
        intent="chitchat",
        session_id="test-session",
    )
    report("ChatResponse", cr.answer == "A")

except Exception as exc:
    report("Schemas import", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Flows
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 5.1 Pipeline Flows ===")

try:
    from pipeline.flows import (
        chitchat_flow,
        chitchat_flow_stream,
        rag_flow,
        rag_flow_stream,
        _format_context,
        _trim_history,
    )

    report("Flows import", True)

    # Test _format_context
    docs = [
        {"text": "Content 1", "metadata": {"title": "Doc A"}},
        {"text": "Content 2", "metadata": {"source": "file.pdf"}},
    ]
    ctx = _format_context(docs)
    report("_format_context", "Doc A" in ctx and "Content 1" in ctx)

    # Test _trim_history
    history = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    trimmed = _trim_history(history, limit=3)
    report(
        "_trim_history", len(trimmed) == 3 and trimmed[0]["content"] == "msg7"
    )

    report("_trim_history(None)", _trim_history(None) == [])

    # Test chitchat_flow with a mock chat model
    class MockChatModel:
        model = "mock-model"

        def generate(self, query, history=None, mode="rag", context=None):
            return f"Mock answer for: {query}"

        def generate_stream(
            self, query, history=None, mode="rag", context=None
        ):
            yield "Mock "
            yield "stream"

    mock = MockChatModel()
    result = chitchat_flow(question="Hello!", history=None, chat_model=mock)
    report(
        "chitchat_flow",
        result["intent"] == "chitchat"
        and "Hello!" in result["answer"]
        and result["num_sources"] == 0,
    )

    # Test chitchat_flow_stream
    chunks = list(
        chitchat_flow_stream(question="Hi", history=None, chat_model=mock)
    )
    report("chitchat_flow_stream", chunks == ["Mock ", "stream"])

except Exception as exc:
    report("Flows import", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. API App creation (without loading heavy models)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 5.2 API App ===")

try:
    from api.main import create_app

    report("create_app import", True)

    test_app = create_app()
    report("FastAPI app created", test_app is not None)
    report("App title", test_app.title == "RAG v2 Chatbot API")

    # Check routes exist
    route_paths = [r.path for r in test_app.routes]
    report("/chat route", "/chat" in route_paths)
    report("/chat/stream route", "/chat/stream" in route_paths)
    report("/health route", "/health" in route_paths)
    report("/ route", "/" in route_paths)

except Exception as exc:
    report("API App", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Pipeline module (syntax + import chain — no model loading)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 5.1 Pipeline Orchestration ===")

try:
    import ast

    src = (RAG_V2_ROOT / "pipeline" / "rag_pipeline.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    report("rag_pipeline.py syntax", True)

    # Check key imports exist
    import_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                import_names.append(alias.name)

    report("imports SelfEvaluator", "SelfEvaluator" in import_names)
    report("imports QueryReflector", "QueryReflector" in import_names)
    report("imports TavilySearchTool", "TavilySearchTool" in import_names)
    report("imports chitchat_flow", "chitchat_flow" in import_names)
    report("imports rag_flow", "rag_flow" in import_names)

    # Check RAGPipeline class exists with query and query_stream
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    pipeline_cls = [c for c in classes if c.name == "RAGPipeline"]
    report("RAGPipeline class exists", len(pipeline_cls) == 1)
    if pipeline_cls:
        methods = [
            n.name
            for n in ast.walk(pipeline_cls[0])
            if isinstance(n, ast.FunctionDef)
        ]
        report("query() method", "query" in methods)
        report("query_stream() method", "query_stream" in methods)

except Exception as exc:
    report("Pipeline syntax check", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
total = PASSED + FAILED
print(f"Phase 5 Tests: {PASSED}/{total} passed, {FAILED} failed")
if FAILED == 0:
    print("All tests PASSED!")
else:
    print(f"WARNING: {FAILED} test(s) FAILED")
print(f"{'='*60}")
sys.exit(1 if FAILED else 0)
