# Refactoring Plan — Agent Module
> Mục tiêu: Loại bỏ business logic khỏi tools, kiểm soát context budget, cải thiện latency

---

## 1. Chẩn đoán vấn đề hiện tại

### 1.1 Tool đang làm quá nhiều việc

| Tool | Vấn đề |
|---|---|
| `compare_cohorts` | Encode business logic (validate mã khóa, format output, parallel search) — thêm loại so sánh mới = thêm tool |
| `compare_programs` | Tương tự — thêm `course_keyword` vào schema làm tool description phình to |
| `multi_rag_search` | Overlap với `rag_search` — agent hay bị nhầm khi nào dùng cái nào |
| `clarify_question` | Interaction logic không nên là tool — agent quyết định clarify hay không là không ổn định với Qwen 8B |

**Hệ quả:** Mỗi câu hỏi complex mới → cân nhắc thêm tool → tool descriptions ngày càng dài → context của Qwen 8B bị ăn mòn trước khi query được gửi đi.

### 1.2 Context budget bị tiêu thụ sai chỗ

```
Qwen 8B context budget: ~3200 tokens (agent_context_token_budget)

Phân bổ hiện tại (ước tính):
  AGENT_SYSTEM_PROMPT         ~400 tokens    ✓ hợp lý
  Tool descriptions (6 tools) ~350 tokens    ← có thể cắt
  Conversation history (4 turns) ~300 tokens ✓
  Tool results (3 results × 500 chars) ~500 tokens
  ─────────────────────────────────────────
  Tổng trước khi query        ~1550 tokens
  Còn lại cho reasoning       ~1650 tokens   ← mỏng với ReAct loop
```

### 1.3 Agent loop là bottleneck latency

```
Theo MODULE.md — agent path worst case:
  Iteration 1: agent_node (Qwen) = 2000-30000ms
  tools_node                     = 100-500ms
  Iteration 2: agent_node (Qwen) = 2000-30000ms
  ─────────────────────────────────────────────
  Total:                         60-120s ⚠️
```

Nguyên nhân: Qwen 8B chạy local phải reason về tool selection 2-4 lần tuần tự. Với so sánh khóa/ngành, agent luôn cần đúng 2 iterations → latency gấp đôi không cần thiết.

---

## 2. Kiến trúc đề xuất: Planner-Executor

Thay vì agent loop tự do, tách thành 3 tầng cố định:

```
Query (complex)
    │
    ▼
[pre_clarify node]          ← Rule-based, 0ms, không LLM
    │ rõ ràng
    ▼
[planner node]              ← Gemini: sinh retrieval plan (1 LLM call)
    │ {steps: [...]}
    ▼
[executor node]             ← Python thuần, parallel, không LLM
    │ [doc1, doc2, ...]
    ▼
[synthesize node]           ← Gemini: tổng hợp câu trả lời (1 LLM call)
    │
    ▼
Answer
```

**Kết quả:** 2 LLM calls cố định thay vì 2-4 calls tuần tự. Qwen 8B không còn cần đưa ra quyết định phức tạp.

---

## 3. Thay đổi cụ thể theo file

### 3.1 `graph_state.py` — Thêm fields mới

**Thêm vào `AgentGraphState`:**

```python
# Clarification control
clarification_done: bool        # đã hỏi user → không hỏi lại
skip_clarify: bool              # query rõ → bypass pre_clarify

# Planner output
retrieval_plan: dict | None     # {steps: [...], needs_web: bool, reasoning: str}
```

**Không xóa** các fields cũ — giữ backward compatibility cho agent loop path.

---

### 3.2 `lc_tools.py` — Thu gọn từ 6 xuống 3 tools

**Tools bị xóa:**

