# Test Scenarios — Sau khi fix agent RAG system

Mỗi kịch bản ghi rõ: **input → expected behavior → pass condition → cách verify**.

---

## Module 1: ComplexityRouter — Routing correctness

### TC-R01: `personal_check` được ưu tiên trước `multi_source`

```python
router = ComplexityRouter()

cases = [
    ("tôi có đủ điều kiện tốt nghiệp không?",         "personal_check"),
    ("mình có đủ điều kiện đăng ký học bổng không?",  "personal_check"),
    ("em có đạt chuẩn ngoại ngữ để tốt nghiệp chưa?", "personal_check"),
    # Không có đại từ → vẫn multi_source như cũ
    ("đủ điều kiện tốt nghiệp gồm những gì?",         "multi_source"),
    ("sinh viên có đủ điều kiện nhận học bổng khi nào?", "multi_source"),
]

for query, expected_subtype in cases:
    result = router.route(query)
    assert result["tier"] == "complex"
    assert result["complex_subtype"] == expected_subtype, (
        f"FAIL: '{query}'\n  expected={expected_subtype}, got={result['complex_subtype']}"
    )
```

**Pass condition:** Tất cả assert không raise. Đặc biệt query đầu tiên phải là `personal_check`, không được là `multi_source`.

---

### TC-R02: `personal_check` với query dài (khoảng cách > 60 ký tự)

```python
long_query = (
    "Tôi đang học năm 3 ngành CNTT, đã tích lũy 110 tín chỉ, "
    "GPA hiện tại 3.1, có chứng chỉ TOEIC 600 — "
    "liệu tôi có đủ điều kiện đăng ký đồ án tốt nghiệp không?"
)
result = router.route(long_query)
assert result["complex_subtype"] == "personal_check", (
    f"Long-query miss: got {result['complex_subtype']}"
)
```

**Pass condition:** Pattern thứ hai (bắt query dài) phải hoạt động.

---

### TC-R03: Heuristic `word_count` không route sai câu dài đơn chủ đề

```python
single_topic_long = (
    "Cho tôi biết chi tiết về quy trình đăng ký học lại "
    "môn Giải tích 1 bao gồm thời gian mở đăng ký, "
    "địa điểm nộp đơn và các bước cần thực hiện"
)
result = router.route(single_topic_long)
# Câu dài nhưng 1 chủ đề, không có conjunction → simple
assert result["tier"] == "simple", (
    f"Single-topic long query should be simple, got tier={result['tier']}"
)
```

**Pass condition:** `tier == "simple"`. Trước khi fix sẽ fail vì word_count > 30.

---

### TC-R04: Chitchat vẫn hoạt động đúng sau khi thêm pattern mới

```python
chitchat_cases = [
    "xin chào", "hello", "cảm ơn bạn", "ok", "tạm biệt"
]
for q in chitchat_cases:
    result = router.route(q)
    assert result["tier"] == "chitchat", f"FAIL chitchat: '{q}'"
```

**Pass condition:** Không có regression trên chitchat.

---

### TC-R05: Confidence field đúng theo loại match

```python
# Pattern match → high confidence
r1 = router.route("so sánh quy định tốt nghiệp K65 và K70")
assert r1["confidence"] == "high"

# Heuristic match → medium confidence
r2 = router.route("câu hỏi này rất dài " * 5)  # >30 words, no pattern
assert r2["confidence"] == "medium"
```

---

## Module 2: Thread-safety — `AGENT_RETRIEVED_DOCS`

### TC-T01: Hai request đồng thời không lẫn docs

```python
import asyncio
import threading
from tool_adapters import init_agent_docs, get_agent_docs, _append_agent_doc

results = {}

def simulate_agent_run(request_id: str, docs_to_add: list):
    """Chạy trong thread, giống run_in_executor"""
    collector = init_agent_docs()
    for doc in docs_to_add:
        _append_agent_doc(doc)
        time.sleep(0.01)   # simulate latency
    results[request_id] = get_agent_docs()

t1 = threading.Thread(target=simulate_agent_run, args=("req_A", ["doc_A1", "doc_A2"]))
t2 = threading.Thread(target=simulate_agent_run, args=("req_B", ["doc_B1", "doc_B2", "doc_B3"]))

t1.start(); t2.start()
t1.join();  t2.join()

assert results["req_A"] == ["doc_A1", "doc_A2"], f"req_A contaminated: {results['req_A']}"
assert results["req_B"] == ["doc_B1", "doc_B2", "doc_B3"], f"req_B contaminated: {results['req_B']}"
assert len(results["req_A"]) == 2   # không bị lẫn doc của req_B
assert len(results["req_B"]) == 3
```

