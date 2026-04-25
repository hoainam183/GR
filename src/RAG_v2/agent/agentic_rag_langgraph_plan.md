# Agentic RAG — Kế hoạch triển khai (LangGraph Edition)

> **Ngữ cảnh**: Nâng cấp RAG v2 (8-layer linear pipeline) → Agentic RAG với LangGraph  
> **Stack**: Qwen 2.5 8B · LM Studio · Qdrant · MongoDB · Python · LangGraph  
> **Kiến trúc**: Option A — Agent là layer bổ sung, câu đơn giản vẫn chạy pipeline cũ

---

## Tổng quan tiến độ

```
✅ Tuần 1  [████████████████]  State · Tools · Adapters · Test độc lập       (DONE)
🔄 Tuần 2* [████████░░░░░░░░]  LangGraph Migration Sprint (thay thế Tuần 2 cũ)
   Tuần 3  [░░░░░░░░░░░░░░░░]  Router · Tích hợp pipeline · E2E test
   Tuần 4  [░░░░░░░░░░░░░░░░]  MongoDB logging · Evaluation · Báo cáo
```

---

## Lý do chuyển sang LangGraph

| Vấn đề với Custom ReAct | LangGraph giải quyết |
|---|---|
| Loop detection thủ công dễ miss edge case | Built-in conditional edges, rõ ràng |
| Message history management error-prone | `add_messages` reducer tự xử lý |
| Khó visualize/debug luồng chạy | `graph.get_graph().draw_ascii()` |
| Test khó vì logic trải rải trong while loop | Mỗi node test độc lập |
| Mở rộng thêm node phải sửa while loop | Thêm node/edge không ảnh hưởng code cũ |

## Những gì giữ nguyên từ Tuần 1

- `agent/state.py` → **không đổi** (AgentState vẫn dùng để log MongoDB)
- `agent/tools.py` → **không đổi** (TOOL_DEFINITIONS vẫn là spec)
- `agent/tool_adapters.py` → **không đổi** (execute_tool vẫn là execution layer)
- `agent/prompts.py` → **không đổi**
- `agent/complexity_router.py` → **không đổi**

## Cấu trúc thư mục mục tiêu

```
RAG_v2/
├── agent/
│   ├── __init__.py               ← Cập nhật exports
│   ├── state.py                  ✅ DONE (Tuần 1)
│   ├── tools.py                  ✅ DONE (Tuần 1)
│   ├── tool_adapters.py          ✅ DONE (Tuần 1)
│   ├── prompts.py                ✅ DONE (Tuần 1)
│   ├── complexity_router.py      ✅ DONE (Tuần 1)
│   ├── graph_state.py            ← MỚI (Tuần 2*)
│   ├── lc_tools.py               ← MỚI (Tuần 2*)
│   └── react_agent.py            ← VIẾT LẠI (Tuần 2*)
├── pipeline/
│   ├── rag_pipeline.py           ← Sửa Tuần 3
│   └── mongo_logger.py           ← Sửa Tuần 4
├── tests/
│   ├── test_adapters.py          ✅ DONE (Tuần 1)
│   ├── test_agent_langgraph.py   ← VIẾT MỚI (Tuần 2*, thay test_agent_mock.py)
│   ├── test_router.py            ← Tuần 3
│   └── test_e2e.py               ← Tuần 3
├── eval/
│   ├── question_sets/
│   │   ├── simple_questions.json
│   │   └── complex_questions.json
│   └── evaluate.py
└── config/
    └── settings.py               ← Sửa Tuần 3
```

## Kiến trúc LangGraph

```
Query
  │
  ▼
ComplexityRouter ──────────────────────────────────┐
  │ "complex"                                      │ "simple" / "chitchat"
  ▼                                                ▼
ReActAgent.run()                        RAG v2 pipeline / chitchat handler
  │
  ▼
LangGraph StateGraph
  │
  ├── START
  │     │
  │     ▼
  ├── agent_node  ←─────────────────────────────┐
  │     │ (LLM + bind_tools)                    │
  │     ▼                                       │
  │  _should_continue()                         │
  │     ├── "tools"      ──► tools_node ────────┘
  │     ├── "synthesize" ──► synthesize_node ──► END
  │     └── "end"        ──► extract_answer_node ► END
  │
  ▼
AgentState (dataclass)  ──► MongoDB logging
  │
  ▼
final_answer → caller (pipeline / API)
```

---

# TUẦN 1 — ✅ DONE

> **Deliverables đã hoàn thành:**
> - `agent/state.py`, `agent/tools.py`, `agent/tool_adapters.py`, `agent/prompts.py`, `agent/complexity_router.py`
> - `tests/test_adapters.py` — tất cả pass
> - `execute_tool("rag_search", {...})` trả về kết quả thực từ Qdrant

---

# TUẦN 2* — LangGraph Migration Sprint

**Mục tiêu**: Thay thế custom ReAct loop bằng LangGraph `StateGraph`. Public API của `ReActAgent.run()` giữ nguyên — pipeline cũ không cần sửa.

---

## Bước 0 — Cài đặt dependencies

```bash
pip install langgraph langchain-core langchain-openai

# Verify
python -c "from langgraph.graph import StateGraph; from langchain_openai import ChatOpenAI; print('OK')"
```

---

## Ngày 1 — `agent/graph_state.py` *(file mới)*

### Nhiệm vụ
`AgentGraphState` là TypedDict dùng riêng trong LangGraph graph — **khác** với `AgentState` (dataclass) dùng để log MongoDB. Cần tách biệt để không couple hai layer.

### Code

```python
# agent/graph_state.py
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentGraphState(TypedDict):
    """
    LangGraph runtime state — dùng trong graph nodes.
    Khác với AgentState (dataclass) dùng để log MongoDB.

    add_messages reducer: tự động append/merge messages thay vì overwrite.
    """
    messages: Annotated[list, add_messages]
    query: str
    session_id: str
    tool_call_history: list[str]   # track tools đã gọi để phát hiện loop
    iteration: int
    max_iterations: int
    final_answer: str | None
    error: str | None
```

### Checklist
- [ ] `python -c "from agent.graph_state import AgentGraphState; print('OK')`
- [ ] Không có external dependency ngoài langgraph

---

## Ngày 2 — `agent/lc_tools.py` *(file mới)*

### Nhiệm vụ
Wrap `execute_tool` thành LangChain `StructuredTool`. LangGraph cần format này để `llm.bind_tools()` và `ToolNode` hoạt động. Pydantic schemas đảm bảo validation trước khi gọi adapter.

### Lý do cần file này
- `TOOL_DEFINITIONS` (tools.py) là OpenAI JSON format → dùng cho spec/documentation
- `LANGGRAPH_TOOLS` (lc_tools.py) là LangChain StructuredTool → dùng cho runtime execution
- Không xóa `tools.py` vì vẫn cần cho backward compatibility và logging

### Code