| Tool bị xóa | Lý do | Thay thế bằng |
|---|---|---|
| `compare_cohorts` | Business logic trong tool | Planner sinh 2 retrieval steps |
| `compare_programs` | Business logic trong tool | Planner sinh 2 retrieval steps |
| `multi_rag_search` | Overlap với `rag_search`, agent hay nhầm | Executor chạy parallel |

**Tools giữ lại:**

```python
LANGGRAPH_TOOLS = [
    rag_search,      # primitive duy nhất để lấy data
    web_search,      # fallback Tavily
    clarify_question # giữ lại nhưng CHỈ dùng trong agent loop path
]
```

**Tác động lên context:**

```
Tool descriptions trước: 6 tools × ~60 tokens = ~360 tokens
Tool descriptions sau:   3 tools × ~50 tokens = ~150 tokens
Tiết kiệm: ~210 tokens  → dành cho tool results
```

**Giữ nguyên** `TOOL_MAP` — executor dùng `_rag_search` trực tiếp từ `tool_adapters.py`, không qua `TOOL_MAP`.

---

### 3.3 `tool_adapters.py` — Giữ nguyên implementations, thêm executor helper

**Không xóa** `_compare_cohorts`, `_compare_programs` — vẫn có thể gọi trực tiếp từ executor nếu cần trong tương lai.

**Thêm `execute_parallel_plan()`:**

```python
def execute_parallel_plan(steps: list[dict]) -> list[tuple[str, str]]:
    """
    Chạy danh sách retrieval steps song song.
    Trả về [(collection_label, result_str), ...] theo thứ tự steps.

    Không có LLM. Thread-safe vì _rag_search đã có cache + lock.
    """
    results = [None] * len(steps)

    def _run(i: int, step: dict) -> None:
        result = _rag_search(
            query=step["query"],
            collection=step["collection"],
            resolved_cohort=step.get("filter_hint"),
            resolved_major=step.get("filter_hint"),
        )
        results[i] = (step.get("label", step["collection"]), result)

    with ThreadPoolExecutor(max_workers=min(4, len(steps))) as pool:
        futures = [pool.submit(_run, i, step) for i, step in enumerate(steps)]
        for f in futures:
            f.result(timeout=45)

    return [r for r in results if r is not None]
```

---

### 3.4 `react_agent.py` — Refactor graph topology

#### 3.4.1 Routing strategy: 2 paths song song

```
                    START
                      │
                      ▼
               [pre_clarify]  ← rule-based
               /            \
         clarify           tiếp tục
              │                │
    [extract_answer]     [complexity check]
              │            /          \
             END     simple query   complex query
                          │                │
                    [agent loop]    [planner]
                          │                │
                         END        [executor]
                                          │
                                   [synthesize]
                                          │
                                         END
```

**Routing logic tại `complexity check`:**

```python
def _after_pre_clarify(state) -> str:
    if state.get("clarification_done"):
        return "extract_answer"

    # Query đã rõ → chọn path
    query = state["query"]
    if _needs_planner(query):   # có so sánh, multi-collection rõ ràng
        return "planner"
    return "agent"              # agent loop cho query cần web search / unknown pattern
```

**`_needs_planner()` — rule-based, không dùng LLM:**

```python
_PLANNER_TRIGGERS = re.compile(
    r"\b(so sánh|khác nhau|giống nhau)\b"
    r"|\bK\d{2,3}\b.{1,120}\bK\d{2,3}\b"
    r"|\b(?:IT|MI|ET|EM)-[A-Z0-9]+\b.{1,50}\b(?:IT|MI|ET|EM)-[A-Z0-9]+\b"
    r"|\bđủ điều kiện\b"
    r"|\btất cả.{0,20}(điều kiện|quy định)\b",
    re.IGNORECASE,
)

def _needs_planner(query: str) -> bool:
    return bool(_PLANNER_TRIGGERS.search(query))
```

#### 3.4.2 Planner node — Gemini sinh retrieval plan

