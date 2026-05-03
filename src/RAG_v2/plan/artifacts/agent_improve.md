# Phân tích hệ thống Agent RAG — Học vụ HUST

> Dựa trên code review: `complexity_router.py`, `react_agent.py`, `tool_adapters.py`, `graph_state.py`, `lc_tools.py`, `prompts.py`, `state.py`

---

## 1. Vấn đề gặp phải

### 1.1 Routing sai do pattern quá rộng

**Mô tả:** `ComplexityRouter` dùng regex pattern `\bđủ\s+điều\s+kiện\b` để gán `multi_source` subtype, nhưng pattern này bắt một tập query rất không đồng nhất.

**Ví dụ cụ thể:**

```
"tôi có đủ điều kiện tốt nghiệp không?"
→ Route: multi_source → Planner-Executor  ✗ (cần ReAct, thiếu context cá nhân)

"đủ điều kiện nhận học bổng KKHT gồm những gì?"
→ Route: multi_source → Planner-Executor  ✓ (đúng)

"môn Mạng máy tính có đủ điều kiện đăng ký không?"
→ Route: multi_source → Planner-Executor  ✗ (RAG đơn giản là đủ)
```

**Hậu quả:** Query cần clarify cá nhân bị đẩy vào planner, sinh ra retrieval plan nhưng không thể trả lời "bạn CÓ đủ hay không" vì thiếu thông tin GPA, tín chỉ, ngoại ngữ của sinh viên cụ thể.

---

### 1.2 Heuristic `word_count > 30` quá thô

**Mô tả:** Một câu hỏi dài về một chủ đề duy nhất bị route nhầm sang `complex/general`.

**Ví dụ cụ thể:**

```
"Cho tôi biết chi tiết về quy trình đăng ký học lại môn
 Giải tích 1 bao gồm thời gian, địa điểm và các bước cần làm"
→ word_count = 31 → Route: complex/general → ReAct agent loop  ✗
→ Thực tế: một chủ đề, một collection ke_hoach, RAG đơn giản là đủ
```

---

### 1.3 `AGENT_RETRIEVED_DOCS` là global mutable không thread-safe

**Mô tả:** Biến `AGENT_RETRIEVED_DOCS: list[dict] = []` trong `tool_adapters.py` được ghi bởi mọi agent run đồng thời mà không có lock.

**Ví dụ cụ thể:**

```python
# tool_adapters.py
AGENT_RETRIEVED_DOCS: list[dict[str, Any]] = []  # ← không có lock

# _rag_search() và _format_web_results() đều ghi vào list này
AGENT_RETRIEVED_DOCS.extend(results)  # race condition khi 2 user cùng query
```

**Hậu quả:** Trong môi trường nhiều user đồng thời, trace log của user A lẫn với kết quả của user B. Khó debug, dữ liệu analytics bị nhiễu.

---

### 1.4 Import lồng trong method `_executor_node`

**Mô tả:** `tool_adapters` được import bên trong body của method thay vì top-level.

**Ví dụ cụ thể:**

```python
# react_agent.py
def _executor_node(self, state: AgentGraphState) -> dict[str, Any]:
    from .tool_adapters import execute_retrieval_plan, _web_search  # ← runtime import
    ...
```

**Vấn đề kép:**
- `_web_search` là private function, bị import trực tiếp — vi phạm encapsulation.
- Import trong method body che giấu dependency, khó test và debug.

---

### 1.5 Không detect tool error trong `_after_tools`

**Mô tả:** Khi tool trả về chuỗi `[Loi...]`, agent vẫn loop lại bình thường thay vì synthesize sớm.

**Ví dụ cụ thể:**

```python
# Khi Qdrant down hoặc collection sai:
tool_result = "[Loi: Collection 'quy_dinh' khong hop le]"

# _after_tools không kiểm tra content của ToolMessage
# → agent dùng kết quả lỗi này để "reason" tiếp
# → iteration 2: gọi lại tool với query khác → vẫn lỗi
# → iteration 3, 4... → hết max_iterations → synthesize
# → tốn 3-4 LLM calls thay vì dừng ngay
```

---

### 1.6 Planner-Executor không validate plan chất lượng

**Mô tả:** `_after_planner` chỉ kiểm tra `plan.get("steps")` tồn tại, không kiểm tra chất lượng từng step.

**Ví dụ cụ thể:**

