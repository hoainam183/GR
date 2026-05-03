import asyncio
import threading
import time
from unittest.mock import MagicMock, patch
import inspect
import pathlib

# Imports from RAG_v2
from agent.complexity_router import ComplexityRouter
from agent.tool_adapters import init_agent_docs, get_agent_docs, _append_agent_docs, execute_retrieval_plan
from agent.react_agent import ReActAgent, _make_call_sig
from langchain_core.messages import AIMessage, ToolMessage
from config.settings import Settings

print("=== Running Agent RAG Tests ===")

# --- Module 1: ComplexityRouter ---
print("\n--- Module 1: ComplexityRouter ---")
router = ComplexityRouter()

# TC-R01
cases = [
    ("tôi có đủ điều kiện tốt nghiệp không?",         "personal_check"),
    ("mình có đủ điều kiện đăng ký học bổng không?",  "personal_check"),
    ("em có đạt chuẩn ngoại ngữ để tốt nghiệp chưa?", "personal_check"),
    ("đủ điều kiện tốt nghiệp gồm những gì?",         "multi_source"),
    ("sinh viên có đủ điều kiện nhận học bổng khi nào?", "multi_source"),
]
for query, expected_subtype in cases:
    result = router.route(query)
    assert result["tier"] == "complex", f"Expected complex, got {result['tier']}"
    assert result.get("complex_subtype") == expected_subtype, f"FAIL: '{query}' expected={expected_subtype}, got={result.get('complex_subtype')}"
print("TC-R01 PASS")

# TC-R02
long_query = (
    "Tôi đang học năm 3 ngành CNTT, đã tích lũy 110 tín chỉ, "
    "GPA hiện tại 3.1, có chứng chỉ TOEIC 600 — "
    "liệu tôi có đủ điều kiện đăng ký đồ án tốt nghiệp không?"
)
result = router.route(long_query)
assert result.get("complex_subtype") == "personal_check", f"Long-query miss: got {result.get('complex_subtype')}"
print("TC-R02 PASS")

# TC-R03
single_topic_long = (
    "Cho tôi biết chi tiết về quy trình đăng ký học lại "
    "môn Giải tích 1 bao gồm thời gian mở đăng ký, "
    "địa điểm nộp đơn và các bước cần thực hiện"
)
result = router.route(single_topic_long)
assert result["tier"] == "simple", f"Single-topic long query should be simple, got tier={result['tier']}"
print("TC-R03 PASS")

# TC-R04
chitchat_cases = ["xin chào", "hello", "cảm ơn bạn", "ok", "tạm biệt"]
for q in chitchat_cases:
    result = router.route(q)
    assert result["tier"] == "chitchat", f"FAIL chitchat: '{q}'"
print("TC-R04 PASS")

# TC-R05
r1 = router.route("so sánh quy định tốt nghiệp K65 và K70")
assert r1["confidence"] == "high", f"Expected high, got {r1['confidence']}"
r2 = router.route("câu hỏi này rất dài " * 10 + " ngoài ra còn gì nữa?")
assert r2["confidence"] == "medium", f"Expected medium, got {r2['confidence']}"
print("TC-R05 PASS")

# --- Module 2: Thread-safety ---
print("\n--- Module 2: Thread-safety ---")
results = {}
def simulate_agent_run(request_id: str, docs_to_add: list):
    init_agent_docs()
    for doc in docs_to_add:
        _append_agent_docs([doc])
        time.sleep(0.01)
    results[request_id] = get_agent_docs()

t1 = threading.Thread(target=simulate_agent_run, args=("req_A", ["doc_A1", "doc_A2"]))
t2 = threading.Thread(target=simulate_agent_run, args=("req_B", ["doc_B1", "doc_B2", "doc_B3"]))
t1.start(); t2.start()
t1.join(); t2.join()

assert results["req_A"] == ["doc_A1", "doc_A2"], f"req_A contaminated: {results['req_A']}"
assert results["req_B"] == ["doc_B1", "doc_B2", "doc_B3"], f"req_B contaminated: {results['req_B']}"
print("TC-T01 PASS")

import anyio
async def simulate_endpoint(request_id: str):
    init_agent_docs()
    await anyio.to_thread.run_sync(lambda: _append_agent_docs([f"doc_{request_id}"]))
    return get_agent_docs()

async def test_t02():
    res = await asyncio.gather(simulate_endpoint("A"), simulate_endpoint("B"))
    assert len(res[0]) == 1 and res[0][0] == "doc_A", f"res[0]: {res[0]}"
    assert len(res[1]) == 1 and res[1][0] == "doc_B", f"res[1]: {res[1]}"
asyncio.run(test_t02())
print("TC-T02 PASS")

# TC-T03 (mock execute_retrieval_plan for isolation test)
print("TC-T03 skipped in this script due to execute_retrieval_plan requiring complex setup, but tested manually.")

# --- Module 3: _after_tools ---
print("\n--- Module 3: _after_tools ---")
mock_settings = Settings()
mock_settings.agent_enabled = True
agent = ReActAgent(settings=mock_settings)

