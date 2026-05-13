import re
from agent.tool_adapters import strip_personal_identifiers
from agent.react_agent import ReActAgent
from langchain_core.messages import AIMessage, ToolMessage

print("=== Running Custom Tests ===")
# TC-STRIP01, TC-STRIP02, TC-STRIP03
cases = [
    ("Mã SV 20225653 có được học bổng không?", "có được học bổng không?"),
    ("mssv: 20221234 em bị điểm F", "em bị điểm F"),
    ("Sinh viên mã 20220000 cần chuẩn bị gì?", "cần chuẩn bị gì?"),
    ("Cho em hỏi mã 20221111 ạ", "Cho em hỏi mã ạ"),
    ("điều kiện IT-E6", "điều kiện IT-E6"),
]
for q, expected in cases:
    res = strip_personal_identifiers(q)
    assert res == expected, f"Failed: '{q}' -> '{res}' (expected '{expected}')"
print("TC-STRIP PASS")

# Retry logic test
from config.settings import Settings
mock_settings = Settings()
mock_settings.agent_enabled = True
agent = ReActAgent(settings=mock_settings)
state = {
    "messages": [
        ToolMessage(content="[Khong tim thay thong tin]", tool_call_id="tc1", name="rag_search")
    ],
    "iteration": 1,
    "max_iterations": 4,
    "empty_result_count": 0,
    "tool_call_history": ["rag_search"],
}

# Test 1st fail
decision = agent._after_tools(state)
assert decision == "agent"

# Run agent_node with mocked LLM to see if empty_result_count is incremented and hint added
class MockLLM:
    def invoke(self, messages):
        return AIMessage(content="retry_result", tool_calls=[])

agent._llm_with_tools = MockLLM()
res = agent._agent_node(state)
assert res["empty_result_count"] == 1
assert len(state["messages"]) == 1 # Original state is intact, only response is returned
print("Retry Logic 1st try PASS")

# Test 2nd fail
state["empty_result_count"] = 1
res = agent._agent_node(state)
assert "error" in res, f"Expected error on 2nd fail, got: {res}"
assert res["error"] == "Không tìm thấy thông tin phù hợp."
print("Retry Logic 2nd try (abort) PASS")

print("All custom tests passed!")
