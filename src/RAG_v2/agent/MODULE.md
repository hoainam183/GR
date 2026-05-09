# Module: `agent` — LangGraph ReAct Agent & Planner-Executor Layer

## Tổng quan

Module `agent` triển khai **Agentic RAG** sử dụng LangGraph framework. Kể từ phiên bản refactor Planner-Executor, kiến trúc hỗ trợ 2 luồng xử lý riêng biệt:
1. **Planner-Executor Path**: Dành cho các câu hỏi phức tạp đã biết trước pattern (so sánh khóa, so sánh ngành, đa nguồn). Dùng Gemini để phân tích, lập kế hoạch tìm kiếm (parallel) và tổng hợp, loại bỏ vòng lặp chậm chạp của local LLM.
2. **ReAct Agent Loop**: Dành cho các truy vấn general, ambiguous hoặc chitchat fallback. Dùng Qwen local để suy luận từng bước.

---

## Cấu trúc file

```
agent/
├── __init__.py           # Export ReActAgent
├── react_agent.py        # ReActAgent — LangGraph graph orchestrator
├── tool_adapters.py      # Tool implementations & execute_retrieval_plan (parallel)
├── lc_tools.py           # LangChain tool wrappers (LANGGRAPH_TOOLS list)
├── prompts.py            # System prompts: AGENT, SYNTHESIS, DECOMPOSE, PLANNER
├── state.py              # AgentState dataclass — kết quả cuối của agent run
├── graph_state.py        # AgentGraphState TypedDict — state internal với planner fields
└── tools.py              # Tool schema definitions
```

> **Lưu ý:** `complexity_router.py` đã chuyển sang module `query/` (xem `query/MODULE.md`).

---

## Nhiệm vụ chi tiết

### `react_agent.py` — `ReActAgent` (LangGraph)

**Kiến trúc graph mới (Dual-Path):**
```
START ─[_route_complex]─┬─► decompose → planner ─[_after_planner]─┬─► executor → synthesize → END
                        │                                         └─► agent (fallback)
                        └─► agent ─[_should_continue]─┬─► tools ─[_after_tools]─┬─► agent
                                                      ├─► synthesize → END      ├─► synthesize → END
                                                      └─► extract_answer → END  └─► extract_answer → END
```

**Cải tiến quan trọng:**
- **Chống thiên lệch Planner (Anti-bias):** Nâng cấp logic tiêm mã ngành tại `_decompose_node()` và `_planner_node()`. Khi phát hiện từ khóa so sánh gián tiếp (`so sánh`, `khác gì`, `khác nhau`, `với`), hệ thống sẽ tuyệt đối không tự động tiêm `major_code` hiện tại từ `user_context` vào, tránh làm thiên lệch Planner.
- `_after_tools()`: Detect `[Loi...]` prefix → synthesize sớm. Nếu `[Khong tim thay...]`, retry (vòng lại `agent`).
- `_agent_node()`: Quản lý Retry Defense-in-depth: nếu tool trả về trống, inject SystemMessage hint (giảm từ khóa, bỏ thông tin cá nhân). Nếu `empty_result_count >= 2`, abort và synthesize.
- `_validate_plan()`: Kiểm tra chất lượng plan (>50% steps hợp lệ) trước khi execute. Reject nếu query rỗng hoặc collection không hợp lệ.
- `_VALID_COLLECTIONS`: Frozenset các collection hợp lệ mà Planner được phép dùng.
- Import `execute_retrieval_plan` và `web_search_for_executor` được đưa lên top-level.

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

**Query Sanitization:**
- Hàm `strip_personal_identifiers`: Loại bỏ mã sinh viên (chuỗi 8 số) hoặc tiền tố "mã sv:" ra khỏi truy vấn RAG để không làm nhiễu không gian Semantic vector (BGE-M3).

**Thread-safety — Per-request docs (quan trọng):**
- `AGENT_RETRIEVED_DOCS` đã được thay thế bằng `_agent_docs_ctx: ContextVar` để mỗi request có danh sách riêng.
- Gọi `init_agent_docs()` trong thread worker (trong `pipeline.query_agent()`) trước khi chạy agent.
- Gọi `get_agent_docs()` sau agent.run() để lấy docs của request đó.
- `web_search_for_executor()`: Public wrapper cho `_web_search`, được import top-level từ `react_agent.py`.

---

### `prompts.py` — Agent Prompts

- `AGENT_SYSTEM_PROMPT`: Hướng dẫn Qwen local (đã được làm gọn ~250 tokens).
- `SYNTHESIS_PROMPT`: Tổng hợp kết quả.
- `DECOMPOSE_SYSTEM_PROMPT`: Tách query thành mảng `sub_questions`.
- `PLANNER_SYSTEM_PROMPT`: Lên JSON retrieval plan (có hỗ trợ `cohort_hint`, `major_hint` từ `user_context`).

---

### `state.py` & `graph_state.py`

- `AgentGraphState` bổ sung: `execution_path`, `sub_questions`, `retrieval_plan`, `user_context`, `empty_result_count` (cho retry logic).
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