```python
# Gemini trả về plan hợp lệ về cú pháp nhưng kém chất lượng:
{
  "steps": [
    {"query": "", "collection": "quy_dinh", "label": "step_1"},  # query rỗng
    {"query": "tốt nghiệp", "collection": "invalid_col", "label": "step_2"}  # collection sai
  ]
}
# _after_planner thấy steps != [] → route đến executor
# executor chạy → rag_search trả về [Loi] cho cả 2 steps
# synthesize với context toàn lỗi → câu trả lời vô nghĩa
```

---

### 1.7 Personal context query không được nhận diện

**Mô tả:** Query chứa đại từ nhân xưng kết hợp với điều kiện cá nhân không có subtype riêng, bị lẫn vào `multi_source`.

**Ví dụ cụ thể:**

```
"Tôi học IT-E6, GPA 2.8, đã tích lũy 120 tín chỉ — tôi có đủ ĐK tốt nghiệp chưa?"
→ Khớp \bđủ\s+điều\s+kiện\b → multi_source → Planner-Executor
→ Planner tạo plan tìm kiếm "điều kiện tốt nghiệp IT-E6"
→ Executor trả về quy định chung
→ Synthesize KHÔNG so sánh được GPA 2.8 vs ngưỡng, vì Planner không biết
   sinh viên đã tự cung cấp thông tin cá nhân trong query
```

---

## 2. Hướng giải quyết

### 2.1 Tách "personal context query" khỏi `multi_source`

Thêm pattern ưu tiên cao hơn vào `_COMPLEX_PATTERN_SPECS`, đặt **trước** pattern `multi_source`:

```python
# complexity_router.py — thêm vào đầu _COMPLEX_PATTERN_SPECS
(
    r"\b(tôi|mình|em)\b.{0,60}\b(có\s+thể|đủ|đạt|được\s+không|có\s+được)\b",
    "personal_check"   # ← subtype mới
),
```

Trong `react_agent.py`, xử lý subtype mới:

```python
# react_agent.py — run()
execution_path = "agent"
if complexity_subtype in ("comparison", "multi_source"):
    execution_path = "planner"
elif complexity_subtype == "personal_check":
    execution_path = "agent"   # ReAct để có thể clarify
```

---

### 2.2 Cải thiện heuristic word_count

Kết hợp thêm điều kiện số entity type xuất hiện:

```python
# complexity_router.py — thay thế heuristic word_count đơn thuần
if word_count > 30:
    # Kiểm tra thêm: nếu chỉ có 1 loại entity → vẫn là simple
    has_multiple_topics = bool(
        re.search(r"\b(và|cũng|ngoài ra|đồng thời)\b", q_lower)
    )
    if has_multiple_topics:
        result = {"tier": "complex", "reason": f"heuristic: word_count={word_count} + multi_topic", ...}
    else:
        result = {"tier": "simple", "reason": f"heuristic: long_but_single_topic", ...}
```

---

### 2.3 Fix thread-safety cho `AGENT_RETRIEVED_DOCS`

Thay global list bằng `contextvars.ContextVar` để mỗi request có context riêng:

```python
# tool_adapters.py
from contextvars import ContextVar

_agent_docs_var: ContextVar[list] = ContextVar('agent_docs', default=None)

def init_agent_docs() -> list:
    docs: list = []
    _agent_docs_var.set(docs)
    return docs

def get_agent_docs() -> list:
    docs = _agent_docs_var.get(None)
    return list(docs) if docs is not None else []

def _append_agent_doc(item) -> None:
    docs = _agent_docs_var.get(None)
    if docs is not None:
        docs.append(item)
```

---

### 2.4 Fix import trong `_executor_node`

```python
# tool_adapters.py — expose public function
def web_search_public(query: str) -> str:
    """Public wrapper cho _web_search, dùng bởi executor."""
    return execute_tool("web_search", {"query": query})

# react_agent.py — top-level import
from .tool_adapters import execute_retrieval_plan, web_search_public

def _executor_node(self, state: AgentGraphState) -> dict[str, Any]:
    # không còn import lồng
    plan = state.get("retrieval_plan") or {}
    ...
    if plan.get("needs_web"):
        web_result = web_search_public(query=state["query"])
```

---

### 2.5 Detect tool error trong `_after_tools`

```python
# react_agent.py
def _after_tools(self, state: AgentGraphState) -> Literal["agent", "synthesize", "end"]:
    history = state.get("tool_call_history", [])
    if not history:
        return "agent"

    last_tool = history[-1]

    if last_tool == "clarify_question":
        return "end"

    # Kiểm tra ToolMessage cuối có phải lỗi không
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            content = str(msg.content or "")
            if content.startswith("[Loi") or content.startswith("[Khong tim thay"):
                logger.warning("[Agent] Tool returned error — forcing synthesize")
                return "synthesize"
            break

    return "agent"
```