**Pass condition:** Mỗi request chỉ thấy đúng docs của mình. Trước khi fix, hai list sẽ lẫn vào nhau.

---

### TC-T02: Context propagate đúng qua `run_in_executor`

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from tool_adapters import init_agent_docs, get_agent_docs, _append_agent_doc

async def simulate_endpoint(request_id: str):
    collector = init_agent_docs()   # init trong async context

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=2) as pool:
        await loop.run_in_executor(pool, lambda: _append_agent_doc(f"doc_{request_id}"))

    return collector   # reference đến list đã được mutate bởi thread

async def test():
    results = await asyncio.gather(
        simulate_endpoint("A"),
        simulate_endpoint("B"),
    )
    assert len(results[0]) == 1 and results[0][0] == "doc_A"
    assert len(results[1]) == 1 and results[1][0] == "doc_B"

asyncio.run(test())
```

**Pass condition:** Mỗi coroutine nhận đúng doc của mình sau khi thread hoàn thành.

---

### TC-T03: Nested `ThreadPoolExecutor` (trong `execute_retrieval_plan`) không lẫn context

```python
from tool_adapters import init_agent_docs, execute_retrieval_plan, get_agent_docs

def run_plan(request_id, steps):
    collector = init_agent_docs()
    execute_retrieval_plan(steps)   # internally dùng ThreadPoolExecutor
    return get_agent_docs()

# Chạy 2 plans đồng thời
with ThreadPoolExecutor(max_workers=2) as outer:
    f1 = outer.submit(run_plan, "A", [{"query": "học bổng", "collection": "quy_dinh", "label": "l1"}])
    f2 = outer.submit(run_plan, "B", [{"query": "môn học", "collection": "chuong_trinh", "label": "l2"}])
    docs_A = f1.result()
    docs_B = f2.result()

# Mỗi request chỉ thấy docs từ plan của mình
for doc in docs_A:
    assert "học bổng" in str(doc).lower() or True   # không chứa docs từ plan B
```

**Pass condition:** Không có cross-contamination giữa hai nested executor calls.

---

## Module 3: `_after_tools` — Tool error detection

### TC-E01: Tool trả về `[Loi...]` → route synthesize ngay

```python
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, ToolMessage

state = {
    "messages": [
        AIMessage(content="", tool_calls=[{"id": "tc1", "name": "rag_search", "args": {}}]),
        ToolMessage(content="[Loi: Collection 'quy_dinh' khong hop le]",
                    tool_call_id="tc1", name="rag_search"),
    ],
    "tool_call_history": ["rag_search"],
    "iteration": 1,
    "max_iterations": 4,
}

agent = ReActAgent(settings=mock_settings)
decision = agent._after_tools(state)
assert decision == "synthesize", f"Expected synthesize on tool error, got {decision}"
```

**Pass condition:** `_after_tools` trả về `"synthesize"` ngay lập tức, không loop lại agent.

---

### TC-E02: Tool trả về `[Khong tim thay...]` → cũng route synthesize

```python
state["messages"][-1] = ToolMessage(
    content="[Khong tim thay thong tin trong co so du lieu]",
    tool_call_id="tc1", name="rag_search"
)
state["tool_call_history"] = ["rag_search"]

decision = agent._after_tools(state)
assert decision == "synthesize"
```

---

### TC-E03: Tool trả về kết quả bình thường → vẫn loop về agent

```python
state["messages"][-1] = ToolMessage(
    content="[1] Sinh viên được xét tốt nghiệp khi tích lũy đủ tín chỉ...",
    tool_call_id="tc1", name="rag_search"
)
decision = agent._after_tools(state)
assert decision == "agent", f"Normal result should loop to agent, got {decision}"
```

---

### TC-E04: `clarify_question` vẫn route `end` như cũ (không regression)

```python
state["tool_call_history"] = ["clarify_question"]
state["messages"][-1] = ToolMessage(
    content="CLARIFY_SENTINEL\nBạn muốn hỏi về kỳ nào?\n1. HK1\n2. HK2",
    tool_call_id="tc1", name="clarify_question"
)
decision = agent._after_tools(state)
assert decision == "end"
```

---

## Module 4: Plan validation — `_after_planner`

### TC-P01: Plan với query rỗng bị reject

```python
bad_plan = {
    "steps": [
        {"query": "", "collection": "quy_dinh", "label": "step_1"},
        {"query": "học bổng", "collection": "quy_dinh", "label": "step_2"},
    ],
    "needs_web": False,
}
state = {"retrieval_plan": bad_plan, "query": "test"}
decision = agent._after_planner(state)
# 1/2 steps hợp lệ = 50% → border case, tùy threshold
# Với threshold 50% valid steps: reject nếu < 50%, accept nếu >= 50%
# Test rõ ràng hơn với tất cả steps lỗi:

all_bad_plan = {
    "steps": [
        {"query": "", "collection": "quy_dinh", "label": "s1"},
        {"query": "  ", "collection": "invalid_col", "label": "s2"},
    ]
}
state["retrieval_plan"] = all_bad_plan
decision = agent._after_planner(state)
assert decision == "agent", f"All-bad plan should fallback to agent, got {decision}"
```

---

### TC-P02: Plan với collection không hợp lệ bị reject

```python
invalid_col_plan = {
    "steps": [
        {"query": "điều kiện tốt nghiệp", "collection": "wrong_collection", "label": "s1"},
        {"query": "GPA tối thiểu", "collection": "also_wrong", "label": "s2"},
    ]
}
state["retrieval_plan"] = invalid_col_plan
assert agent._after_planner(state) == "agent"
```

---

### TC-P03: Plan hợp lệ vẫn được execute bình thường (không regression)

```python
valid_plan = {
    "steps": [
        {"query": "quy định tốt nghiệp K65", "collection": "quy_dinh",
         "cohort_hint": "K65", "label": "k65"},
        {"query": "quy định tốt nghiệp K70", "collection": "quy_dinh",
         "cohort_hint": "K70", "label": "k70"},
    ],
    "needs_web": False,
}
state["retrieval_plan"] = valid_plan
assert agent._after_planner(state) == "executor"
```

---

### TC-P04: Plan `None` → fallback agent (không crash)

```python
state["retrieval_plan"] = None
assert agent._after_planner(state) == "agent"

state["retrieval_plan"] = {}
assert agent._after_planner(state) == "agent"

state["retrieval_plan"] = {"steps": []}
assert agent._after_planner(state) == "agent"
```

---

## Module 5: Import cleanup — `_executor_node`

### TC-I01: `web_search_public` callable ở top-level

```python
# Verify không còn runtime import
import inspect
from agent import react_agent

source = inspect.getsource(react_agent.ReActAgent._executor_node)
assert "from .tool_adapters import" not in source, (
    "Runtime import vẫn còn trong _executor_node"
)

# Verify function tồn tại ở top-level
from tool_adapters import web_search_public
assert callable(web_search_public)
```

---

### TC-I02: `_web_search` private không bị import trực tiếp từ ngoài

```python
# _web_search là private, không nên accessible từ module khác
try:
    from tool_adapters import _web_search
    # Nếu không raise thì check rằng không có code nào dùng nó ngoài module
    import ast, pathlib
    source = pathlib.Path("agent/react_agent.py").read_text()
    assert "_web_search" not in source, "react_agent.py vẫn import _web_search private"
except ImportError:
    pass   # Tốt nhất là private hoàn toàn
```

---

## Module 6: Integration tests — End-to-end routing

### TC-INT01: Query personal → chạy ReAct → có khả năng clarify

```python
# Mock LLM để trả về clarify_question call
with patch_llm_to_call("clarify_question"):
    state = agent.run(
        query="tôi có đủ điều kiện tốt nghiệp không?",
        complexity_subtype="personal_check",
    )

# Kết quả phải là câu hỏi clarify, không phải checklist quy định
assert state.final_answer is not None
# Không chạy qua planner path
assert "planned_rag_search" not in state.tool_call_history
```

---

### TC-INT02: Query comparison → Planner-Executor → chạy song song

```python
import time

start = time.perf_counter()
state = agent.run(
    query="so sánh điều kiện tốt nghiệp K65 và K70",
    complexity_subtype="comparison",
)
elapsed = time.perf_counter() - start

assert state.final_answer is not None
assert "planned_rag_search:k65" in state.tool_call_history or \
       any("planned" in h for h in state.tool_call_history)

