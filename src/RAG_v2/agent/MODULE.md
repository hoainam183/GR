# Module: `agent` — LangGraph ReAct Agent Layer

## Tổng quan

Module `agent` triển khai **Agentic RAG** sử dụng LangGraph framework. Thay vì chạy một lần retrieve-generate cố định, agent có khả năng **lập kế hoạch và thực thi nhiều bước** (multi-hop reasoning): chọn tool, gọi tool, nhận kết quả, quyết định bước tiếp theo. Được dùng cho các câu hỏi phức tạp: so sánh, đa nguồn, điều kiện đa tiêu chí.

---

## Cấu trúc file

```
agent/
├── __init__.py           # Export ReActAgent, ComplexityRouter
├── react_agent.py        # ReActAgent — LangGraph graph orchestrator
├── complexity_router.py  # ComplexityRouter — phân loại simple/complex/chitchat
├── tool_adapters.py      # Tool implementations (rag_search, compare, web_search...)
├── lc_tools.py           # LangChain tool wrappers (LANGGRAPH_TOOLS list)
├── prompts.py            # System prompts: AGENT_SYSTEM_PROMPT, SYNTHESIS_PROMPT
├── state.py              # AgentState dataclass — kết quả cuối của agent run
├── graph_state.py        # AgentGraphState TypedDict — LangGraph internal state
└── tools.py              # Tool schema definitions
```

---

## Nhiệm vụ chi tiết

### `complexity_router.py` — `ComplexityRouter`

**Nhiệm vụ:** Phân loại query trước khi chọn pipeline xử lý.

**3 tier routing:**

| Tier | Pattern | Xử lý |
|---|---|---|
| `chitchat` | xin chào, cảm ơn, tạm biệt | hardcoded reply (0ms) |
| `simple` | không có complex signals | RAG v2 pipeline |
| `complex` | patterns phức tạp (xem bên dưới) | LangGraph ReAct agent |

**Complex patterns (regex-based):**
- `so sánh` — từ khóa so sánh
- Hai cohort codes trong cùng query: `K65 ... K70`
- Hai programme codes: `IT-E6 ... IT-E7`
- `khác nhau` + `K\d{2}/ngành/chương trình`
- `đủ điều kiện` — multi-source eligibility
- Câu hỏi đa điều kiện: `(có thể/có được) ... (tốt nghiệp/đăng ký/học bổng)`
- Query > 30 words
- Query có > 1 dấu `?`

---

### `react_agent.py` — `ReActAgent` (LangGraph)

**Kiến trúc graph:**
```
START → agent ─┬→ tools → agent (loop, tối đa max_iterations=4)
               ├→ synthesize → END
               └→ extract_answer → END
```

**Nodes:**

| Node | Nhiệm vụ | LLM |
|---|---|---|
| `agent_node` | Call LLM với bound tools → quyết định gọi tool nào | ✅ Agent LLM |
| `tools_node` | Execute tool calls, ghi results vào state | ❌ |
| `synthesize_node` | Tổng hợp kết quả khi hit iteration limit | ✅ Synthesis LLM |
| `extract_answer_node` | Extract câu trả lời trực tiếp từ LLM | ❌ |

**2 LLMs riêng biệt:**

| LLM | Vai trò | Provider default |
|---|---|---|
| `_llm_with_tools` | Tool calling, reasoning, planning | LM Studio (Qwen2.5-8b) |
| `_synthesis_llm` | Final answer synthesis (chất lượng cao hơn) | LM Studio hoặc Gemini |

**Duplicate detection:**
- Exact duplicate (same name + same args) → `synthesize`
- Same tool repeated (except `rag_search`, `clarify_question`) → `synthesize`

**Edge routing (`_should_continue`):**
```
1. error flag → synthesize
2. no tool calls → end (direct answer)
3. max iterations → synthesize
4. exact duplicate call → synthesize
5. repeated tool (not rag_search/clarify) → synthesize
6. else → tools (continue loop)
```

---

### `tool_adapters.py` — Tool Implementations

**6 tools có sẵn:**

