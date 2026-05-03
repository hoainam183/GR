# Module: `agent` — LangGraph ReAct Agent & Planner-Executor Layer

## Tổng quan

Module `agent` triển khai **Agentic RAG** sử dụng LangGraph framework. Kể từ phiên bản refactor Planner-Executor, kiến trúc hỗ trợ 2 luồng xử lý riêng biệt:
1. **Planner-Executor Path**: Dành cho các câu hỏi phức tạp đã biết trước pattern (so sánh khóa, so sánh ngành, đa nguồn). Dùng Gemini để phân tích, lập kế hoạch tìm kiếm (parallel) và tổng hợp, loại bỏ vòng lặp chậm chạp của local LLM.
2. **ReAct Agent Loop**: Dành cho các truy vấn general, ambiguous hoặc chitchat fallback. Dùng Qwen local để suy luận từng bước.

---

## Cấu trúc file

```
agent/
├── __init__.py           # Export ReActAgent, ComplexityRouter
├── react_agent.py        # ReActAgent — LangGraph graph orchestrator
├── complexity_router.py  # ComplexityRouter — phân loại simple/complex/chitchat và subtype
├── tool_adapters.py      # Tool implementations & execute_retrieval_plan (parallel)
├── lc_tools.py           # LangChain tool wrappers (LANGGRAPH_TOOLS list)
├── prompts.py            # System prompts: AGENT, SYNTHESIS, DECOMPOSE, PLANNER
├── state.py              # AgentState dataclass — kết quả cuối của agent run
├── graph_state.py        # AgentGraphState TypedDict — state internal với planner fields
└── tools.py              # Tool schema definitions
```

---

## Nhiệm vụ chi tiết

### `complexity_router.py` — `ComplexityRouter`

**Nhiệm vụ:** Phân loại query trước khi chọn pipeline xử lý.

**Tier routing:** `chitchat` | `simple` | `complex`

Đối với **`complex`**, router xác định thêm trường **`complex_subtype`**:
- `comparison`: So sánh 2 mã khóa hoặc 2 mã ngành.
- `multi_source`: Câu hỏi đa điều kiện (vd: "đủ điều kiện tốt nghiệp không").
- `general`: Câu hỏi dài, phức tạp nhưng không khớp pattern rõ ràng.

---

### `react_agent.py` — `ReActAgent` (LangGraph)

**Kiến trúc graph mới (Dual-Path):**
```
START ─[_route_complex]─┬─► decompose → planner ─[_after_planner]─┬─► executor → synthesize → END
                        │                                         └─► agent (fallback)
                        └─► agent ─[_should_continue]─┬─► tools ─[_after_tools]─┬─► agent
                                                      ├─► synthesize → END      ├─► synthesize → END
                                                      └─► extract_answer → END  └─► extract_answer → END
```

**Nodes:**
- `decompose`: Tách câu hỏi phức tạp thành sub-questions (Gemini).
- `planner`: Lên kế hoạch retrieval từ sub-questions (Gemini).
- `executor`: Chạy các steps song song bằng `ThreadPoolExecutor` (Không cần LLM).
- `agent`: Call Qwen LLM với bound tools (vòng lặp ReAct truyền thống).
- `tools`: Chạy tool từ agent loop.
- `synthesize` / `extract_answer`: Tổng hợp câu trả lời cuối.

**LLM Roles:**
- `_llm_with_tools` (Qwen local): Dùng cho agent loop (chậm, ~30-60s).
- `_synthesis_llm` (Gemini): Dùng cho Planner path (`decompose`, `planner`, `synthesize`) (nhanh, ~8-15s).

---

### `tool_adapters.py` — Tool Implementations

**Tools cho Agent Loop (`LANGGRAPH_TOOLS`):**
1. `rag_search`: Tìm 1 collection cụ thể.
2. `web_search`: Tavily web search.
3. `clarify_question`: Yêu cầu user cung cấp thêm thông tin.

*(Lưu ý: Các tool `multi_rag_search`, `compare_cohorts`, `compare_programs` đã bị loại bỏ khỏi Agent Loop vì được thay thế bởi Planner path)*

**Executor (`execute_retrieval_plan`):**
- Hàm nhận một list các steps (từ Planner) và chạy `_rag_search` song song qua `ThreadPoolExecutor`.

---

### `prompts.py` — Agent Prompts

- `AGENT_SYSTEM_PROMPT`: Hướng dẫn Qwen local (đã được làm gọn ~250 tokens).
- `SYNTHESIS_PROMPT`: Tổng hợp kết quả.
- `DECOMPOSE_SYSTEM_PROMPT`: Tách query thành mảng `sub_questions`.
- `PLANNER_SYSTEM_PROMPT`: Lên JSON retrieval plan (có hỗ trợ `cohort_hint`, `major_hint` từ `user_context`).

---

### `state.py` & `graph_state.py`

- `AgentGraphState` bổ sung: `execution_path`, `sub_questions`, `retrieval_plan`, `user_context`.
- `AgentState`: Output chuẩn để log vào DB.

---

## Luồng Planner-Executor điển hình (So sánh)

```
query: "So sánh quy định học bổng giữa K65 và K70"
user_context: { "cohort": "K66" }

START
  │ (complex_subtype = "comparison")
  ▼
decompose_node (Gemini)
  → ["Quy định học bổng K65", "Quy định học bổng K70"]
  │
  ▼
planner_node (Gemini)
  → {"steps": [
       {"query": "quy định học bổng", "collection": "quy_dinh", "cohort_hint": "K65"},
       {"query": "quy định học bổng", "collection": "quy_dinh", "cohort_hint": "K70"}
    ]}
  │
  ▼
executor_node (Parallel ThreadPool)
  → Lấy 2 kết quả song song (không tốn time LLM)
  │
  ▼
synthesize_node (Gemini)
  → Final Answer (Tổng ~8s - 12s)
  │
  ▼
END
```

---

## Latency contribution (Hiện tại)

| Scenario | Thời gian | Cải thiện |
|---|---|---|
| Planner path (So sánh, đa nguồn) | **8s - 15s** | ↓ 80% |
| Agent path fallback (General) | **60-120s** | Không đổi |
| Simple RAG fallback | ~4-8s | Không đổi |