```python
# agent/lc_tools.py
from __future__ import annotations

import logging
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .tool_adapters import execute_tool

logger = logging.getLogger(__name__)

# ─── Pydantic schemas ────────────────────────────────────────────────

CollectionName = Literal["quy_dinh", "chuong_trinh", "ke_hoach", "thong_bao"]
CurriculumCollection = Literal["quy_dinh", "chuong_trinh"]


class RagSearchInput(BaseModel):
    query: str = Field(description="Câu truy vấn tìm kiếm, viết ngắn gọn và cụ thể")
    collection: CollectionName = Field(description="Collection cần tìm kiếm")


class QueryItem(BaseModel):
    query: str
    collection: CollectionName


class MultiRagSearchInput(BaseModel):
    queries: list[QueryItem] = Field(
        min_length=2, max_length=4,
        description="Danh sách query, mỗi query 1 collection"
    )


class CompareCohortsInput(BaseModel):
    topic: str = Field(description="Chủ đề so sánh, vd: học bổng KKHT")
    cohort_a: str = Field(description="Khóa thứ nhất, vd: K65")
    cohort_b: str = Field(description="Khóa thứ hai, vd: K70")
    collection: CurriculumCollection = Field(description="Collection chứa thông tin cần so sánh")


class WebSearchInput(BaseModel):
    query: str = Field(description="Câu truy vấn web, kèm tên trường để chính xác hơn")


class ClarifyInput(BaseModel):
    message: str = Field(description="Câu hỏi làm rõ, ngắn gọn")
    options: list[str] = Field(max_length=3, description="2-3 lựa chọn gợi ý")


# ─── Adapter functions ───────────────────────────────────────────────
# Nhận Pydantic objects từ LangChain, chuyển về dict cho execute_tool

def _rag_search(query: str, collection: str) -> str:
    return execute_tool("rag_search", {"query": query, "collection": collection})


def _multi_rag_search(queries: list[QueryItem]) -> str:
    # LangChain parse thành Pydantic objects — convert về dict
    queries_dicts = [
        q.model_dump() if hasattr(q, "model_dump") else dict(q)
        for q in queries
    ]
    return execute_tool("multi_rag_search", {"queries": queries_dicts})


def _compare_cohorts(topic: str, cohort_a: str, cohort_b: str, collection: str) -> str:
    return execute_tool("compare_cohorts", {
        "topic": topic, "cohort_a": cohort_a,
        "cohort_b": cohort_b, "collection": collection,
    })


def _web_search(query: str) -> str:
    return execute_tool("web_search", {"query": query})


def _clarify_question(message: str, options: list[str]) -> str:
    return execute_tool("clarify_question", {"message": message, "options": options})


# ─── LangChain StructuredTools ────────────────────────────────────────

LANGGRAPH_TOOLS = [
    StructuredTool.from_function(
        func=_rag_search,
        name="rag_search",
        description=(
            "Tìm kiếm thông tin trong database trường. Chọn đúng collection: "
            "quy_dinh (quy định học vụ, học bổng, điều kiện tốt nghiệp, kỷ luật); "
            "chuong_trinh (môn học, tín chỉ, chương trình đào tạo); "
            "ke_hoach (lịch thi, kế hoạch học kỳ, ngày nghỉ); "
            "thong_bao (thông báo mới, tin tức, sự kiện sắp tới)"
        ),
        args_schema=RagSearchInput,
    ),
    StructuredTool.from_function(
        func=_multi_rag_search,
        name="multi_rag_search",
        description=(
            "Tìm đồng thời nhiều collection cho câu hỏi cần thông tin từ ≥2 nguồn. "
            "Ví dụ: 'Đủ điều kiện tốt nghiệp chưa?' cần cả quy_dinh lẫn chuong_trinh."
        ),
        args_schema=MultiRagSearchInput,
    ),
    StructuredTool.from_function(
        func=_compare_cohorts,
        name="compare_cohorts",
        description=(
            "So sánh quy định hoặc chương trình đào tạo giữa 2 khóa sinh viên. "
            "Dùng khi câu hỏi đề cập 2 khóa khác nhau (K65, K66, K70...)."
        ),
        args_schema=CompareCohortsInput,
    ),
    StructuredTool.from_function(
        func=_web_search,
        name="web_search",
        description=(
            "Tìm thông tin mới nhất trên internet qua Tavily. "
            "Chỉ dùng khi database không có kết quả hoặc cần thông tin rất mới."
        ),
        args_schema=WebSearchInput,
    ),
    StructuredTool.from_function(
        func=_clarify_question,
        name="clarify_question",
        description=(
            "Hỏi lại người dùng khi câu hỏi quá mơ hồ không thể tìm kiếm. "
            "Tối đa 1 lần trong cuộc hội thoại."
        ),
        args_schema=ClarifyInput,
    ),
]

# Map để lookup nhanh trong tools_node
TOOL_MAP: dict[str, StructuredTool] = {t.name: t for t in LANGGRAPH_TOOLS}
```

### Checklist
- [ ] `python -c "from agent.lc_tools import LANGGRAPH_TOOLS; print(len(LANGGRAPH_TOOLS))"` → ra `5`
- [ ] `python -c "from agent.lc_tools import TOOL_MAP; print(list(TOOL_MAP.keys()))"` → 5 tên tool
- [ ] Không import lỗi

---

## Ngày 3-4 — `agent/react_agent.py` *(viết lại toàn bộ)*

### Nhiệm vụ
Thay thế custom while loop bằng LangGraph `StateGraph`. **Public API `run()` giữ nguyên** — trả về `AgentState` dataclass như cũ.

### Mapping node → logic cũ

| LangGraph Node | Logic cũ tương đương |
|---|---|
| `agent_node` | `_get_next_action()` |
| `tools_node` | `execute_tool()` call + message append |
| `synthesize_node` | `_synthesize()` fallback |
| `extract_answer_node` | Extract `msg.content` khi final answer |
| `_should_continue()` | Guard conditions trong while loop |

### Code