```python
class RetrievalStep(BaseModel):
    query: str                  # query cụ thể để embed + search
    collection: str             # quy_dinh | chuong_trinh | ke_hoach | ho_tro_sv
    filter_hint: str | None     # "K65", "IT-E6" — truyền vào reranker
    label: str                  # label cho output: "IT-E6", "K65", ...

class RetrievalPlan(BaseModel):
    steps: list[RetrievalStep]  # tối đa 4 steps
    needs_web: bool
    reasoning: str              # debug only

def _planner_node(self, state: AgentGraphState) -> dict:
    """1 LLM call duy nhất — dùng Gemini (synthesis_llm), không dùng Qwen."""
    import instructor
    client = instructor.from_openai(self._synthesis_llm)

    plan = client.chat.completions.create(
        response_model=RetrievalPlan,
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Query: {state['query']}"},
        ],
    )
    logger.info("[Planner] %d steps planned: %s", len(plan.steps), plan.reasoning)
    return {"retrieval_plan": plan.model_dump()}
```

**`PLANNER_SYSTEM_PROMPT`** (thêm vào `prompts.py`):

```
Bạn là query planner cho hệ thống RAG đại học BKHN.
Sinh retrieval plan tối thiểu (≤4 steps) để lấy đủ thông tin trả lời query.

Collections:
- quy_dinh: quy định học vụ, học bổng, điều kiện tốt nghiệp
- chuong_trinh: môn học, tín chỉ, chương trình đào tạo
- ke_hoach: lịch đăng ký, lịch thi, deadline
- ho_tro_sv: biểu mẫu, hỗ trợ sinh viên

Nguyên tắc:
- So sánh A vs B → 2 steps, cùng collection, filter_hint khác nhau
- Multi-aspect → mỗi aspect 1 step, collection khác nhau
- Tối đa 4 steps — ưu tiên ít steps, query cụ thể
- needs_web=true chỉ khi cần thông tin ngoài database trường
```

#### 3.4.3 Executor node — Python thuần, parallel

```python
def _executor_node(self, state: AgentGraphState) -> dict:
    """Không có LLM. Gọi execute_parallel_plan từ tool_adapters."""
    from .tool_adapters import execute_parallel_plan, _web_search

    plan = state.get("retrieval_plan", {})
    steps = plan.get("steps", [])

    labeled_results = execute_parallel_plan(steps)

    tool_messages = [
        ToolMessage(
            content=f"### {label}\n{result}"[:self._tool_result_limit],
            tool_call_id=f"plan_{i}",
            name="rag_search",
        )
        for i, (label, result) in enumerate(labeled_results)
    ]

    if plan.get("needs_web"):
        web_result = _web_search(query=state["query"])
        tool_messages.append(ToolMessage(
            content=web_result[:self._tool_result_limit],
            tool_call_id="plan_web",
            name="web_search",
        ))

    return {"messages": tool_messages}
```

#### 3.4.4 Graph topology mới

```python
def _build_graph(self) -> Any:
    graph = StateGraph(AgentGraphState)

    # Nodes
    graph.add_node("pre_clarify", self._pre_clarify_node)
    graph.add_node("planner",     self._planner_node)      # MỚI
    graph.add_node("executor",    self._executor_node)     # MỚI
    graph.add_node("agent",       self._agent_node)        # GIỮ cho fallback path
    graph.add_node("tools",       self._tools_node)        # GIỮ cho fallback path
    graph.add_node("synthesize",  self._synthesize_node)
    graph.add_node("extract_answer", self._extract_answer_node)

    # Edges
    graph.add_edge(START, "pre_clarify")
    graph.add_conditional_edges(
        "pre_clarify", self._after_pre_clarify,
        {
            "planner":        "planner",
            "agent":          "agent",
            "extract_answer": "extract_answer",
        }
    )
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "synthesize")     # planner path → synthesize trực tiếp

    graph.add_conditional_edges(               # agent loop path giữ nguyên
        "agent", self._should_continue,
        {"tools": "tools", "synthesize": "synthesize", "end": "extract_answer"},
    )
    graph.add_conditional_edges(
        "tools", self._after_tools,
        {"agent": "agent", "synthesize": "synthesize", "end": "extract_answer"},
    )
    graph.add_edge("synthesize",    END)
    graph.add_edge("extract_answer", END)

    return graph.compile()
```