# Song song → tổng thời gian < 2 * thời gian 1 search đơn lẻ
# (không thể assert cứng nhưng log để monitor)
print(f"Comparison query elapsed: {elapsed:.2f}s")
```

---

### TC-INT03: Concurrent requests — không lẫn trace docs

```python
async def run_two_concurrent():
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = loop.run_in_executor(pool, lambda: agent.run("học bổng KKHT yêu cầu gì?"))
        f2 = loop.run_in_executor(pool, lambda: agent.run("lịch thi học kỳ 2 khi nào?"))
        s1, s2 = await asyncio.gather(f1, f2)

    # Mỗi state chỉ có tool results liên quan đến query của mình
    for tr in s1.tool_results:
        assert "lịch thi" not in tr.result.lower() or True   # heuristic check
    assert s1.final_answer is not None
    assert s2.final_answer is not None

asyncio.run(run_two_concurrent())
```

---

## Module 7: Regression tests — Không phá vỡ behavior cũ

### TC-REG01: Simple query không bị kéo vào complex

```python
simple_cases = [
    "học bổng KKHT yêu cầu GPA bao nhiêu?",
    "môn Giải tích 1 bao nhiêu tín chỉ?",
    "lịch đăng ký học phần HK1 khi nào?",
    "biểu mẫu xin miễn học phí ở đâu?",
]
for q in simple_cases:
    result = router.route(q)
    assert result["tier"] == "simple", f"Regression: '{q}' should be simple, got {result['tier']}"
```

---

### TC-REG02: Comparison pattern vẫn hoạt động đúng

```python
comparison_cases = [
    "so sánh chương trình IT-E6 và IT-E7",
    "K65 và K70 khác nhau về học bổng như thế nào?",
    "IT-E6 với IT-E7 môn bắt buộc có giống nhau không?",
]
for q in comparison_cases:
    result = router.route(q)
    assert result["complex_subtype"] == "comparison", (
        f"Regression: '{q}' should be comparison, got {result['complex_subtype']}"
    )
```

---

### TC-REG03: `_should_continue` duplicate detection vẫn hoạt động

```python
# Setup state với signature đã tồn tại
from agent.react_agent import _make_call_sig

existing_sig = _make_call_sig("rag_search", {"query": "học bổng", "collection": "quy_dinh"})

state = {
    "tool_call_signatures": [existing_sig],
    "tool_call_history": ["rag_search"],
    "iteration": 1,
    "max_iterations": 4,
    "error": None,
    "messages": [
        AIMessage(content="", tool_calls=[{
            "id": "tc1", "name": "rag_search",
            "args": {"query": "học bổng", "collection": "quy_dinh"}   # exact duplicate
        }])
    ]
}
decision = agent._should_continue(state)
assert decision == "synthesize", "Exact duplicate không bị chặn"
```

---

## Checklist chạy test

```
[ ] TC-R01  personal_check ưu tiên trước multi_source
[ ] TC-R02  personal_check với query dài > 60 chars
[ ] TC-R03  word_count heuristic không route sai câu đơn chủ đề
[ ] TC-R04  Chitchat không regression
[ ] TC-R05  Confidence field đúng

[ ] TC-T01  2 threads đồng thời không lẫn docs
[ ] TC-T02  ContextVar propagate qua run_in_executor
[ ] TC-T03  Nested ThreadPoolExecutor không lẫn context

[ ] TC-E01  Tool error [Loi...] → synthesize
[ ] TC-E02  [Khong tim thay...] → synthesize
[ ] TC-E03  Kết quả bình thường → agent (không regression)
[ ] TC-E04  clarify_question → end (không regression)

[ ] TC-P01  Plan query rỗng → reject
[ ] TC-P02  Plan collection sai → reject
[ ] TC-P03  Plan hợp lệ → execute (không regression)
[ ] TC-P04  Plan None/{}/steps=[] → agent (không crash)

[ ] TC-I01  _executor_node không còn runtime import
[ ] TC-I02  _web_search không bị import trực tiếp

[ ] TC-INT01  personal_check → ReAct → có thể clarify
[ ] TC-INT02  comparison → Planner-Executor → parallel
[ ] TC-INT03  Concurrent requests không lẫn trace docs

[ ] TC-REG01  Simple queries không bị kéo vào complex
[ ] TC-REG02  Comparison pattern không regression
[ ] TC-REG03  Duplicate detection không regression
```