```python
# agent/react_agent.py
from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from .graph_state import AgentGraphState
from .lc_tools import LANGGRAPH_TOOLS, TOOL_MAP
from .prompts import AGENT_SYSTEM_PROMPT, SYNTHESIS_PROMPT
from .state import AgentState, ToolResult

logger = logging.getLogger(__name__)


class ReActAgent:
    """
    LangGraph-based ReAct Agent.
    Public API giống hệt phiên bản custom — pipeline cũ không cần thay đổi.
    """

    def __init__(self, settings: Any) -> None:
        lm_studio_url = (
            getattr(settings, "lm_studio_url", None)
            or getattr(settings, "lm_studio_base_url", "http://localhost:1234/v1")
        )
        self.model_name = getattr(
            settings, "agent_model",
            getattr(settings, "chat_model", "qwen2.5-8b-instruct"),
        )
        self.max_iterations = int(getattr(settings, "agent_max_iterations", 4))

        # LLM có bind tools — dùng trong agent_node
        self._llm = ChatOpenAI(
            base_url=lm_studio_url,
            api_key="lm-studio",
            model=self.model_name,
            temperature=0.1,
            max_tokens=800,
            timeout=30,
        )
        self._llm_with_tools = self._llm.bind_tools(LANGGRAPH_TOOLS)

        # LLM không tools — dùng trong synthesize_node
        self._synthesis_llm = ChatOpenAI(
            base_url=lm_studio_url,
            api_key="lm-studio",
            model=self.model_name,
            temperature=0.2,
            max_tokens=600,
            timeout=30,
        )

        self._graph = self._build_graph()
        logger.info("[Agent] LangGraph graph compiled with %d tools", len(LANGGRAPH_TOOLS))

    # ─── Public API ──────────────────────────────────────────────────

    def run(self, query: str, session_id: str = "") -> AgentState:
        """
        Main entry point. Trả về AgentState để caller log MongoDB.
        Interface giống hoàn toàn với phiên bản custom ReAct.
        """
        initial_state: AgentGraphState = {
            "messages": [
                SystemMessage(content=AGENT_SYSTEM_PROMPT),
                HumanMessage(content=query),
            ],
            "query": query,
            "session_id": session_id,
            "tool_call_history": [],
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "final_answer": None,
            "error": None,
        }

        logger.info("[Agent] Starting for query: '%s...'", query[:80])

        try:
            result = self._graph.invoke(initial_state)
        except Exception as exc:
            logger.error("[Agent] Graph execution failed: %s", exc, exc_info=True)
            return self._make_error_state(query, session_id, str(exc))

        return self._to_agent_state(result, query, session_id)

    # ─── Graph nodes ─────────────────────────────────────────────────

    def _agent_node(self, state: AgentGraphState) -> dict:
        """Gọi LLM với tools bound để quyết định hành động tiếp theo."""
        new_iteration = state["iteration"] + 1
        logger.info("[Agent] Iteration %d/%d", new_iteration, state["max_iterations"])

        try:
            response = self._llm_with_tools.invoke(state["messages"])
        except Exception as exc:
            logger.error("[Agent] LLM call failed: %s", exc)
            return {"messages": [], "iteration": new_iteration, "error": str(exc)}

        return {"messages": [response], "iteration": new_iteration}

    def _tools_node(self, state: AgentGraphState) -> dict:
        """
        Thực thi tất cả tool calls trong AIMessage cuối cùng.
        Trả về ToolMessages và cập nhật tool_call_history.
        """
        messages = state["messages"]
        last_ai: AIMessage = messages[-1]

        tool_messages: list[ToolMessage] = []
        new_history = list(state.get("tool_call_history", []))

        for tc in last_ai.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            logger.info("[Agent] Calling tool: %s(%s)", tool_name, tool_args)

            lc_tool = TOOL_MAP.get(tool_name)
            if lc_tool is None:
                result = f"[Lỗi hệ thống: Tool '{tool_name}' không tồn tại]"
            else:
                try:
                    result = lc_tool.invoke(tool_args)
                except Exception as exc:
                    logger.error("[Agent] Tool %s failed: %s", tool_name, exc)
                    result = f"[Lỗi khi tìm kiếm: {exc}]"

            tool_messages.append(
                ToolMessage(
                    content=str(result)[:2000],  # cắt bớt cho Qwen 8B context window
                    tool_call_id=tc["id"],
                    name=tool_name,
                )
            )
            new_history.append(tool_name)

        return {
            "messages": tool_messages,
            "tool_call_history": new_history,
        }

    def _synthesize_node(self, state: AgentGraphState) -> dict:
        """
        Fallback synthesis — gọi khi hết iterations hoặc phát hiện loop.
        Tổng hợp từ ToolMessages đã có trong history.
        """
        logger.warning("[Agent] Forced synthesis after %d iterations", state["iteration"])

        # Ưu tiên: nếu clarify_question là tool cuối, relay kết quả của nó
        history = state.get("tool_call_history", [])
        if history and history[-1] == "clarify_question":
            for msg in reversed(state["messages"]):
                if isinstance(msg, ToolMessage) and msg.name == "clarify_question":
                    return {"final_answer": str(msg.content).replace("[CLARIFY]\n", "", 1)}

        # Collect tool results từ message history
        tool_contents: list[str] = []
        for msg in state["messages"]:
            if isinstance(msg, ToolMessage) and msg.content:
                label = f"[{msg.name}]" if msg.name else "[tool]"
                tool_contents.append(f"{label}\n{msg.content}")

        if not tool_contents:
            return {
                "final_answer": (
                    "Xin lỗi, tôi không tìm thấy thông tin phù hợp với câu hỏi của bạn. "
                    "Vui lòng liên hệ Phòng Đào tạo để được hỗ trợ."
                )
            }

        context = "\n\n---\n\n".join(tool_contents)
        try:
            response = self._synthesis_llm.invoke([
                SystemMessage(content=SYNTHESIS_PROMPT),
                HumanMessage(
                    content=f"Câu hỏi: {state['query']}\n\nThông tin tìm được:\n{context}"
                ),
            ])
            answer = response.content or "Tôi không tìm thấy thông tin về vấn đề này."
        except Exception as exc:
            logger.error("[Agent] Synthesis LLM failed: %s", exc)
            answer = f"Thông tin tìm được:\n{tool_contents[0][:500]}"

        return {"final_answer": answer}

    def _extract_answer_node(self, state: AgentGraphState) -> dict:
        """
        Trích xuất final answer khi LLM trả lời trực tiếp (không dùng tool).
        """
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                return {"final_answer": str(msg.content)}
        return {"final_answer": None}

    # ─── Conditional edge ────────────────────────────────────────────

    def _should_continue(
        self, state: AgentGraphState
    ) -> Literal["tools", "synthesize", "end"]:
        """
        Routing sau mỗi agent_node call.

        Logic:
          - error xảy ra                           → "synthesize"
          - LLM không gọi tool (text answer)       → "end"
          - Hết max_iterations                     → "synthesize"
          - Loop: cùng tool gọi 2 lần              → "synthesize"
          - Tool call hợp lệ                       → "tools"
        """
        if state.get("error"):
            return "synthesize"

        messages = state["messages"]
        last = messages[-1] if messages else None

        if not isinstance(last, AIMessage) or not getattr(last, "tool_calls", None):
            # LLM đưa ra câu trả lời text trực tiếp → done
            return "end"

        # Kiểm tra iteration limit
        if state["iteration"] >= state["max_iterations"]:
            logger.warning("[Agent] Max iterations %d reached", state["max_iterations"])
            return "synthesize"

        # Loop detection: tool đã gọi rồi (trừ clarify_question)
        tool_name = last.tool_calls[0]["name"]
        history = state.get("tool_call_history", [])
        if tool_name in history and tool_name != "clarify_question":
            logger.warning("[Agent] Loop detected — tool '%s' called twice", tool_name)
            return "synthesize"

        return "tools"

    # ─── Graph construction ──────────────────────────────────────────

    def _build_graph(self):
        graph = StateGraph(AgentGraphState)

        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tools_node)
        graph.add_node("synthesize", self._synthesize_node)
        graph.add_node("extract_answer", self._extract_answer_node)

        graph.add_edge(START, "agent")
        graph.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "tools": "tools",
                "synthesize": "synthesize",
                "end": "extract_answer",
            },
        )
        graph.add_edge("tools", "agent")
        graph.add_edge("synthesize", END)
        graph.add_edge("extract_answer", END)

        return graph.compile()

    # ─── State conversion ─────────────────────────────────────────────

    def _to_agent_state(
        self,
        graph_result: AgentGraphState,
        query: str,
        session_id: str,
    ) -> AgentState:
        """
        Chuyển AgentGraphState (LangGraph) → AgentState (dataclass) để log MongoDB.
        Giữ nguyên interface với pipeline cũ.
        """
        state = AgentState(query=query, session_id=session_id)
        state.iteration = graph_result.get("iteration", 0)
        state.tool_call_history = list(graph_result.get("tool_call_history", []))
        state.final_answer = graph_result.get("final_answer")
        state.error = graph_result.get("error")

        # Rebuild ToolResult list từ message history
        messages = graph_result.get("messages", [])

        # Map tool_call_id → (name, args) từ AIMessages
        call_meta: dict[str, dict] = {}
        for msg in messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    call_meta[tc["id"]] = {"name": tc["name"], "args": tc["args"]}

        # Build ToolResult từ ToolMessages
        iter_counter = 0
        for msg in messages:
            if isinstance(msg, ToolMessage):
                meta = call_meta.get(msg.tool_call_id or "", {})
                tr = ToolResult(
                    tool_name=meta.get("name") or getattr(msg, "name", "unknown"),
                    args=meta.get("args", {}),
                    result=str(msg.content),
                    iteration=iter_counter,
                )
                state.tool_results.append(tr)
                iter_counter += 1

        return state

    def _make_error_state(self, query: str, session_id: str, error_msg: str) -> AgentState:
        state = AgentState(query=query, session_id=session_id)
        state.error = error_msg
        state.final_answer = (
            "Xin lỗi, có lỗi xảy ra trong quá trình xử lý. "
            "Vui lòng thử lại hoặc liên hệ Phòng Đào tạo để được hỗ trợ."
        )
        return state
```