---

### 3.5 `complexity_router.py` — Không thay đổi

Router vẫn giữ nguyên — phân loại `simple` / `complex` / `chitchat`. Việc chọn `planner path` vs `agent loop path` trong nội bộ complex được xử lý bởi `_after_pre_clarify` trong graph.

---

### 3.6 `prompts.py` — Cập nhật 2 prompts

**`AGENT_SYSTEM_PROMPT`** — bỏ phần hướng dẫn `compare_cohorts`, `compare_programs`, `multi_rag_search`. Giữ 3 tools còn lại. Ước tính giảm ~150 tokens.

**Thêm `PLANNER_SYSTEM_PROMPT`** — prompt cho planner node (xem mục 3.4.2).

**`SYNTHESIS_PROMPT`** — giữ nguyên, đã tốt.

---

## 4. Tác động lên latency

| Scenario | Trước | Sau |
|---|---|---|
| So sánh K65 vs K70 | 60-120s (2 Qwen iterations) | ~15-25s (1 Gemini plan + parallel exec) |
| So sánh IT-E6 vs IT-E7 | 60-120s | ~15-25s |
| Đủ điều kiện tốt nghiệp | 60-120s (multi-collection) | ~15-25s |
| Web search fallback | 15-40s | 15-40s (agent loop path, không đổi) |
| Simple query | ~4-8s | ~4-8s (không đổi) |

---

## 5. Thứ tự implement

```
Phase 1 — Không breaking change
  ├─ graph_state.py: thêm fields mới
  ├─ tool_adapters.py: thêm execute_parallel_plan()
  └─ prompts.py: thêm PLANNER_SYSTEM_PROMPT

Phase 2 — Core refactor
  ├─ react_agent.py: thêm _planner_node, _executor_node
  ├─ react_agent.py: thêm _needs_planner(), cập nhật _after_pre_clarify
  └─ react_agent.py: cập nhật _build_graph() với topology mới

Phase 3 — Cleanup (sau khi test)
  ├─ lc_tools.py: xóa compare_cohorts, compare_programs, multi_rag_search
  └─ prompts.py: cập nhật AGENT_SYSTEM_PROMPT bỏ tools đã xóa

Phase 4 — Validation
  ├─ Test planner path: so sánh khóa, so sánh ngành, multi-collection
  ├─ Test agent loop path: web search, unknown patterns
  └─ Test backward compatibility: simple queries không bị ảnh hưởng
```

> ⚠️ **Phase 3 chỉ thực hiện sau khi Phase 4 pass** — giữ `compare_cohorts`, `compare_programs` trong `tool_adapters.py` (không xóa implementation), chỉ xóa khỏi `LANGGRAPH_TOOLS` list.

---

## 6. Tóm tắt thay đổi theo file

| File | Thay đổi | Mức độ |
|---|---|---|
| `graph_state.py` | Thêm 3 fields | Nhỏ |
| `tool_adapters.py` | Thêm `execute_parallel_plan()` | Nhỏ |
| `lc_tools.py` | Xóa 3 tools khỏi `LANGGRAPH_TOOLS` | Nhỏ (Phase 3) |
| `prompts.py` | Thêm `PLANNER_SYSTEM_PROMPT`, trim `AGENT_SYSTEM_PROMPT` | Nhỏ |
| `react_agent.py` | Thêm 2 nodes, 1 routing function, cập nhật graph | **Trung bình** |
| `complexity_router.py` | **Không thay đổi** | — |
| `state.py` | **Không thay đổi** | — |