---

### 2.6 Validate plan chất lượng trước khi execute

```python
# react_agent.py
VALID_COLLECTIONS = {"quy_dinh", "chuong_trinh", "ke_hoach", "ho_tro_sv"}

def _validate_plan(self, plan: dict) -> bool:
    steps = plan.get("steps", [])
    if not steps:
        return False
    valid_steps = [
        s for s in steps
        if s.get("query", "").strip()
        and s.get("collection") in VALID_COLLECTIONS
    ]
    if len(valid_steps) < len(steps) * 0.5:   # hơn 50% steps lỗi → reject
        logger.warning("[Planner] Plan quality too low: %d/%d valid steps",
                       len(valid_steps), len(steps))
        return False
    return True

def _after_planner(self, state):
    plan = state.get("retrieval_plan")
    if plan and self._validate_plan(plan):
        return "executor"
    logger.warning("[Planner] Invalid plan — falling back to agent loop")
    return "agent"
```

---

## 3. Hướng phát triển hệ thống Agent

### 3.1 Ngắn hạn — Ổn định hóa (1–2 sprint)

| Việc cần làm | Ưu tiên | Effort |
|---|---|---|
| Fix thread-safety `AGENT_RETRIEVED_DOCS` | Cao | Thấp |
| Thêm `personal_check` subtype vào router | Cao | Thấp |
| Fix runtime import trong `_executor_node` | Trung | Thấp |
| Detect tool error trong `_after_tools` | Cao | Thấp |
| Validate plan quality trong `_after_planner` | Trung | Trung |

---

### 3.2 Trung hạn — Nâng chất lượng routing (1–2 tháng)

**Semantic routing thay thế regex thuần:**

Thay vì regex pattern matching, dùng một LLM nhỏ (hoặc embedding classifier) để phân loại query. Routing accuracy sẽ cao hơn đáng kể cho các câu hỏi tiếng Việt có ngữ cảnh phức tạp.

```python
# Ý tưởng: ComplexityRouter có thêm phương thức semantic
def route_semantic(self, query: str) -> Dict[str, Any]:
    # Dùng embedding similarity với một tập ví dụ đã label
    # Fallback về regex nếu similarity không đủ cao
    ...
```

**Logging và phân tích routing decisions:**

Router đã có `logger.info` — cần thêm pipeline thu thập log để phát hiện:
- Những pattern nào hay bị route sai (false positive / negative)
- Phân phối `tier` và `complex_subtype` theo thời gian
- Correlation giữa routing decision và user satisfaction

---

### 3.3 Dài hạn — Kiến trúc mở rộng

**Thêm tầng user context injection:**

Khi sinh viên đã đăng nhập, inject `user_context` (GPA, tín chỉ, khóa, ngành) vào prompt của `_agent_node`. Agent sẽ có thể trả lời "bạn CÓ đủ điều kiện" thay vì chỉ liệt kê checklist.

```python
# Trong _build_initial_messages:
if user_context:
    ctx_summary = f"Thông tin sinh viên: GPA={user_context.get('gpa')}, " \
                  f"tín chỉ={user_context.get('credits')}, khóa={user_context.get('cohort')}"
    messages.insert(1, SystemMessage(content=ctx_summary))
```

**Caching ở tầng plan:**

Với các query comparison phổ biến (IT-E6 vs IT-E7, K65 vs K70), plan thường giống nhau. Cache retrieval plan theo `(query_template, subtype)` để bỏ qua bước decompose + plan khi không cần thiết.

**Evaluation pipeline:**

Xây dựng bộ test case có ground truth để đo:
- Routing accuracy theo từng subtype
- Answer correctness (RAG faithfulness + relevance)
- Latency p50/p95 theo execution path

```
Ví dụ test case:
query: "So sánh môn học bắt buộc IT-E6 và IT-E7"
expected_tier: complex
expected_subtype: comparison
expected_path: planner
expected_collections: [chuong_trinh]
```

---

## Tóm tắt

```
Ổn định ngay:   thread-safety, tool error detection, import cleanup
Cải thiện routing: personal_check subtype, word_count heuristic
Dài hạn:        user context injection, semantic router, eval pipeline
```

Kiến trúc hybrid (Planner-Executor + ReAct) là đúng hướng cho domain học vụ.
Điểm mấu chốt cần cải thiện là **boundary giữa các nhánh routing** —
đặc biệt là tách "query cần thông tin cá nhân" ra khỏi `multi_source` pattern chung.