### Checklist Ngày 3-4
- [ ] `from agent.react_agent import ReActAgent` không lỗi
- [ ] Visualize graph (không cần LM Studio):
  ```python
  from agent.react_agent import ReActAgent
  from unittest.mock import MagicMock
  s = MagicMock()
  s.lm_studio_url = "http://localhost:1234/v1"
  s.agent_model = "qwen2.5-8b-instruct"
  s.agent_max_iterations = 4
  agent = ReActAgent(s)
  print(agent._graph.get_graph().draw_ascii())
  ```
- [ ] Graph có đủ 4 nodes: agent, tools, synthesize, extract_answer
- [ ] Edges đúng: agent→tools→agent (loop), agent→synthesize→END, agent→extract_answer→END

---

## Cập nhật `agent/__init__.py`

```python
# agent/__init__.py
"""Agent module — LangGraph-based Agentic RAG orchestration."""

from .complexity_router import ComplexityRouter
from .graph_state import AgentGraphState
from .lc_tools import LANGGRAPH_TOOLS, TOOL_MAP
from .react_agent import ReActAgent
from .state import AgentState, ToolResult
from .tool_adapters import execute_tool
from .tools import (
    TOOL_DEFINITIONS,
    TOOL_NAMES,
    AgentTool,
    ToolRegistry,
    build_default_tool_declarations,
)

__all__ = [
    # State
    "AgentState",
    "ToolResult",
    "AgentGraphState",
    # Tools
    "AgentTool",
    "ToolRegistry",
    "TOOL_DEFINITIONS",
    "TOOL_NAMES",
    "LANGGRAPH_TOOLS",
    "TOOL_MAP",
    "build_default_tool_declarations",
    # Execution
    "execute_tool",
    # Agent
    "ComplexityRouter",
    "ReActAgent",
]
```

---

## Ngày 5 — `tests/test_agent_langgraph.py`

### Nhiệm vụ
Viết lại test mock cho LangGraph agent. Patch target thay đổi từ `openai.OpenAI` → `agent.react_agent.ChatOpenAI`.

### Code

