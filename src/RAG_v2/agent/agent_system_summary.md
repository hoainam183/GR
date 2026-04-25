# Tóm tắt Hệ thống Agentic RAG với LangGraph

## Tổng quan kiến trúc

Hệ thống là một **Agentic RAG** được xây dựng theo **Option A** — Agent là layer bổ sung nằm trên RAG v2 pipeline cũ, không phá vỡ backward compatibility.

```
Query
  │
  ▼
ComplexityRouter
  ├── "chitchat"  → Canned response handler
  ├── "simple"    → RAG v2 Pipeline (giữ nguyên)
  └── "complex"   → ReActAgent (LangGraph)
                        │
                    StateGraph
                    START → agent ──┬→ tools → agent (loop)
                                    ├→ synthesize → END
                                    └→ extract_answer → END
```

---

## Các thành phần chính

### 1. `ComplexityRouter` — Phân loại câu hỏi

Ba tầng routing dựa trên regex pattern matching và heuristics:

| Tier | Điều kiện | Xử lý |
|---|---|---|
| `chitchat` | Chào hỏi, cảm ơn, tạm biệt | Short-circuit, không vào RAG |
| `simple` | Câu hỏi đơn domain, rõ ràng | RAG v2 pipeline cũ |
| `complex` | So sánh 2 khóa/ngành, điều kiện tốt nghiệp, câu mơ hồ, >30 từ | LangGraph Agent |

Pattern matching phân biệt được mã khóa (`K65`) vs mã ngành (`IT-E6`), phát hiện multi-question qua đếm dấu `?` và conjunction `" và "`.

---

### 2. `AgentGraphState` — Runtime State của LangGraph

```python
class AgentGraphState(TypedDict):
    messages: Annotated[list, add_messages]  # add_messages reducer
    tool_call_history: list[str]             # coarse loop detection
    tool_call_signatures: list[str]          # exact duplicate detection
    iteration: int
    max_iterations: int
    final_answer: str | None
    error: str | None
```

Tách biệt hoàn toàn với `AgentState` (dataclass dùng cho MongoDB logging) — tránh coupling giữa execution layer và persistence layer.

---

### 3. `AgentState` — Persistence State

Dùng để log MongoDB sau khi graph chạy xong.

| Field | Mô tả |
|---|---|
| `tool_results` | Chỉ giữ **3 kết quả gần nhất** để inject vào LLM context |
| `_log_tool_results` | Giữ **toàn bộ** để ghi MongoDB, không bao giờ bị truncate |

---

### 4. `ReActAgent` — LangGraph Graph

**4 nodes:**

| Node | Chức năng |
|---|---|
| `agent_node` | Gọi LLM với bound tools, quyết định hành động tiếp theo |
| `tools_node` | Thực thi tool calls, ghi signature cho duplicate detection |
| `synthesize_node` | Fallback: tổng hợp từ tool results khi hết iterations hoặc loop |
| `extract_answer_node` | Trích xuất direct answer khi LLM trả lời không dùng tool |

**Loop detection 2 tầng:**

```
Exact duplicate (cùng name + cùng args)  →  synthesize ngay
Cùng tool name, khác args:
  - rag_search        → ALLOWED (collection khác là hợp lệ)
  - clarify_question  → ALLOWED
  - Tất cả tool khác  → synthesize (conservative với Qwen 8B)
```

**Conditional edge sau `tools_node`:** nếu `clarify_question` vừa được gọi → route thẳng đến `extract_answer` thay vì quay lại `agent`, tránh agent tiếp tục suy luận khi đang chờ user input.

**2 LLM instances riêng biệt:**

| Instance | Dùng cho | max_tokens |
|---|---|---|
| `_llm_with_tools` | `agent_node` — chọn tool | 800 |
| `_synthesis_llm` | `synthesize_node` — tổng hợp câu trả lời | 1200 |

---

### 5. `LANGGRAPH_TOOLS` — 6 tools được định nghĩa