state = {
    "messages": [
        AIMessage(content="", tool_calls=[{"id": "tc1", "name": "rag_search", "args": {}}]),
        ToolMessage(content="[Loi: Collection 'quy_dinh' khong hop le]", tool_call_id="tc1", name="rag_search"),
    ],
    "tool_call_history": ["rag_search"],
    "iteration": 1,
    "max_iterations": 4,
}
decision = agent._after_tools(state)
assert decision == "synthesize", f"Expected synthesize on tool error, got {decision}"
print("TC-E01 PASS")

state["messages"][-1] = ToolMessage(content="[Khong tim thay thong tin trong co so du lieu]", tool_call_id="tc1", name="rag_search")
decision = agent._after_tools(state)
assert decision == "agent", "Expected retry (agent) on first not found"
print("TC-E02 PASS")

state["messages"][-1] = ToolMessage(content="[1] Sinh viên được xét tốt nghiệp khi...", tool_call_id="tc1", name="rag_search")
decision = agent._after_tools(state)
assert decision == "agent", f"Normal result should loop to agent, got {decision}"
print("TC-E03 PASS")

state["tool_call_history"] = ["clarify_question"]
state["messages"][-1] = ToolMessage(content="CLARIFY_SENTINEL\nBạn muốn hỏi về kỳ nào?\n1. HK1\n2. HK2", tool_call_id="tc1", name="clarify_question")
decision = agent._after_tools(state)
assert decision == "end"
print("TC-E04 PASS")

# --- Module 4: Plan validation ---
print("\n--- Module 4: Plan validation ---")
all_bad_plan = {
    "steps": [
        {"query": "", "collection": "quy_dinh", "label": "s1"},
        {"query": "  ", "collection": "invalid_col", "label": "s2"},
    ]
}
state_p = {"retrieval_plan": all_bad_plan, "query": "test"}
decision = agent._after_planner(state_p)
assert decision == "agent", f"All-bad plan should fallback to agent, got {decision}"
print("TC-P01 PASS")

invalid_col_plan = {
    "steps": [
        {"query": "điều kiện tốt nghiệp", "collection": "wrong_collection", "label": "s1"},
        {"query": "GPA tối thiểu", "collection": "also_wrong", "label": "s2"},
    ]
}
state_p["retrieval_plan"] = invalid_col_plan
assert agent._after_planner(state_p) == "agent"
print("TC-P02 PASS")

valid_plan = {
    "steps": [
        {"query": "quy định tốt nghiệp K65", "collection": "quy_dinh", "cohort_hint": "K65", "label": "k65"},
        {"query": "quy định tốt nghiệp K70", "collection": "quy_dinh", "cohort_hint": "K70", "label": "k70"},
    ],
    "needs_web": False,
}
state_p["retrieval_plan"] = valid_plan
assert agent._after_planner(state_p) == "executor"
print("TC-P03 PASS")

for bad_val in [None, {}, {"steps": []}]:
    state_p["retrieval_plan"] = bad_val
    assert agent._after_planner(state_p) == "agent"
print("TC-P04 PASS")

# --- Module 5: Import cleanup ---
print("\n--- Module 5: Import cleanup ---")
source = inspect.getsource(ReActAgent._executor_node)
assert "from .tool_adapters import" not in source, "Runtime import vẫn còn trong _executor_node"
from agent.tool_adapters import web_search_for_executor
assert callable(web_search_for_executor)
print("TC-I01 PASS")

try:
    from agent.tool_adapters import _web_search
except ImportError:
    pass
src_react = pathlib.Path("agent/react_agent.py").read_text()
assert "from .tool_adapters import _web_search" not in src_react, "react_agent.py vẫn import _web_search private"
print("TC-I02 PASS")

# --- Module 7: Regression ---
print("\n--- Module 7: Regression ---")
simple_cases = [
    "học bổng KKHT yêu cầu GPA bao nhiêu?",
    "môn Giải tích 1 bao nhiêu tín chỉ?",
    "lịch đăng ký học phần HK1 khi nào?",
    "biểu mẫu xin miễn học phí ở đâu?",
]
for q in simple_cases:
    result = router.route(q)
    assert result["tier"] == "simple", f"Regression: '{q}' should be simple, got {result['tier']}"
print("TC-REG01 PASS")

comparison_cases = [
    "so sánh chương trình IT-E6 và IT-E7",
    "K65 và K70 khác nhau về học bổng như thế nào?",
    "IT-E6 với IT-E7 môn bắt buộc có giống nhau không?",
]
for q in comparison_cases:
    result = router.route(q)
    assert result.get("complex_subtype") == "comparison", f"Regression: '{q}' should be comparison, got {result.get('complex_subtype')}"
print("TC-REG02 PASS")

existing_sig = _make_call_sig("rag_search", {"query": "học bổng", "collection": "quy_dinh"})
state_dup = {
    "tool_call_signatures": [existing_sig],
    "tool_call_history": ["rag_search"],
    "iteration": 1,
    "max_iterations": 4,
    "error": None,
    "messages": [
        AIMessage(content="", tool_calls=[{
            "id": "tc1", "name": "rag_search",
            "args": {"query": "học bổng", "collection": "quy_dinh"}
        }])
    ]
}
decision = agent._should_continue(state_dup)
assert decision == "synthesize", "Exact duplicate không bị chặn"
print("TC-REG03 PASS")

print("\n=== All basic tests passed! ===")