```python
# tests/test_agent_langgraph.py
"""
Test LangGraph ReActAgent với mock — không cần LM Studio running.
Chạy: pytest tests/test_agent_langgraph.py -v
"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, ToolMessage

from agent.react_agent import ReActAgent
from agent.state import AgentState


def make_settings(max_iterations: int = 4) -> MagicMock:
    s = MagicMock()
    s.lm_studio_url = "http://localhost:1234/v1"
    s.agent_model = "qwen2.5-8b-instruct"
    s.agent_max_iterations = max_iterations
    return s


def make_ai_with_tool(tool_name: str, args: dict, call_id: str = "tc_001") -> AIMessage:
    """Tạo AIMessage giả lập Qwen gọi tool."""
    return AIMessage(
        content="",
        tool_calls=[{
            "id": call_id,
            "name": tool_name,
            "args": args,
            "type": "tool_call",
        }],
    )


def make_ai_answer(content: str) -> AIMessage:
    """Tạo AIMessage giả lập Qwen trả lời trực tiếp (không dùng tool)."""
    return AIMessage(content=content, tool_calls=[])


PATCH_CHAT = "agent.react_agent.ChatOpenAI"


class TestSimpleFlow:

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_one_tool_then_answer(self, mock_chat_cls, mock_execute):
        """Agent gọi 1 tool → nhận kết quả → trả lời trực tiếp."""
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool("rag_search", {"query": "học bổng KKHT", "collection": "quy_dinh"}),
            make_ai_answer("Học bổng KKHT yêu cầu GPA ≥ 3.2 và không có môn F."),
        ]
        mock_execute.return_value = "GPA ≥ 3.2, không có môn F, không bị kỷ luật."

        agent = ReActAgent(make_settings())
        state = agent.run("Điều kiện học bổng KKHT là gì?")

        assert state.final_answer is not None
        assert "rag_search" in state.tool_call_history
        assert state.error is None
        assert state.iteration == 2
        assert len(state.tool_results) == 1
        assert state.tool_results[0].tool_name == "rag_search"

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_direct_answer_no_tool(self, mock_chat_cls, mock_execute):
        """Agent trả lời trực tiếp không cần gọi tool."""
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer("Xin chào! Tôi có thể giúp gì cho bạn?")

        agent = ReActAgent(make_settings())
        state = agent.run("Xin chào")

        assert state.final_answer is not None
        assert len(state.tool_call_history) == 0
        mock_execute.assert_not_called()


class TestComplexFlow:

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_compare_cohorts_flow(self, mock_chat_cls, mock_execute):
        """Agent gọi compare_cohorts cho câu hỏi so sánh 2 khóa."""
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool("compare_cohorts", {
                "topic": "học bổng KKHT",
                "cohort_a": "K65", "cohort_b": "K70",
                "collection": "quy_dinh",
            }, call_id="tc_002"),
            make_ai_answer("K65 yêu cầu GPA ≥ 3.2, K70 yêu cầu GPA ≥ 3.5."),
        ]
        mock_execute.return_value = "### K65\nGPA ≥ 3.2\n---\n### K70\nGPA ≥ 3.5"

        agent = ReActAgent(make_settings())
        state = agent.run("So sánh học bổng KKHT giữa K65 và K70")

        assert "compare_cohorts" in state.tool_call_history
        assert state.final_answer is not None
        assert state.error is None

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_multi_rag_search_flow(self, mock_chat_cls, mock_execute):
        """Agent gọi multi_rag_search cho câu hỏi đa nguồn."""
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool("multi_rag_search", {
                "queries": [
                    {"query": "điều kiện tốt nghiệp", "collection": "quy_dinh"},
                    {"query": "tín chỉ tích lũy", "collection": "chuong_trinh"},
                ]
            }, call_id="tc_003"),
            make_ai_answer("Bạn cần đủ 130 tín chỉ và không có môn F để tốt nghiệp."),
        ]
        mock_execute.return_value = "Điều kiện: ≥130 tín chỉ, GPA ≥ 2.0, không nợ môn."

        agent = ReActAgent(make_settings())
        state = agent.run("Tôi đủ điều kiện tốt nghiệp chưa?")

        assert "multi_rag_search" in state.tool_call_history
        assert state.final_answer is not None


class TestSafetyMechanisms:

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_loop_detection_triggers_synthesis(self, mock_chat_cls, mock_execute):
        """
        Khi LLM gọi cùng tool 2 lần, _should_continue phát hiện loop
        và chuyển sang synthesize thay vì tiếp tục gọi.
        """
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        tool_call = make_ai_with_tool("rag_search", {"query": "test", "collection": "quy_dinh"})
        synthesis_answer = AIMessage(content="Tổng hợp: kết quả test.")

        mock_llm.invoke.side_effect = [
            tool_call,           # agent_node lần 1 → OK → vào tools_node
            tool_call,           # agent_node lần 2 → loop detected → synthesize_node
            synthesis_answer,    # synthesis_llm.invoke
        ]
        mock_execute.return_value = "Kết quả test."

        agent = ReActAgent(make_settings(max_iterations=4))
        state = agent.run("Test query")

        assert state.final_answer is not None
        # rag_search chỉ execute 1 lần (lần 2 bị chặn trước tools_node)
        assert state.tool_call_history.count("rag_search") == 1

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_max_iterations_triggers_synthesis(self, mock_chat_cls, mock_execute):
        """Hết max_iterations → synthesize, không crash, có final answer."""
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool("rag_search", {"query": "q1", "collection": "quy_dinh"}, "tc_1"),
            make_ai_with_tool("web_search", {"query": "q2"}, "tc_2"),
            # Sau iteration 2 → max reached → synthesize_node
            AIMessage(content="Tổng hợp từ kết quả tìm kiếm."),
        ]
        mock_execute.return_value = "Kết quả mock."

        agent = ReActAgent(make_settings(max_iterations=2))
        state = agent.run("Câu hỏi phức tạp")

        assert state.final_answer is not None
        assert state.iteration <= 2

    @patch(PATCH_CHAT)
    def test_llm_connection_error_returns_graceful_state(self, mock_chat_cls):
        """LM Studio tắt → agent không crash, trả về state có final_answer."""
        from openai import APIConnectionError

        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = APIConnectionError(request=MagicMock())

        agent = ReActAgent(make_settings())
        state = agent.run("Test khi LM Studio tắt")

        # Không raise exception
        assert state.final_answer is not None or state.error is not None


class TestStateConversion:

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_tool_results_logged_correctly(self, mock_chat_cls, mock_execute):
        """AgentState.tool_results được build đúng từ message history."""
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool("rag_search", {"query": "học bổng", "collection": "quy_dinh"}),
            make_ai_answer("GPA ≥ 3.2."),
        ]
        mock_execute.return_value = "Nội dung học bổng KKHT."

        agent = ReActAgent(make_settings())
        state = agent.run("Học bổng KKHT?")

        assert len(state.tool_results) == 1
        tr = state.tool_results[0]
        assert tr.tool_name == "rag_search"
        assert tr.args == {"query": "học bổng", "collection": "quy_dinh"}
        assert "Nội dung học bổng" in tr.result

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_to_log_dict_serializable(self, mock_chat_cls, mock_execute):
        """AgentState.to_log_dict() phải JSON-serializable cho MongoDB."""
        import json

        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer("Câu trả lời.")

        agent = ReActAgent(make_settings())
        state = agent.run("Test serialization")

        log_dict = state.to_log_dict()
        json_str = json.dumps(log_dict, ensure_ascii=False)
        assert len(json_str) > 0
```

### Chạy test

```bash
# Unit tests — không cần LM Studio
pytest tests/test_agent_langgraph.py -v

# Regression check — adapters vẫn hoạt động
pytest tests/test_adapters.py -v -m "not integration"

# Full test suite
pytest tests/ -v -m "not integration and not e2e"
```

### Checklist Ngày 5 (Tuần 2*)
- [ ] `pytest tests/test_agent_langgraph.py -v` — tất cả pass
- [ ] `pytest tests/test_adapters.py -v -m "not integration"` — vẫn pass (không regression)
- [ ] Prompt tune với Qwen thực: accuracy ≥ 8/10

### Bộ câu hỏi tune prompt (giữ nguyên từ plan cũ)

```python
# tests/prompt_tune_questions.py
TUNE_QUESTIONS = [
    ("Điều kiện xét học bổng KKHT học kỳ này là gì?",         "rag_search",       "quy_dinh"),
    ("K70 ngành CNTT phải học bao nhiêu tín chỉ để tốt nghiệp?", "rag_search",    "chuong_trinh"),
    ("Lịch thi học kỳ 1 năm học 2024-2025 khi nào?",           "rag_search",       "ke_hoach"),
    ("So sánh điều kiện nhận học bổng KKHT giữa K65 và K70",   "compare_cohorts",  None),
    ("Tôi đã học đủ tín chỉ và không có môn F, đủ điều kiện tốt nghiệp chưa?", "multi_rag_search", None),
    ("Có thông báo gì mới từ nhà trường không?",               "rag_search",       "thong_bao"),
    ("Học bổng",                                               "clarify_question", None),
    ("Môn Toán cao cấp 1 có mã môn là gì và bao nhiêu tín chỉ?", "rag_search",    "chuong_trinh"),
    ("Quy định về số lần thi lại tối đa là bao nhiêu?",         "rag_search",       "quy_dinh"),
    ("Chương trình đào tạo K70 và K68 khác nhau những gì?",    "compare_cohorts",  None),
]
```