| Tool | Mục đích | Ghi chú |
|---|---|---|
| `rag_search` | Tìm trong 1 collection | 4 collections: quy_dinh, chuong_trinh, ke_hoach, ho_tro_sv |
| `multi_rag_search` | Tìm đồng thời ≥2 collections | Min 2, max 4 queries |
| `compare_cohorts` | So sánh giữa 2 **mã khóa** (K65, K70) | Từ chối mã ngành |
| `compare_programs` | So sánh giữa 2 **mã ngành** (IT-E6, IT-E7) | Từ chối mã khóa |
| `web_search` | Tavily — fallback khi database không có | Chỉ dùng khi rag_search thất bại |
| `clarify_question` | Hỏi lại user khi câu quá mơ hồ | Tối đa 1 lần/lượt hội thoại |

Guard cứng trong `tool_adapters.py`: `compare_cohorts` từ chối mã ngành và ngược lại.

---

### 6. `tool_adapters.py` — Execution Layer

- **In-memory FIFO cache** (256 entries, thread-safe) cho `rag_search` — tránh gọi Qdrant + reranker lặp lại
- **Lazy singleton** cho toàn bộ runtime (embedders, searcher, reranker, Tavily) — chỉ khởi tạo lần đầu
- **Hybrid retrieval**: BGE-M3 + E5 Multilingual embeddings, reranker optional
- Cache key bao gồm: `(query, collection, top_k, cohort, major)` — đủ granular để tránh cache collision

---

## Luồng xử lý điển hình

```
"So sánh học bổng KKHT giữa K65 và K70"
  │
  ├─ ComplexityRouter → "complex" (khớp pattern K\d{2}.+K\d{2})
  │
  ├─ ReActAgent.run()
  │     │
  │     ├─ agent_node: LLM chọn compare_cohorts(K65, K70, quy_dinh)
  │     ├─ _should_continue → "tools"
  │     ├─ tools_node: gọi _compare_cohorts → 2x rag_search (K65, K70)
  │     ├─ _after_tools → "agent"
  │     ├─ agent_node: LLM tổng hợp và trả lời trực tiếp
  │     ├─ _should_continue: không có tool_calls → "end"
  │     └─ extract_answer_node: lấy AIMessage.content
  │
  └─ _to_agent_state(): rebuild ToolResult list → AgentState → MongoDB
```

---

## Điểm mạnh của thiết kế

**Backward compatibility hoàn toàn** — `query()` cũ không bị động đến, `run()` trả về `AgentState` giống hệt phiên bản custom ReAct.

**Graceful degradation** — Mọi failure path đều có fallback:

```
LLM lỗi        → synthesize_node (tổng hợp từ tool results hiện có)
Graph crash    → _make_error_state (trả về state có final_answer)
Agent thất bại → fallback về RAG v2 pipeline
```

**Separation of concerns rõ ràng:**

```
AgentGraphState  →  execution layer (LangGraph runtime)
AgentState       →  persistence layer (MongoDB logging)
TOOL_DEFINITIONS →  spec / documentation (OpenAI JSON format)
LANGGRAPH_TOOLS  →  runtime execution (LangChain StructuredTool)
```

**Context window management cho Qwen 8B:**

- Tool results bị cap **2000 chars** trong ToolMessage
- `tool_results` trong AgentState giữ tối đa **3 entries** cho LLM context
- Synthesis LLM có `max_tokens=1200` (cao hơn agent LLM 800) để đảm bảo câu trả lời hoàn chỉnh

---

## Stack công nghệ

| Thành phần | Công nghệ |
|---|---|
| LLM | Qwen 2.5 8B Instruct (via LM Studio) |
| Agent Framework | LangGraph + LangChain |
| Vector DB | Qdrant |
| Persistence | MongoDB |
| Embeddings | BGE-M3 + E5 Multilingual |
| Web Search | Tavily |
| Language | Python 3.11+ |

---

*Stack: Qwen 2.5 8B · LM Studio · Qdrant · MongoDB · Python · LangGraph*
*Kiến trúc: Option A — Agent là layer bổ sung, câu đơn giản vẫn dùng RAG v2 pipeline cũ*