| Tool | Mô tả |
|---|---|
| `rag_search` | Search một collection cụ thể (embed + vector/keyword search + rerank) |
| `multi_rag_search` | Gọi `rag_search` với nhiều (query, collection) pairs |
| `compare_cohorts` | So sánh theo khóa: `rag_search(topic + K65)` vs `rag_search(topic + K70)` |
| `compare_programs` | So sánh theo ngành: `rag_search(topic + IT-E6)` vs `rag_search(topic + IT-E7)` |
| `web_search` | Tavily web search (dự phòng) |
| `clarify_question` | Yêu cầu user cung cấp thêm thông tin |

**Collection mapping:**
```python
COLLECTION_MAP = {
    "quy_dinh":     "quydinh",   # quy định học vụ
    "chuong_trinh": "ctdt",      # chương trình đào tạo
    "ke_hoach":     "kehoach",   # kế hoạch học kỳ
    "ho_tro_sv":    "stsv",      # hỗ trợ sinh viên
}
```

**In-memory cache cho `rag_search`:** 256 entries FIFO — tránh query lại cùng một thông tin trong cùng agent run.

---

### `prompts.py` — Agent Prompts

**`AGENT_SYSTEM_PROMPT`:** Hướng dẫn agent:
- Vai trò: tư vấn học vụ ĐHBK
- Khi nào dùng tool nào
- Quy tắc không lặp tool
- Format câu trả lời Tiếng Việt
- Khi nào dùng `clarify_question`

**`SYNTHESIS_PROMPT`:** Hướng dẫn synthesis LLM tổng hợp kết quả từ nhiều tool calls thành câu trả lời cuối.

---

### `state.py` — `AgentState`

Dataclass lưu kết quả sau khi agent run xong:
```python
@dataclass
class AgentState:
    query: str
    session_id: str
    iteration: int
    tool_call_history: List[str]
    tool_results: List[ToolResult]
    final_answer: Optional[str]
    error: Optional[str]
```

**`to_log_dict()`:** Serialize thành dict để ghi MongoDB.

---

## Luồng Agent Run điển hình

```
query: "So sánh quy định học bổng giữa IT-E6 và IT-E7"

START
  │
  ▼
agent_node (Qwen2.5-8b + tools)
  → Quyết định: gọi compare_programs(topic="học bổng", major_a="IT-E6", major_b="IT-E7", collection="quy_dinh")
  │
  ▼
tools_node
  → compare_programs() → gọi _rag_search(x2) → kết quả A và B
  │
  ▼
agent_node (lần 2)
  → Đủ thông tin → trả lời trực tiếp (không gọi tool)
  │
  ▼
extract_answer_node → final_answer
  │
  ▼
END
```

---

## LLM involvement

Module `agent` có **nhiều LLM calls nhất** trong toàn hệ thống:

| Call | LLM | Latency | Lần/run |
|---|---|---|---|
| `agent_node` (tool calling) | Qwen2.5-8b (local) | **2000-30000ms** | 1-4 lần |
| `synthesize_node` (fallback) | Qwen2.5-8b | **2000-10000ms** | 0-1 lần |
| Tool execution: `rag_search` | ❌ Không LLM | 100-500ms/call | 1-8 calls |
| Tool execution: `web_search` | ❌ Không LLM | 500-2000ms | 0-1 lần |

> ⚠️ **Agent path có thể tốn 30-120 giây** do:
> 1. LM Studio inference chậm hơn Gemini API
> 2. Nhiều LLM calls tuần tự (không parallel được trong ReAct loop)
> 3. Mỗi iteration = 1 LLM call + N tool calls

---

## Latency contribution

| Scenario | Thời gian |
|---|---|
| Agent path (2 iterations, LM Studio) | **60-120s** ⚠️ |
| Agent path (1 iteration, Gemini synthesis) | **15-40s** |
| Simple RAG fallback (khi agent fail) | ~4-8s |

> ⚠️ **Đây là nguyên nhân chính** gây ra latency trung bình 160s khi câu hỏi được route vào agent.