### Deliverable cuối Tuần 2*
> ✅ `agent/graph_state.py` + `agent/lc_tools.py` + `agent/react_agent.py` (LangGraph)  
> ✅ `tests/test_agent_langgraph.py` — tất cả pass  
> ✅ Không regression với `test_adapters.py`  
> ✅ Graph visualize đúng 4 nodes + conditional edges  
> ✅ Prompt tune accuracy ≥ 80%

---

# TUẦN 3 — Integration: Router · Pipeline · E2E

**Mục tiêu**: Hệ thống end-to-end hoàn chỉnh. Câu đơn giản → pipeline cũ, câu phức tạp → LangGraph agent.

---

## Ngày 1 — Test Router

### `tests/test_router.py`

```python
# tests/test_router.py
import pytest
from agent.complexity_router import ComplexityRouter

router = ComplexityRouter()

class TestChitchat:
    def test_greeting(self):
        assert router.route("xin chào") == "chitchat"
        assert router.route("Hello bạn") == "chitchat"
    def test_thanks(self):
        assert router.route("cảm ơn bạn") == "chitchat"
    def test_ok(self):
        assert router.route("ok") == "chitchat"

class TestSimple:
    def test_policy_question(self):
        assert router.route("Điều kiện xét học bổng KKHT là gì?") == "simple"
    def test_course_question(self):
        assert router.route("Môn Toán cao cấp 1 có bao nhiêu tín chỉ?") == "simple"
    def test_schedule_question(self):
        assert router.route("Lịch thi học kỳ 1 khi nào?") == "simple"

class TestComplex:
    def test_cohort_comparison(self):
        assert router.route("So sánh học bổng giữa K65 và K70") == "complex"
    def test_two_cohorts_mentioned(self):
        assert router.route("K65 và K70 có quy định học bổng khác nhau không?") == "complex"
    def test_graduation_condition(self):
        assert router.route("Tôi đủ điều kiện tốt nghiệp chưa?") == "complex"
    def test_ambiguous_short(self):
        assert router.route("học bổng") == "complex"
    def test_long_query(self):
        long_q = "Sinh viên khóa K70 ngành Khoa học Máy tính học theo chương trình đào tạo mới có cần đáp ứng thêm yêu cầu nào so với khóa K67 không?"
        assert router.route(long_q) == "complex"
```

### Checklist Ngày 1
- [ ] `pytest tests/test_router.py -v` — tất cả pass
- [ ] Thêm 5 câu hỏi thực tế từ use case trường → test thêm

---

## Ngày 2-3 — Tích hợp `rag_pipeline.py` + `settings.py`

### `config/settings.py` — Thêm agent settings

```python
# Thêm vào class Settings hiện tại:
agent_enabled: bool = True
agent_max_iterations: int = 4
agent_model: str = "qwen2.5-8b-instruct"
lm_studio_url: str = "http://localhost:1234/v1"
```

### `pipeline/rag_pipeline.py` — Thêm `query_v3()`, giữ nguyên `query()`

```python
# pipeline/rag_pipeline.py — CHỈ thêm các phần sau

from agent.complexity_router import ComplexityRouter
from agent.react_agent import ReActAgent

class RAGPipeline:

    def __init__(self, settings):
        # ... code __init__ hiện tại ...

        # Thêm mới:
        self.complexity_router = ComplexityRouter()
        self.agent = ReActAgent(settings) if settings.agent_enabled else None
        logger.info(f"Agent mode: {'enabled (LangGraph)' if self.agent else 'disabled'}")

    def query_v3(self, user_query: str, session_id: str = "") -> dict:
        """
        Entry point mới — routing thông minh.
        query() cũ vẫn giữ nguyên cho backward compatibility.
        """
        route = self.complexity_router.route(user_query)

        if route == "chitchat":
            return {
                "answer": self._handle_chitchat(user_query),
                "mode": "chitchat",
                "route": "chitchat",
            }

        if route == "simple" or self.agent is None:
            result = self.query(user_query)  # gọi pipeline cũ
            result["mode"] = "rag_v2"
            result["route"] = route
            return result

        # Complex → LangGraph Agent
        state = self.agent.run(user_query, session_id=session_id)

        if hasattr(self, "mongo_logger") and self.mongo_logger:
            self.mongo_logger.log_agent_trace(session_id, state.to_log_dict())

        if state.error and not state.final_answer:
            logger.warning(f"Agent failed ({state.error}), falling back to RAG v2")
            result = self.query(user_query)
            result["mode"] = "rag_v2_fallback"
            return result

        return {
            "answer": state.final_answer,
            "mode": "agent",
            "route": "complex",
            "tools_used": state.tool_call_history,
            "iterations": state.iteration,
        }

    def _handle_chitchat(self, query: str) -> str:
        # ⚠️ Điều chỉnh theo chitchat implementation hiện tại
        return "Xin chào! Tôi là trợ lý tư vấn học vụ ĐHBK. Bạn cần hỗ trợ gì?"
```

### Thêm API endpoint mới

```python
# api/routes/chat.py — thêm endpoint, giữ endpoint cũ

@router.post("/api/chat/v3")
async def chat_v3(request: ChatRequest):
    mode = getattr(request, "mode", "auto")

    if mode == "rag":
        result = pipeline.query(request.message)
    elif mode == "agent":
        state = pipeline.agent.run(request.message, session_id=request.session_id)
        result = {"answer": state.final_answer, "mode": "agent"}
    else:
        result = pipeline.query_v3(request.message, session_id=request.session_id)

    return result
```

### Checklist Ngày 2-3
- [ ] `query_v3()` được thêm, `query()` cũ không đổi
- [ ] Return format nhất quán (có `mode`, `route`, `tools_used`)
- [ ] Fallback về RAG v2 khi agent thất bại

---

## Ngày 4-5 — End-to-End Test

### `tests/test_e2e.py`

```python
# tests/test_e2e.py
"""
End-to-end test — cần Qdrant + LM Studio running.
Chạy: pytest tests/test_e2e.py -v -m e2e
"""
import pytest
from pipeline.rag_pipeline import RAGPipeline
from config.settings import Settings

@pytest.fixture(scope="module")
def pipeline():
    return RAGPipeline(Settings())

@pytest.mark.e2e
class TestRouting:

    def test_chitchat_routed_correctly(self, pipeline):
        result = pipeline.query_v3("xin chào")
        assert result["mode"] == "chitchat"
        assert result["answer"] is not None

    def test_simple_uses_rag_pipeline(self, pipeline):
        result = pipeline.query_v3("Điều kiện xét học bổng KKHT là gì?")
        assert result["mode"] == "rag_v2"
        assert result["answer"] is not None

    def test_complex_uses_agent(self, pipeline):
        result = pipeline.query_v3("So sánh học bổng KKHT giữa K65 và K70")
        assert result["mode"] == "agent"
        assert result["answer"] is not None
        assert len(result.get("tools_used", [])) > 0

    def test_graduation_uses_multi_rag(self, pipeline):
        result = pipeline.query_v3("Tôi đủ điều kiện tốt nghiệp chưa?")
        assert result["mode"] == "agent"
        assert "multi_rag_search" in result.get("tools_used", [])

    def test_agent_fallback_on_failure(self, pipeline):
        import unittest.mock as mock
        with mock.patch.object(pipeline.agent, "run", side_effect=Exception("Connection refused")):
            result = pipeline.query_v3("So sánh K65 và K70")
            assert result["answer"] is not None

@pytest.mark.e2e
class TestAnswerQuality:

    def test_answer_not_empty(self, pipeline):
        result = pipeline.query_v3("Điều kiện xét học bổng KKHT?")
        assert len(result["answer"]) > 50

    def test_answer_in_vietnamese(self, pipeline):
        result = pipeline.query_v3("Lịch thi học kỳ 1 khi nào?")
        vietnamese_chars = set("àáâãèéêìíòóôõùúăđ")
        assert any(c in result["answer"].lower() for c in vietnamese_chars)

    def test_comparison_mentions_both_cohorts(self, pipeline):
        result = pipeline.query_v3("So sánh học bổng KKHT K65 và K70")
        answer_lower = result["answer"].lower()
        assert "k65" in answer_lower or "K65" in result["answer"]
        assert "k70" in answer_lower or "K70" in result["answer"]
```

### Checklist Ngày 4-5
- [ ] Routing tests pass (chitchat/simple/complex đúng mode)
- [ ] `test_graduation_uses_multi_rag` pass
- [ ] `test_answer_quality` pass — answer có nội dung thực
- [ ] `test_agent_fallback_on_failure` pass — không crash

### Deliverable cuối Tuần 3
> ✅ Hệ thống end-to-end hoạt động  
> ✅ Câu đơn giản → RAG v2, câu phức tạp → LangGraph Agent  
> ✅ Không regression với pipeline cũ

---

# TUẦN 4 — Logging · Evaluation · Báo cáo

**Mục tiêu**: Agent traces lưu MongoDB, so sánh định lượng Agent vs RAG v2.

---

## Ngày 1 — MongoDB Agent Traces

### `pipeline/mongo_logger.py` — Thêm agent logging

```python
# Thêm vào class MongoLogger hiện tại:

from datetime import datetime

def log_agent_trace(self, session_id: str, trace_dict: dict):
    """Lưu LangGraph agent trace vào collection 'agent_traces'."""
    doc = {
        "session_id": session_id,
        "created_at": datetime.utcnow(),
        **trace_dict,
    }
    try:
        self.db["agent_traces"].insert_one(doc)
    except Exception as e:
        logger.error(f"Failed to log agent trace: {e}")
        # Không raise — logging failure không crash chatbot

def get_agent_stats(self, limit: int = 100) -> dict:
    """Thống kê hiệu suất agent — dùng cho evaluation."""
    traces = list(self.db["agent_traces"].find(
        {}, {"_id": 0},
        sort=[("created_at", -1)], limit=limit
    ))
    if not traces:
        return {}

    avg_iterations = sum(t.get("iterations", 0) for t in traces) / len(traces)
    tool_freq: dict = {}
    for t in traces:
        for tool in t.get("tool_names_sequence", []):
            tool_freq[tool] = tool_freq.get(tool, 0) + 1
    error_count = sum(1 for t in traces if t.get("error"))

    return {
        "total_traces": len(traces),
        "avg_iterations": round(avg_iterations, 2),
        "tool_frequency": tool_freq,
        "error_rate": round(error_count / len(traces), 3),
    }
```

### Setup MongoDB indexes (chạy 1 lần)

```python
# scripts/setup_mongo_indexes.py
from pymongo import MongoClient, DESCENDING

client = MongoClient("YOUR_MONGO_URI")
db = client["YOUR_DB_NAME"]

db["agent_traces"].create_index([("session_id", 1)])
db["agent_traces"].create_index([("created_at", DESCENDING)])
db["agent_traces"].create_index([("tool_names_sequence", 1)])
print("Indexes created for agent_traces")
```

### Checklist Ngày 1
- [ ] `log_agent_trace()` không crash khi MongoDB unavailable
- [ ] `db.agent_traces.find_one()` có document sau khi chạy test
- [ ] Index trên `session_id` và `created_at`

---

## Ngày 2 — Bộ câu hỏi Evaluation

```json
// eval/question_sets/simple_questions.json (thêm đủ 10 câu)
[
  {"id": "S01", "query": "Điều kiện xét học bổng KKHT là gì?",
   "expected_keywords": ["GPA", "tín chỉ", "học bổng"], "expected_route": "simple"},
  {"id": "S02", "query": "Môn Toán cao cấp 1 có bao nhiêu tín chỉ?",
   "expected_keywords": ["tín chỉ"], "expected_route": "simple"},
  {"id": "S03", "query": "Lịch thi kết thúc học phần học kỳ 1 khi nào?",
   "expected_keywords": ["thi", "học kỳ"], "expected_route": "simple"}
]
```

```json
// eval/question_sets/complex_questions.json (thêm đủ 10 câu)
[
  {"id": "C01", "query": "So sánh điều kiện nhận học bổng KKHT giữa K65 và K70",
   "expected_keywords": ["K65", "K70", "học bổng"],
   "expected_route": "complex", "expected_tools": ["compare_cohorts"]},
  {"id": "C02", "query": "Tôi đã tích lũy đủ tín chỉ và không có môn F, tôi đủ điều kiện tốt nghiệp chưa?",
   "expected_keywords": ["tốt nghiệp", "điều kiện"],
   "expected_route": "complex", "expected_tools": ["multi_rag_search"]}
]
```

### Checklist Ngày 2
- [ ] 10 câu simple + 10 câu complex trong JSON files
- [ ] Mỗi câu có `expected_keywords`, `expected_route`, `expected_tools`

---

## Ngày 3-4 — Script Evaluation

### `eval/evaluate.py`

```python
# eval/evaluate.py
"""
So sánh RAG v2 vs LangGraph Agent trên bộ câu hỏi thực.
Chạy: python eval/evaluate.py
"""
import json
import time
import logging
from pipeline.rag_pipeline import RAGPipeline
from config.settings import Settings

logging.basicConfig(level=logging.WARNING)


def load_questions(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def evaluate_answer(answer: str, expected_keywords: list[str]) -> dict:
    if not answer:
        return {"keyword_score": 0.0, "has_content": False}
    answer_lower = answer.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return {
        "keyword_score": found / len(expected_keywords) if expected_keywords else 0.0,
        "has_content": len(answer) > 50,
        "answer_length": len(answer),
    }


def run_evaluation():
    pipeline = RAGPipeline(Settings())
    results = {"simple": [], "complex": []}

    for category, filepath in [
        ("simple", "eval/question_sets/simple_questions.json"),
        ("complex", "eval/question_sets/complex_questions.json"),
    ]:
        questions = load_questions(filepath)
        print(f"\n{'='*50}\nEvaluating {category.upper()} ({len(questions)} questions)\n{'='*50}")

        for q in questions:
            query = q["query"]
            expected_keywords = q.get("expected_keywords", [])
            expected_tools = q.get("expected_tools", [])

            # RAG v2 baseline
            t0 = time.time()
            rag_result = pipeline.query(query)
            rag_time = time.time() - t0
            rag_eval = evaluate_answer(rag_result.get("answer", ""), expected_keywords)

            # LangGraph Agent
            t0 = time.time()
            agent_result = pipeline.query_v3(query)
            agent_time = time.time() - t0
            agent_eval = evaluate_answer(agent_result.get("answer", ""), expected_keywords)

            tool_correct = None
            if expected_tools:
                used_tools = agent_result.get("tools_used", [])
                tool_correct = any(t in used_tools for t in expected_tools)

            row = {
                "id": q["id"],
                "query": query[:60],
                "rag_keyword_score": rag_eval["keyword_score"],
                "agent_keyword_score": agent_eval["keyword_score"],
                "rag_latency": round(rag_time, 2),
                "agent_latency": round(agent_time, 2),
                "agent_iterations": agent_result.get("iterations", 0),
                "tool_correct": tool_correct,
                "agent_mode": agent_result.get("mode"),
            }
            results[category].append(row)

            winner = "AGENT" if agent_eval["keyword_score"] > rag_eval["keyword_score"] else \
                     ("TIE" if agent_eval["keyword_score"] == rag_eval["keyword_score"] else "RAG")
            print(f"[{q['id']}] {winner} | RAG: {rag_eval['keyword_score']:.1f} ({rag_time:.1f}s) "
                  f"| Agent: {agent_eval['keyword_score']:.1f} ({agent_time:.1f}s)")

    # Summary
    print(f"\n{'='*50}\nSUMMARY\n{'='*50}")
    for category, rows in results.items():
        if not rows:
            continue
        avg_rag = sum(r["rag_keyword_score"] for r in rows) / len(rows)
        avg_agent = sum(r["agent_keyword_score"] for r in rows) / len(rows)
        avg_rag_lat = sum(r["rag_latency"] for r in rows) / len(rows)
        avg_agent_lat = sum(r["agent_latency"] for r in rows) / len(rows)

        print(f"\n[{category.upper()}]")
        print(f"  Keyword score — RAG: {avg_rag:.2f} | Agent: {avg_agent:.2f}")
        print(f"  Latency avg   — RAG: {avg_rag_lat:.1f}s | Agent: {avg_agent_lat:.1f}s")

        if category == "complex":
            tool_rows = [r for r in rows if r["tool_correct"] is not None]
            if tool_rows:
                tc = sum(r["tool_correct"] for r in tool_rows) / len(tool_rows)
                print(f"  Tool selection accuracy: {tc:.0%}")

    with open("eval/results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nResults saved to eval/results.json")


if __name__ == "__main__":
    run_evaluation()
```

### Checklist Ngày 3-4
- [ ] `python eval/evaluate.py` chạy không lỗi
- [ ] `eval/results.json` được save
- [ ] Agent keyword score cho câu complex ≥ RAG v2 score

---

## Ngày 5 — Phân tích & Báo cáo

### Template kết quả

```markdown
## Kết quả Evaluation — LangGraph Agent vs RAG v2

### Simple Questions (n=10)
| Metric | RAG v2 | Agent |
|---|---|---|
| Keyword Score | X.XX | X.XX |
| Avg Latency | X.Xs | X.Xs |

Nhận xét: Agent không cải thiện đáng kể câu đơn giản (expected — chúng vẫn chạy RAG v2).
Overhead nhỏ do qua ComplexityRouter.

### Complex Questions (n=10)
| Metric | RAG v2 | Agent |
|---|---|---|
| Keyword Score | X.XX | X.XX |
| Tool Selection Accuracy | N/A | X% |
| Avg Latency | X.Xs | X.Xs |
| Avg Iterations | N/A | X.X |

Nhận xét: Agent cải thiện rõ rệt câu phức tạp (dự kiến +20-40% keyword score).
```

### Checklist Ngày 5
- [ ] So sánh keyword scores simple vs complex
- [ ] Xác nhận câu simple không regression
- [ ] Tool selection accuracy cho câu complex
- [ ] Latency overhead của agent so với RAG v2
- [ ] Snapshot MongoDB `agent_traces` cho thesis

### Deliverable cuối Tuần 4
> ✅ MongoDB lưu đầy đủ LangGraph agent traces  
> ✅ Bảng so sánh định lượng RAG v2 vs Agent  
> ✅ Kết quả evaluation chứng minh agent tốt hơn với câu phức tạp  
> ✅ Data sẵn sàng cho chương "Kết quả thực nghiệm" của thesis

---

## Checklist tổng kết toàn dự án

### Files được tạo mới
- [x] `agent/__init__.py`
- [x] `agent/state.py`
- [x] `agent/tools.py`
- [x] `agent/tool_adapters.py`
- [x] `agent/prompts.py`
- [x] `agent/complexity_router.py`
- [ ] `agent/graph_state.py`          ← Tuần 2*
- [ ] `agent/lc_tools.py`             ← Tuần 2*

### Files được viết lại / cập nhật
- [ ] `agent/react_agent.py`          ← Viết lại bằng LangGraph (Tuần 2*)
- [ ] `agent/__init__.py`             ← Cập nhật exports (Tuần 2*)
- [ ] `pipeline/rag_pipeline.py`      ← Thêm `query_v3()`, KHÔNG sửa `query()` cũ (Tuần 3)
- [ ] `pipeline/mongo_logger.py`      ← Thêm `log_agent_trace()` (Tuần 4)
- [ ] `api/routes/chat.py`            ← Thêm `/api/chat/v3` (Tuần 3)
- [ ] `config/settings.py`            ← Thêm agent settings (Tuần 3)

### Tests
- [x] `tests/test_adapters.py`
- [ ] `tests/test_agent_langgraph.py` ← Thay thế test_agent_mock.py (Tuần 2*)
- [ ] `tests/test_router.py`          ← Tuần 3
- [ ] `tests/test_e2e.py`             ← Tuần 3

### Evaluation
- [ ] `eval/question_sets/simple_questions.json`  — 10 câu
- [ ] `eval/question_sets/complex_questions.json` — 10 câu
- [ ] `eval/evaluate.py`
- [ ] `eval/results.json`

---

*Stack: Qwen 2.5 8B · LM Studio · Qdrant · MongoDB · Python · LangGraph*  
*Kiến trúc: Option A — Agent là layer bổ sung, câu đơn giản vẫn dùng RAG v2 pipeline cũ*
