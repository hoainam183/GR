# Agentic RAG — Kế hoạch triển khai chi tiết (4 tuần)

> **Ngữ cảnh**: Nâng cấp RAG v2 (8-layer linear pipeline) → Agentic RAG với Custom ReAct Loop  
> **Stack**: Qwen 2.5 8B · LM Studio · Qdrant · MongoDB · Python  
> **Kiến trúc**: Option A — Agent là layer bổ sung, câu đơn giản vẫn chạy pipeline cũ

---

## Tổng quan tiến độ

```
Tuần 1  [████████░░░░░░░░]  State · Tools · Adapters · Test độc lập
Tuần 2  [████████████░░░░]  ReAct Agent · Prompts · Mock test · Tune
Tuần 3  [████████████████]  Router · Tích hợp pipeline · E2E test
Tuần 4  [████████████████]  MongoDB logging · Evaluation · Báo cáo
```

---

## Cấu trúc thư mục mục tiêu

```
RAG_v2/
├── agent/
│   ├── __init__.py
│   ├── state.py              ← Tuần 1, Ngày 1
│   ├── tools.py              ← Tuần 1, Ngày 2
│   ├── tool_adapters.py      ← Tuần 1, Ngày 3-4
│   ├── react_agent.py        ← Tuần 2, Ngày 1-2
│   ├── prompts.py            ← Tuần 2, Ngày 1
│   └── complexity_router.py  ← Tuần 3, Ngày 1
├── pipeline/
│   ├── rag_pipeline.py       ← Sửa Tuần 3, Ngày 2-3
│   └── mongo_logger.py       ← Sửa Tuần 4, Ngày 1
├── tests/
│   ├── test_adapters.py      ← Tuần 1, Ngày 5
│   ├── test_agent_mock.py    ← Tuần 2, Ngày 3-4
│   ├── test_router.py        ← Tuần 3, Ngày 1
│   └── test_e2e.py           ← Tuần 3, Ngày 4-5
├── eval/
│   ├── question_sets/
│   │   ├── simple_questions.json    ← Tuần 4, Ngày 2
│   │   └── complex_questions.json   ← Tuần 4, Ngày 2
│   └── evaluate.py           ← Tuần 4, Ngày 3-4
└── config/
    └── settings.py           ← Sửa Tuần 3, Ngày 2
```

---

# TUẦN 1 — Foundation: State · Tools · Adapters

**Mục tiêu cuối tuần**: 5 tool adapters hoạt động độc lập, không cần agent loop, test pass hết.

---

## Ngày 1 — `agent/state.py`

### Nhiệm vụ
Xây dựng `AgentState` — trạng thái trung tâm của agent, lưu toàn bộ context qua mỗi iteration.

### Code

```python
# agent/state.py
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime


@dataclass
class ToolResult:
    tool_name: str
    args: dict
    result: str
    iteration: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "tool": self.tool_name,
            "args": self.args,
            "result": self.result,
            "iteration": self.iteration,
            "timestamp": self.timestamp
        }


@dataclass
class AgentState:
    query: str
    session_id: str = ""
    messages: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    tool_call_history: list[str] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 4          # Giữ thấp cho Qwen 8B
    final_answer: str | None = None
    route: str = "complex"           # 'simple' | 'complex' | 'chitchat'
    error: str | None = None

    # --- State checks ---

    def is_done(self) -> bool:
        return (
            self.final_answer is not None
            or self.iteration >= self.max_iterations
            or self.error is not None
        )

    def has_called_tool(self, tool_name: str) -> bool:
        """Tránh gọi cùng tool với cùng args nhiều lần."""
        return tool_name in self.tool_call_history

    # --- Mutation helpers ---

    def add_tool_result(self, tool_name: str, args: dict, result: str):
        tr = ToolResult(
            tool_name=tool_name,
            args=args,
            result=result,
            iteration=self.iteration
        )
        self.tool_results.append(tr)
        self.tool_call_history.append(tool_name)

        # Trim context: chỉ giữ 3 kết quả gần nhất để không overflow context window Qwen 8B
        if len(self.tool_results) > 3:
            self.tool_results = self.tool_results[-3:]

    def get_context_summary(self) -> str:
        """Tóm tắt tool results hiện tại để inject vào messages."""
        if not self.tool_results:
            return "Chưa có kết quả tìm kiếm."
        parts = []
        for tr in self.tool_results:
            parts.append(f"[Kết quả từ {tr.tool_name}]\n{tr.result}")
        return "\n\n---\n\n".join(parts)

    def to_log_dict(self) -> dict:
        """Serialize để lưu MongoDB."""
        return {
            "query": self.query,
            "session_id": self.session_id,
            "route": self.route,
            "iterations": self.iteration,
            "tool_calls": [tr.to_dict() for tr in self.tool_results],
            "tool_names_sequence": self.tool_call_history,
            "final_answer_length": len(self.final_answer) if self.final_answer else 0,
            "error": self.error,
        }
```

### Checklist Ngày 1
- [ ] Tạo file `agent/__init__.py` (để import được)
- [ ] Code `state.py` hoàn chỉnh
- [ ] Viết quick test trong Python shell:
  ```python
  state = AgentState(query="test", session_id="sess_001")
  state.iteration += 1
  state.add_tool_result("rag_search", {"query": "test"}, "kết quả test")
  assert state.has_called_tool("rag_search") == True
  assert state.is_done() == False
  print(state.get_context_summary())  # phải in ra kết quả
  ```
- [ ] Không có external dependency nào — file này pure Python

---

## Ngày 2 — `agent/tools.py`

### Nhiệm vụ
Định nghĩa 5 tool declarations theo format OpenAI function calling mà Qwen 2.5 8B hiểu được.  
**Quan trọng**: Description phải rõ ràng — Qwen 8B quyết định dùng tool nào dựa vào description này.

### Code

```python
# agent/tools.py

# Map tên collection friendly → tên Qdrant thực tế của bạn
# ⚠️ Điều chỉnh các giá trị enum và description cho đúng tên collection thực
COLLECTION_DESCRIPTIONS = {
    "quy_dinh": "quy định học vụ, học bổng KKHT, miễn giảm học phí, kỷ luật, điều kiện tốt nghiệp",
    "chuong_trinh": "chương trình đào tạo, danh sách môn học, số tín chỉ, môn tiên quyết, bắt buộc/tự chọn",
    "ke_hoach": "lịch thi, lịch học kỳ, kế hoạch năm học, tuần học, ngày nghỉ lễ",
    "thong_bao": "thông báo mới nhất, tin tức trường, sự kiện sắp diễn ra",
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": (
                "Tìm kiếm thông tin trong một collection cụ thể của cơ sở dữ liệu trường. "
                "Dùng khi câu hỏi rõ ràng thuộc về một lĩnh vực duy nhất. "
                f"Collections: {'; '.join(f'{k}: {v}' for k, v in COLLECTION_DESCRIPTIONS.items())}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Câu truy vấn tìm kiếm, viết lại ngắn gọn và cụ thể"
                    },
                    "collection": {
                        "type": "string",
                        "enum": list(COLLECTION_DESCRIPTIONS.keys()),
                        "description": "Tên collection cần tìm kiếm"
                    }
                },
                "required": ["query", "collection"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "multi_rag_search",
            "description": (
                "Tìm kiếm đồng thời nhiều collection để trả lời câu hỏi tổng hợp. "
                "Dùng khi câu hỏi cần thông tin từ nhiều nguồn. "
                "Ví dụ: 'Đủ điều kiện tốt nghiệp chưa?' cần cả quy_dinh lẫn chuong_trinh."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "description": "Danh sách các query, mỗi query tìm trên một collection",
                        "items": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "collection": {
                                    "type": "string",
                                    "enum": list(COLLECTION_DESCRIPTIONS.keys())
                                }
                            },
                            "required": ["query", "collection"]
                        },
                        "minItems": 2,
                        "maxItems": 4
                    }
                },
                "required": ["queries"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_cohorts",
            "description": (
                "So sánh quy định hoặc chương trình đào tạo giữa hai khóa sinh viên. "
                "Dùng khi câu hỏi đề cập đến 2 khóa khác nhau (K65, K66, K67, K68, K69, K70...). "
                "Tool này tự động tìm kiếm thông tin của cả 2 khóa."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Chủ đề cần so sánh, ví dụ: 'học bổng KKHT', 'môn học bắt buộc'"
                    },
                    "cohort_a": {
                        "type": "string",
                        "description": "Khóa thứ nhất, ví dụ: K65"
                    },
                    "cohort_b": {
                        "type": "string",
                        "description": "Khóa thứ hai, ví dụ: K70"
                    },
                    "collection": {
                        "type": "string",
                        "enum": ["quy_dinh", "chuong_trinh"],
                        "description": "Collection chứa thông tin cần so sánh"
                    }
                },
                "required": ["topic", "cohort_a", "cohort_b", "collection"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Tìm kiếm thông tin mới nhất trên internet qua Tavily. "
                "Chỉ dùng khi thông tin có thể chưa có trong database (thông báo rất mới, "
                "sự kiện trong tuần này, hoặc khi rag_search không tìm thấy kết quả)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Câu truy vấn web, thêm tên trường để có kết quả chính xác"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clarify_question",
            "description": (
                "Hỏi lại người dùng khi câu hỏi quá mơ hồ không thể tìm kiếm. "
                "Ví dụ: 'học bổng' mà không rõ loại nào. "
                "Dùng tối đa 1 lần trong cuộc hội thoại."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Câu hỏi làm rõ, ngắn gọn"
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-3 lựa chọn gợi ý cho user",
                        "maxItems": 3
                    }
                },
                "required": ["message", "options"]
            }
        }
    }
]

# Helper: lấy tên tool từ definitions
TOOL_NAMES = [t["function"]["name"] for t in TOOL_DEFINITIONS]
```

### Checklist Ngày 2
- [ ] Điền tên Qdrant collection thực tế của bạn vào `COLLECTION_DESCRIPTIONS`
- [ ] Chạy `python -c "from agent.tools import TOOL_DEFINITIONS; print(len(TOOL_DEFINITIONS))"` → phải ra `5`
- [ ] Review description của từng tool: có đủ rõ để Qwen chọn đúng không?
- [ ] Không có external dependency

---

## Ngày 3-4 — `agent/tool_adapters.py`

### Nhiệm vụ
Bọc pipeline hiện tại thành các adapter functions. Đây là phần tốn công nhất tuần 1 vì phải kết nối với code cũ.

### Bước chuẩn bị (làm trước khi code)

Mở pipeline hiện tại và xác định:
```python
# Trả lời các câu hỏi sau về pipeline cũ của bạn:
# 1. Hàm search chính là gì? (embed + Qdrant query + rerank)
# 2. Input của nó là gì? (query string? + collection name?)
# 3. Output của nó là gì? (list Document? list dict? list string?)
# 4. Tavily search được gọi như thế nào?
```

### Code

```python
# agent/tool_adapters.py
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ⚠️ Điều chỉnh import này theo cấu trúc pipeline hiện tại của bạn
# Ví dụ: from pipeline.flows import search_and_rerank
# Ví dụ: from pipeline.rag_pipeline import RAGPipeline
# Ví dụ: from pipeline.retriever import QdrantRetriever

# Map collection name (agent) → collection name thực trong Qdrant
COLLECTION_MAP: dict[str, str] = {
    "quy_dinh":    "YOUR_QDRANT_COLLECTION_NAME_1",   # ← điền tên thực
    "chuong_trinh": "YOUR_QDRANT_COLLECTION_NAME_2",  # ← điền tên thực
    "ke_hoach":    "YOUR_QDRANT_COLLECTION_NAME_3",   # ← điền tên thực
    "thong_bao":   "YOUR_QDRANT_COLLECTION_NAME_4",   # ← điền tên thực
}


# ─────────────────────────────────────────────
# Public entry point — agent gọi hàm này
# ─────────────────────────────────────────────

def execute_tool(tool_name: str, args: dict) -> str:
    """
    Router thực thi tool và trả về string result.
    Mọi lỗi đều được bắt và trả về error string (không raise exception)
    để agent loop không bị crash.
    """
    DISPATCH = {
        "rag_search":        _rag_search,
        "multi_rag_search":  _multi_rag_search,
        "compare_cohorts":   _compare_cohorts,
        "web_search":        _web_search,
        "clarify_question":  _clarify_question,
    }
    adapter = DISPATCH.get(tool_name)
    if adapter is None:
        return f"[Lỗi hệ thống: Tool '{tool_name}' không được hỗ trợ]"
    try:
        result = adapter(**args)
        logger.info(f"Tool {tool_name} executed, result length: {len(result)}")
        return result
    except TypeError as e:
        # Sai args — log để debug
        logger.error(f"Tool {tool_name} wrong args {args}: {e}")
        return f"[Lỗi: Tham số không đúng cho tool {tool_name}: {e}]"
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
        return f"[Lỗi khi tìm kiếm: {str(e)}]"


# ─────────────────────────────────────────────
# Adapter implementations
# ─────────────────────────────────────────────

def _rag_search(query: str, collection: str) -> str:
    """
    Gọi RAG pipeline hiện tại (embed → Qdrant search → rerank).
    ⚠️ Điều chỉnh phần import và gọi hàm cho đúng với pipeline của bạn.
    """
    qdrant_collection = COLLECTION_MAP.get(collection)
    if not qdrant_collection:
        return f"[Lỗi: Collection '{collection}' không hợp lệ]"

    # ─── Điều chỉnh đoạn này ───────────────────────────────────────
    # Ví dụ 1: Nếu pipeline của bạn có hàm standalone:
    # from pipeline.flows import search_flow
    # results = search_flow(query=query, collection=qdrant_collection, top_k=5)

    # Ví dụ 2: Nếu pipeline là class method:
    # from pipeline.rag_pipeline import get_pipeline_instance
    # pipeline = get_pipeline_instance()
    # results = pipeline.search(query=query, collection=qdrant_collection)

    # Ví dụ 3: Nếu search trực tiếp Qdrant:
    # from pipeline.retriever import embed_and_search
    # results = embed_and_search(query, collection=qdrant_collection, top_k=5)
    # ───────────────────────────────────────────────────────────────

    raise NotImplementedError("⚠️ Điều chỉnh lời gọi pipeline tại đây")

    return _format_search_results(results, collection)


def _multi_rag_search(queries: list[dict]) -> str:
    """Search nhiều collection và ghép kết quả."""
    if not queries:
        return "[Lỗi: Không có query nào được cung cấp]"

    parts = []
    for q in queries:
        query_text = q.get("query", "")
        collection = q.get("collection", "")
        if not query_text or not collection:
            continue
        result = _rag_search(query=query_text, collection=collection)
        header = f"### Thông tin từ [{collection}] — '{query_text}'"
        parts.append(f"{header}\n{result}")

    if not parts:
        return "Không tìm thấy thông tin từ các nguồn được yêu cầu."
    return "\n\n---\n\n".join(parts)


def _compare_cohorts(topic: str, cohort_a: str, cohort_b: str, collection: str) -> str:
    """Tìm thông tin cho 2 khóa và ghép lại để agent so sánh."""
    query_a = f"{topic} {cohort_a}"
    query_b = f"{topic} {cohort_b}"

    result_a = _rag_search(query=query_a, collection=collection)
    result_b = _rag_search(query=query_b, collection=collection)

    return (
        f"### {topic} — {cohort_a}\n{result_a}\n\n"
        f"---\n\n"
        f"### {topic} — {cohort_b}\n{result_b}"
    )


def _web_search(query: str) -> str:
    """
    Gọi Tavily search (đã có trong pipeline cũ).
    ⚠️ Điều chỉnh import theo pipeline hiện tại.
    """
    # ─── Điều chỉnh đoạn này ───────────────────────────────────────
    # from pipeline.tools.tavily_tool import TavilySearchTool
    # tavily = TavilySearchTool()
    # results = tavily.search(query, max_results=3)
    # ───────────────────────────────────────────────────────────────
    raise NotImplementedError("⚠️ Điều chỉnh lời gọi Tavily tại đây")

    return _format_web_results(results)


def _clarify_question(message: str, options: list[str]) -> str:
    """
    Không gọi external API — trả về formatted string để agent
    relay lại cho user. Agent sẽ dùng chuỗi này làm final answer.
    """
    options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
    return f"[CLARIFY]\n{message}\n\n{options_text}"


# ─────────────────────────────────────────────
# Format helpers
# ─────────────────────────────────────────────

def _format_search_results(results: Any, collection: str) -> str:
    """
    Chuyển output của pipeline cũ → string cho agent.
    ⚠️ Điều chỉnh theo format output thực tế của pipeline bạn.
    """
    if not results:
        return f"Không tìm thấy thông tin phù hợp trong {collection}."

    chunks = []
    # Ví dụ nếu results là list[ScoredPoint] từ Qdrant:
    for i, item in enumerate(results[:4], 1):
        if hasattr(item, "payload"):          # Qdrant ScoredPoint
            content = item.payload.get("content", "")
            source = item.payload.get("source", "")
        elif isinstance(item, dict):           # dict format
            content = item.get("content", item.get("text", str(item)))
            source = item.get("source", "")
        else:                                  # plain string
            content = str(item)
            source = ""

        chunk = f"[{i}] {content}"
        if source:
            chunk += f"\n    Nguồn: {source}"
        chunks.append(chunk)

    return "\n\n".join(chunks)


def _format_web_results(results: Any) -> str:
    """Chuyển Tavily results → string."""
    if not results:
        return "Không tìm thấy thông tin trên web."

    chunks = []
    items = results if isinstance(results, list) else results.get("results", [])
    for i, item in enumerate(items[:3], 1):
        title = item.get("title", "")
        content = item.get("content", "")[:500]   # cắt bớt
        url = item.get("url", "")
        chunks.append(f"[{i}] {title}\n{content}\nURL: {url}")
    return "\n\n".join(chunks)
```

### Checklist Ngày 3-4
- [ ] Xác định hàm search của pipeline cũ (tên hàm, input, output format)
- [ ] Điền `COLLECTION_MAP` với tên Qdrant collection thực tế
- [ ] Điều chỉnh `_rag_search`: import và gọi đúng hàm pipeline
- [ ] Điều chỉnh `_web_search`: import và gọi đúng TavilySearchTool
- [ ] Điều chỉnh `_format_search_results`: match với format output thực tế
- [ ] Xóa các `raise NotImplementedError` sau khi đã implement

---

## Ngày 5 — Test adapter độc lập

### `tests/test_adapters.py`

```python
# tests/test_adapters.py
"""
Test các tool adapters KHÔNG cần agent loop.
Chạy: pytest tests/test_adapters.py -v
"""
import pytest
from agent.tool_adapters import execute_tool, _clarify_question


class TestExecuteToolRouter:
    """Test router dispatch — không cần Qdrant kết nối."""

    def test_unknown_tool_returns_error_string(self):
        result = execute_tool("nonexistent_tool", {})
        assert "[Lỗi hệ thống:" in result
        assert "nonexistent_tool" in result

    def test_wrong_args_returns_error_string(self):
        # rag_search thiếu 'collection'
        result = execute_tool("rag_search", {"query": "test"})
        assert "[Lỗi:" in result  # không raise exception

    def test_clarify_question_no_api_needed(self):
        result = _clarify_question(
            message="Bạn muốn hỏi về học bổng nào?",
            options=["Học bổng KKHT", "Học bổng tài trợ", "Học bổng toàn phần"]
        )
        assert "[CLARIFY]" in result
        assert "KKHT" in result
        assert "1." in result  # options được đánh số


class TestRagSearch:
    """Test rag_search với Qdrant thực (cần Qdrant running)."""

    @pytest.mark.integration
    def test_rag_search_quy_dinh(self):
        result = execute_tool("rag_search", {
            "query": "điều kiện tốt nghiệp",
            "collection": "quy_dinh"
        })
        assert isinstance(result, str)
        assert len(result) > 50  # có kết quả thực sự
        assert "Không tìm thấy" not in result

    @pytest.mark.integration
    def test_rag_search_invalid_collection(self):
        result = execute_tool("rag_search", {
            "query": "test",
            "collection": "invalid_collection_xyz"
        })
        assert "[Lỗi:" in result

    @pytest.mark.integration
    def test_multi_rag_search_returns_multiple_sections(self):
        result = execute_tool("multi_rag_search", {
            "queries": [
                {"query": "điều kiện tốt nghiệp", "collection": "quy_dinh"},
                {"query": "tín chỉ tích lũy", "collection": "chuong_trinh"}
            ]
        })
        assert "---" in result  # separator giữa 2 sections
        assert "quy_dinh" in result
        assert "chuong_trinh" in result

    @pytest.mark.integration
    def test_compare_cohorts_returns_both_cohorts(self):
        result = execute_tool("compare_cohorts", {
            "topic": "học bổng KKHT",
            "cohort_a": "K65",
            "cohort_b": "K70",
            "collection": "quy_dinh"
        })
        assert "K65" in result
        assert "K70" in result


class TestWebSearch:
    """Test web search — cần Tavily API key."""

    @pytest.mark.integration
    def test_web_search_returns_content(self):
        result = execute_tool("web_search", {
            "query": "Đại học Bách Khoa Hà Nội thông báo mới"
        })
        assert isinstance(result, str)
        assert len(result) > 100
```

### Chạy test

```bash
# Test không cần Qdrant (unit tests)
pytest tests/test_adapters.py -v -m "not integration"

# Test đầy đủ (cần Qdrant + LM Studio running)
pytest tests/test_adapters.py -v

# Xem coverage
pytest tests/test_adapters.py -v --tb=short
```

### Checklist Ngày 5
- [ ] Tất cả unit test (not integration) pass — không cần Qdrant
- [ ] Ít nhất `test_rag_search_quy_dinh` integration test pass
- [ ] `test_compare_cohorts_returns_both_cohorts` pass — kết quả có cả 2 khóa
- [ ] Không có exception nào raise ra ngoài `execute_tool` (chỉ error string)

### Deliverable cuối Tuần 1
> ✅ `agent/state.py`, `agent/tools.py`, `agent/tool_adapters.py` hoàn chỉnh  
> ✅ Tất cả adapter test pass  
> ✅ `execute_tool("rag_search", {...})` trả về kết quả thực từ Qdrant

---

# TUẦN 2 — Agent Core: ReAct Loop · Prompts · Mock Test

**Mục tiêu cuối tuần**: Agent loop chạy được với Qwen, gọi đúng tool theo câu hỏi, tune prompt đến độ chính xác ≥ 80%.

---

## Ngày 1 — `agent/prompts.py`

### Nhiệm vụ
System prompt là phần **ảnh hưởng nhất** đến chất lượng của Qwen 8B. Viết cẩn thận từng chữ.

### Code

```python
# agent/prompts.py

AGENT_SYSTEM_PROMPT = """Bạn là trợ lý tư vấn học vụ chính thức của Đại học Bách Khoa Hà Nội.
Nhiệm vụ: Trả lời câu hỏi của sinh viên về quy định, chương trình đào tạo, lịch học và thông báo.

## CÁC CÔNG CỤ BẠN CÓ THỂ DÙNG

- **rag_search**: Tìm trong database. Chọn đúng collection:
  - `quy_dinh`: quy định học vụ, học bổng, điều kiện tốt nghiệp, kỷ luật
  - `chuong_trinh`: môn học, tín chỉ, chương trình đào tạo
  - `ke_hoach`: lịch thi, lịch học kỳ, kế hoạch năm học
  - `thong_bao`: thông báo và tin tức mới

- **multi_rag_search**: Khi câu hỏi cần thông tin từ ≥2 nguồn khác nhau

- **compare_cohorts**: Khi câu hỏi so sánh giữa 2 khóa (K65, K70...)

- **web_search**: Chỉ khi rag_search không có kết quả hoặc cần thông tin rất mới

- **clarify_question**: Khi câu hỏi quá mơ hồ, không thể tìm kiếm được

## NGUYÊN TẮC BẮT BUỘC

1. **Luôn tìm kiếm trước khi trả lời** — không được đoán hoặc tự bịa thông tin
2. **Chọn đúng tool** theo từng loại câu hỏi
3. **Không lặp lại tool call** nếu đã có kết quả từ tool đó
4. **Khi đã có đủ thông tin** → trả lời ngay, không tìm thêm
5. **Trả lời bằng tiếng Việt**, rõ ràng, có dẫn nguồn khi có thể

## VÍ DỤ QUYẾT ĐỊNH TOOL

Câu hỏi: "Điều kiện xét học bổng KKHT là gì?"
→ Dùng: rag_search(query="điều kiện học bổng KKHT", collection="quy_dinh")

Câu hỏi: "Sinh viên K70 ngành CNTT học bao nhiêu tín chỉ?"
→ Dùng: rag_search(query="tín chỉ tích lũy K70 CNTT", collection="chuong_trinh")

Câu hỏi: "So sánh học bổng KKHT giữa K65 và K70"
→ Dùng: compare_cohorts(topic="học bổng KKHT", cohort_a="K65", cohort_b="K70", collection="quy_dinh")

Câu hỏi: "Tôi đủ điều kiện tốt nghiệp chưa?"
→ Dùng: multi_rag_search với cả quy_dinh và chuong_trinh

Câu hỏi: "Cho biết về học bổng"
→ Dùng: clarify_question để hỏi rõ hơn"""


SYNTHESIS_PROMPT = """Bạn là trợ lý tư vấn học vụ Đại học Bách Khoa Hà Nội.
Dựa vào thông tin đã tìm kiếm được, hãy trả lời câu hỏi của sinh viên một cách rõ ràng và chính xác.

Quy tắc:
- Chỉ dùng thông tin đã cung cấp, không bịa thêm
- Trả lời bằng tiếng Việt
- Nếu không có đủ thông tin, hãy nói thẳng là "Tôi không tìm thấy thông tin về vấn đề này"
- Có thể đề xuất sinh viên liên hệ Phòng Đào tạo nếu cần xác nhận chính thức"""


# Prompt để extract final answer từ agent response
# Dùng khi agent output lẫn lộn với reasoning text
EXTRACT_ANSWER_PROMPT = """Từ đoạn văn sau, hãy trích xuất và viết lại câu trả lời cuối cùng dành cho sinh viên.
Bỏ đi các phần suy nghĩ nội bộ (Thought, Observation, Action).
Chỉ giữ nội dung trả lời thực sự:

{raw_output}

Câu trả lời cuối cùng:"""
```

### Checklist Ngày 1
- [ ] System prompt có đủ ví dụ tool selection không?
- [ ] Description của mỗi collection có đủ keyword để Qwen phân biệt không?
- [ ] Đọc to system prompt — có điểm nào mơ hồ không?

---

## Ngày 2 — `agent/react_agent.py`

### Nhiệm vụ
Implement ReAct loop với robust error handling cho Qwen 8B.

### Code

```python
# agent/react_agent.py
import json
import logging
from openai import OpenAI, APIConnectionError, APITimeoutError

from .state import AgentState
from .tools import TOOL_DEFINITIONS
from .tool_adapters import execute_tool
from .prompts import AGENT_SYSTEM_PROMPT, SYNTHESIS_PROMPT

logger = logging.getLogger(__name__)


class ReActAgent:

    def __init__(self, settings):
        self.client = OpenAI(
            base_url=settings.lm_studio_url,    # "http://localhost:1234/v1"
            api_key="lm-studio",
            timeout=30.0                         # Qwen 8B local có thể chậm
        )
        self.model = settings.agent_model
        self.max_iterations = settings.agent_max_iterations  # 4

    def run(self, query: str, session_id: str = "") -> AgentState:
        """
        Main entry point. Trả về AgentState đầy đủ để caller có thể log.
        """
        state = AgentState(query=query, session_id=session_id)
        state.messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ]

        logger.info(f"[Agent] Starting for query: '{query[:80]}...'")

        while not state.is_done():
            state.iteration += 1
            logger.info(f"[Agent] Iteration {state.iteration}/{self.max_iterations}")

            action = self._get_next_action(state)

            if action["type"] == "final_answer":
                state.final_answer = action["content"]
                logger.info(f"[Agent] Final answer at iteration {state.iteration}")

            elif action["type"] == "tool_call":
                tool_name = action["tool"]
                tool_args = action["args"]

                # Guard: không gọi tool đã gọi rồi (tránh infinite loop)
                if state.has_called_tool(tool_name) and tool_name != "clarify_question":
                    logger.warning(f"[Agent] Tool '{tool_name}' already called, forcing synthesis")
                    state.final_answer = self._synthesize(state)
                    break

                # Execute tool
                logger.info(f"[Agent] Calling tool: {tool_name}({tool_args})")
                result = execute_tool(tool_name, tool_args)
                state.add_tool_result(tool_name, tool_args, result)

                # Handle clarify — kết quả clarify là final answer
                if tool_name == "clarify_question":
                    state.final_answer = result.replace("[CLARIFY]\n", "")
                    break

                # Append vào messages để Qwen biết kết quả và tiếp tục
                state.messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [action["raw_tool_call"]]
                })
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": action["raw_tool_call"]["id"],
                    "content": result[:2000]  # Cắt bớt nếu quá dài cho context window
                })

            elif action["type"] == "connection_error":
                state.error = action.get("message", "LM Studio không phản hồi")
                logger.error(f"[Agent] Connection error: {state.error}")
                # Fallback: dùng context đã có (nếu có)
                if state.tool_results:
                    state.final_answer = self._synthesize(state)
                break

            else:  # parse_error
                logger.warning(f"[Agent] Parse error at iteration {state.iteration}")
                if state.tool_results:
                    # Đã có đủ info, synthesize thẳng
                    state.final_answer = self._synthesize(state)
                    break
                # Chưa có info gì, cho loop tiếp (với updated message)

        # Nếu hết iterations mà chưa có final answer
        if not state.final_answer and not state.error:
            logger.warning("[Agent] Max iterations reached, synthesizing from available context")
            state.final_answer = self._synthesize(state)

        return state

    def _get_next_action(self, state: AgentState) -> dict:
        """
        Gọi Qwen để quyết định action tiếp theo.
        Returns dict with type: 'tool_call' | 'final_answer' | 'parse_error' | 'connection_error'
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=state.messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.1,      # Thấp cho quyết định nhất quán
                max_tokens=800
            )
            msg = response.choices[0].message

            # Qwen chọn gọi tool
            if msg.tool_calls and len(msg.tool_calls) > 0:
                tc = msg.tool_calls[0]
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    logger.error(f"[Agent] JSON parse error in tool args: {tc.function.arguments}")
                    return {"type": "parse_error"}

                return {
                    "type": "tool_call",
                    "tool": tc.function.name,
                    "args": args,
                    "raw_tool_call": {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                }

            # Qwen trả lời trực tiếp
            elif msg.content:
                return {"type": "final_answer", "content": msg.content}

            else:
                logger.warning("[Agent] Empty response from Qwen")
                return {"type": "parse_error"}

        except (APIConnectionError, APITimeoutError) as e:
            return {"type": "connection_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[Agent] Unexpected error: {e}", exc_info=True)
            return {"type": "parse_error"}

    def _synthesize(self, state: AgentState) -> str:
        """
        Fallback: Gọi Qwen một lần nữa không dùng tools,
        chỉ để tổng hợp từ tool results đã có.
        """
        if not state.tool_results:
            return "Xin lỗi, tôi không tìm thấy thông tin phù hợp với câu hỏi của bạn. Vui lòng liên hệ Phòng Đào tạo để được hỗ trợ."

        context = state.get_context_summary()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYNTHESIS_PROMPT},
                    {"role": "user", "content": f"Câu hỏi: {state.query}\n\nThông tin tìm được:\n{context}"}
                ],
                temperature=0.2,
                max_tokens=600
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[Agent] Synthesis fallback failed: {e}")
            return f"Tìm thấy một số thông tin nhưng không thể tổng hợp. Thông tin thô:\n{context[:500]}"
```

### Checklist Ngày 2
- [ ] `ReActAgent` import được không lỗi
- [ ] Timeout 30s set — Qwen 8B local cần thời gian
- [ ] Guard tránh gọi tool lặp hoạt động
- [ ] `_synthesize` được gọi khi max_iterations hoặc parse_error

---

## Ngày 3-4 — Test với Mock Tools

### `tests/test_agent_mock.py`

```python
# tests/test_agent_mock.py
"""
Test ReAct Agent với mock tools — không cần LM Studio running.
Pytest: pytest tests/test_agent_mock.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from agent.react_agent import ReActAgent
from agent.state import AgentState


def make_mock_settings():
    settings = MagicMock()
    settings.lm_studio_url = "http://localhost:1234/v1"
    settings.agent_model = "qwen2.5-8b-instruct"
    settings.agent_max_iterations = 4
    return settings


def make_tool_call_response(tool_name: str, args: dict, call_id: str = "call_001"):
    """Tạo mock response giả lập Qwen gọi tool."""
    import json
    mock_response = MagicMock()
    mock_response.choices[0].message.content = None
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(args)
    mock_response.choices[0].message.tool_calls = [tc]
    return mock_response


def make_final_answer_response(content: str):
    """Tạo mock response giả lập Qwen trả lời trực tiếp."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_response.choices[0].message.tool_calls = None
    return mock_response


class TestAgentFlow:

    @patch("agent.react_agent.execute_tool")
    @patch("openai.OpenAI")
    def test_simple_one_tool_flow(self, mock_openai_cls, mock_execute_tool):
        """Agent gọi 1 tool rồi trả lời."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Lần 1: gọi tool; Lần 2: trả lời
        mock_client.chat.completions.create.side_effect = [
            make_tool_call_response("rag_search", {"query": "học bổng KKHT", "collection": "quy_dinh"}),
            make_final_answer_response("Học bổng KKHT yêu cầu GPA ≥ 3.2 và không có môn F.")
        ]
        mock_execute_tool.return_value = "Nội dung quy định học bổng KKHT: GPA ≥ 3.2..."

        agent = ReActAgent(make_mock_settings())
        state = agent.run("Điều kiện học bổng KKHT là gì?")

        assert state.final_answer is not None
        assert "KKHT" in state.final_answer
        assert len(state.tool_call_history) == 1
        assert state.tool_call_history[0] == "rag_search"
        assert state.error is None

    @patch("agent.react_agent.execute_tool")
    @patch("openai.OpenAI")
    def test_multi_tool_compare_flow(self, mock_openai_cls, mock_execute_tool):
        """Agent gọi compare_cohorts cho câu hỏi so sánh."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = [
            make_tool_call_response("compare_cohorts", {
                "topic": "học bổng KKHT",
                "cohort_a": "K65", "cohort_b": "K70",
                "collection": "quy_dinh"
            }),
            make_final_answer_response("K65: GPA ≥ 3.2. K70: GPA ≥ 3.5. K70 có yêu cầu cao hơn.")
        ]
        mock_execute_tool.return_value = "### K65\nGPA ≥ 3.2\n---\n### K70\nGPA ≥ 3.5"

        agent = ReActAgent(make_mock_settings())
        state = agent.run("So sánh học bổng KKHT K65 và K70")

        assert "compare_cohorts" in state.tool_call_history
        assert state.final_answer is not None

    @patch("agent.react_agent.execute_tool")
    @patch("openai.OpenAI")
    def test_max_iterations_fallback(self, mock_openai_cls, mock_execute_tool):
        """Khi đạt max iterations, agent phải synthesize."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Luôn gọi tool (không bao giờ final answer) — sẽ bị giới hạn bởi max_iterations
        # Nhưng guard "has_called_tool" sẽ chặn sau lần 1
        mock_client.chat.completions.create.return_value = make_tool_call_response(
            "rag_search", {"query": "test", "collection": "quy_dinh"}
        )
        mock_execute_tool.return_value = "Kết quả test"
        # Mock _synthesize
        mock_client.chat.completions.create.side_effect = [
            make_tool_call_response("rag_search", {"query": "test", "collection": "quy_dinh"}),
            make_final_answer_response("Tổng hợp: Kết quả test")
        ]

        agent = ReActAgent(make_mock_settings())
        state = agent.run("test query")

        assert state.final_answer is not None  # phải có answer cuối cùng

    @patch("openai.OpenAI")
    def test_connection_error_handled(self, mock_openai_cls):
        """LM Studio không respond — agent không crash."""
        from openai import APIConnectionError
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())

        agent = ReActAgent(make_mock_settings())
        state = agent.run("test")

        # Không crash, có error info
        assert state.error is not None or state.final_answer is not None
```

### Checklist Ngày 3-4
- [ ] `test_simple_one_tool_flow` pass
- [ ] `test_multi_tool_compare_flow` pass
- [ ] `test_max_iterations_fallback` pass — không infinite loop
- [ ] `test_connection_error_handled` pass — không crash khi LM Studio tắt

---

## Ngày 5 — Tune Prompt với Qwen thực

### Quy trình tune

```
1. Chuẩn bị 10 câu hỏi test (xem bên dưới)
2. Chạy từng câu → ghi lại tool nào được gọi
3. So sánh với tool mong đợi
4. Điều chỉnh prompt nếu sai ≥ 3 câu
```

### Bộ câu hỏi tune prompt (10 câu)

```python
# Tạo file: tests/prompt_tune_questions.py

TUNE_QUESTIONS = [
    # (query, expected_first_tool, expected_collection)
    ("Điều kiện xét học bổng KKHT học kỳ này là gì?",
     "rag_search", "quy_dinh"),

    ("K70 ngành CNTT phải học bao nhiêu tín chỉ để tốt nghiệp?",
     "rag_search", "chuong_trinh"),

    ("Lịch thi học kỳ 1 năm học 2024-2025 khi nào?",
     "rag_search", "ke_hoach"),

    ("So sánh điều kiện nhận học bổng KKHT giữa K65 và K70",
     "compare_cohorts", None),

    ("Tôi đã học đủ tín chỉ và không có môn F, tôi đủ điều kiện tốt nghiệp chưa?",
     "multi_rag_search", None),

    ("Có thông báo gì mới từ nhà trường không?",
     "rag_search", "thong_bao"),

    ("Học bổng",  # mơ hồ
     "clarify_question", None),

    ("Môn Toán cao cấp 1 có mã môn là gì và có bao nhiêu tín chỉ?",
     "rag_search", "chuong_trinh"),

    ("Quy định về số lần thi lại tối đa là bao nhiêu?",
     "rag_search", "quy_dinh"),

    ("Chương trình đào tạo K70 và K68 khác nhau những gì?",
     "compare_cohorts", None),
]
```

### Script chạy tune

```python
# tests/run_prompt_tune.py
"""
Chạy: python tests/run_prompt_tune.py
"""
from agent.react_agent import ReActAgent
from tests.prompt_tune_questions import TUNE_QUESTIONS

# Mock settings — điền URL thực của LM Studio
class Settings:
    lm_studio_url = "http://localhost:1234/v1"
    agent_model = "qwen2.5-8b-instruct"
    agent_max_iterations = 4

agent = ReActAgent(Settings())
correct = 0

for query, expected_tool, expected_collection in TUNE_QUESTIONS:
    state = agent.run(query)
    first_tool = state.tool_call_history[0] if state.tool_call_history else "NONE"
    is_correct = first_tool == expected_tool
    correct += is_correct
    status = "✅" if is_correct else "❌"
    print(f"{status} '{query[:50]}'")
    print(f"   Expected: {expected_tool} | Got: {first_tool}")

print(f"\nAccuracy: {correct}/{len(TUNE_QUESTIONS)} = {correct/len(TUNE_QUESTIONS)*100:.0f}%")
```

### Checklist Ngày 5
- [ ] Accuracy ≥ 8/10 (80%) mới chuyển sang Tuần 3
- [ ] Nếu `clarify_question` bị gọi sai (câu hỏi rõ ràng) → thêm ví dụ vào prompt
- [ ] Nếu `rag_search` hay chọn sai collection → bổ sung keyword vào description
- [ ] Nếu `compare_cohorts` không được gọi → thêm pattern K\d\d vào tool description

### Deliverable cuối Tuần 2
> ✅ `react_agent.py` + `prompts.py` hoàn chỉnh  
> ✅ Tất cả mock test pass  
> ✅ Prompt tune accuracy ≥ 80% với Qwen 8B thực

---

# TUẦN 3 — Integration: Router · Pipeline · E2E

**Mục tiêu cuối tuần**: Hệ thống hoàn chỉnh chạy end-to-end, câu đơn giản vào pipeline cũ, câu phức tạp vào agent.

---

## Ngày 1 — `agent/complexity_router.py` + Test

### Code

```python
# agent/complexity_router.py
import re
import logging

logger = logging.getLogger(__name__)

# ─── Pattern groups ─────────────────────────────────────────────────

CHITCHAT_PATTERNS = [
    r"^(xin chào|hello|hi|chào|hey|yo)\b",
    r"^(bạn là ai|bạn tên gì|you are|who are you)",
    r"^(cảm ơn|thank you|thanks|cảm ơn bạn)",
    r"^(tạm biệt|bye|goodbye|good bye)",
    r"^(ok|okay|được|ừ|vâng|nhé)\s*$",  # 1 từ xã giao
]

COMPLEX_PATTERNS = [
    # So sánh khóa
    r"so\s+sánh",
    r"(K\d{2,}).{0,30}(K\d{2,})",           # K65...K70
    r"khác\s+nhau|giống\s+nhau|khác\s+biệt",
    r"(khóa|lứa|niên\s+khóa).{0,20}(khóa|lứa|niên\s+khóa)",

    # Câu hỏi tổng hợp / điều kiện phức
    r"đủ\s+điều\s+kiện",
    r"có\s+thể.{0,30}(tốt\s+nghiệp|đăng\s+ký|xét|nhận)",
    r"tất\s+cả.{0,20}điều\s+kiện",
    r"điều\s+kiện.{0,30}và.{0,30}điều\s+kiện",  # nhiều điều kiện

    # Câu hỏi mơ hồ (quá ngắn/chung chung)
    r"^(học\s+bổng|môn\s+học|lịch|quy\s+định|chương\s+trình)\s*\??$",

    # Multi-step
    r"(và|đồng\s+thời|cũng\s+như).{0,30}(cho\s+biết|liệt\s+kê|so\s+sánh)",
]

# Keywords chỉ ra đây là câu hỏi về lịch/thời gian — simple
SCHEDULE_SIMPLE_PATTERNS = [
    r"lịch\s+thi\s+\w+\s+(ngày|tuần|tháng|học\s+kỳ)",
    r"(ngày|tuần|tháng)\s+\d+.{0,20}(thi|học|nghỉ)",
]


class ComplexityRouter:

    def route(self, query: str) -> str:
        """
        Returns: 'chitchat' | 'simple' | 'complex'
        """
        q = query.strip()
        q_lower = q.lower()

        # ── 1. Chitchat check ──────────────────────────
        for pattern in CHITCHAT_PATTERNS:
            if re.search(pattern, q_lower):
                logger.info(f"[Router] chitchat: '{q[:50]}'")
                return "chitchat"

        # ── 2. Rõ ràng simple: lịch cụ thể ──────────
        for pattern in SCHEDULE_SIMPLE_PATTERNS:
            if re.search(pattern, q_lower):
                logger.info(f"[Router] simple (schedule): '{q[:50]}'")
                return "simple"

        # ── 3. Complex signals ────────────────────────
        for pattern in COMPLEX_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                logger.info(f"[Router] complex (pattern match): '{q[:50]}'")
                return "complex"

        # ── 4. Heuristic: độ dài và cấu trúc ─────────
        words = q.split()
        question_marks = q.count("?")
        conjunctions = len(re.findall(r"\b(và|với|cùng|đồng\s+thời)\b", q_lower))

        if len(words) > 30:
            logger.info(f"[Router] complex (long query {len(words)} words)")
            return "complex"

        if question_marks > 1:
            logger.info(f"[Router] complex (multiple questions)")
            return "complex"

        if conjunctions >= 2:
            logger.info(f"[Router] complex (multi-conjunction)")
            return "complex"

        # ── 5. Default: simple ────────────────────────
        logger.info(f"[Router] simple (default): '{q[:50]}'")
        return "simple"

    def explain(self, query: str) -> dict:
        """Debug helper: trả về lý do routing."""
        route = self.route(query)
        return {"query": query, "route": route}
```

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
- [ ] Thêm 5 câu hỏi thực tế từ use case trường bạn → test thêm
- [ ] Log routing decision để debug dễ hơn

---

## Ngày 2-3 — Tích hợp vào `rag_pipeline.py` + `settings.py`

### `config/settings.py` — Thêm agent settings

```python
# config/settings.py — thêm vào class Settings hiện tại

# Agent settings
agent_enabled: bool = True
agent_max_iterations: int = 4
agent_model: str = "qwen2.5-8b-instruct"    # tên model trong LM Studio
lm_studio_url: str = "http://localhost:1234/v1"
```

### `pipeline/rag_pipeline.py` — Điều chỉnh tối thiểu

```python
# pipeline/rag_pipeline.py — CHỈ thêm các phần sau, giữ nguyên code cũ

from agent.complexity_router import ComplexityRouter
from agent.react_agent import ReActAgent

class RAGPipeline:

    def __init__(self, settings):
        # ... code __init__ hiện tại ...
        
        # Thêm mới:
        self.complexity_router = ComplexityRouter()
        self.agent = ReActAgent(settings) if settings.agent_enabled else None
        logger.info(f"Agent mode: {'enabled' if self.agent else 'disabled'}")

    # Thêm method mới — KHÔNG sửa method query() cũ
    def query_v3(self, user_query: str, session_id: str = "") -> dict:
        """
        Entry point mới — routing thông minh.
        Method query() cũ vẫn giữ nguyên cho backward compatibility.
        """
        route = self.complexity_router.route(user_query)

        # ── Chitchat ─────────────────────────────────
        if route == "chitchat":
            return {
                "answer": self._handle_chitchat(user_query),
                "mode": "chitchat",
                "route": "chitchat"
            }

        # ── Simple → RAG v2 pipeline cũ ──────────────
        if route == "simple" or self.agent is None:
            result = self.query(user_query)  # gọi method cũ
            result["mode"] = "rag_v2"
            result["route"] = route
            return result

        # ── Complex → Agent ───────────────────────────
        state = self.agent.run(user_query, session_id=session_id)

        # Log agent trace vào MongoDB
        if hasattr(self, "mongo_logger") and self.mongo_logger:
            self.mongo_logger.log_agent_trace(session_id, state.to_log_dict())

        if state.error and not state.final_answer:
            # Fallback về RAG v2 nếu agent thất bại hoàn toàn
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
        """Xử lý chào hỏi đơn giản — tái sử dụng chitchat flow cũ nếu có."""
        # ⚠️ Điều chỉnh theo chitchat implementation hiện tại
        return "Xin chào! Tôi là trợ lý tư vấn học vụ ĐHBK. Bạn cần hỗ trợ gì?"
```

### Thêm API endpoint mới — `api/routes/chat.py`

```python
# api/routes/chat.py — thêm endpoint mới, giữ endpoint cũ

@router.post("/api/chat/v3")
async def chat_v3(request: ChatRequest):
    """
    Endpoint mới với agent support.
    ChatRequest thêm field: mode: "auto" | "rag" | "agent" (default: "auto")
    """
    mode = getattr(request, "mode", "auto")

    if mode == "rag":
        # Force pipeline cũ
        result = pipeline.query(request.message)
    elif mode == "agent":
        # Force agent
        state = pipeline.agent.run(request.message, session_id=request.session_id)
        result = {"answer": state.final_answer, "mode": "agent"}
    else:
        # Auto routing (default)
        result = pipeline.query_v3(request.message, session_id=request.session_id)

    return result
```

### Checklist Ngày 2-3
- [ ] `settings.py` có đủ agent settings
- [ ] `query_v3()` được thêm mà không sửa `query()` cũ
- [ ] `query_v3()` return format nhất quán (có `mode`, `route` field)
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
    settings = Settings()
    return RAGPipeline(settings)

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
        # multi_rag_search phải được gọi
        assert "multi_rag_search" in result.get("tools_used", [])

    def test_agent_fallback_on_lm_studio_down(self, pipeline):
        """Khi LM Studio tắt, phải fallback về RAG v2."""
        import unittest.mock as mock
        with mock.patch.object(pipeline.agent, "run", side_effect=Exception("Connection refused")):
            result = pipeline.query_v3("So sánh K65 và K70")
            # Phải có fallback answer, không crash
            assert result["answer"] is not None


@pytest.mark.e2e
class TestAnswerQuality:

    def test_answer_not_empty(self, pipeline):
        result = pipeline.query_v3("Điều kiện xét học bổng KKHT?")
        assert len(result["answer"]) > 50

    def test_answer_in_vietnamese(self, pipeline):
        result = pipeline.query_v3("Lịch thi học kỳ 1 khi nào?")
        # Kiểm tra có chứa tiếng Việt cơ bản
        vietnamese_chars = set("àáâãèéêìíòóôõùúăđ")
        assert any(c in result["answer"].lower() for c in vietnamese_chars)

    def test_comparison_answer_mentions_both_cohorts(self, pipeline):
        result = pipeline.query_v3("So sánh học bổng KKHT K65 và K70")
        assert "K65" in result["answer"] or "k65" in result["answer"].lower()
        assert "K70" in result["answer"] or "k70" in result["answer"].lower()
```

### Checklist Ngày 4-5
- [ ] Routing tests pass (chitchat/simple/complex đúng mode)
- [ ] `test_graduation_uses_multi_rag` pass — multi_rag_search được gọi
- [ ] `test_answer_quality` pass — answer có nội dung thực
- [ ] `test_agent_fallback_on_lm_studio_down` pass — không crash

### Deliverable cuối Tuần 3
> ✅ Hệ thống end-to-end hoạt động  
> ✅ Câu đơn giản → RAG v2, câu phức tạp → Agent  
> ✅ Không có regression với pipeline cũ

---

# TUẦN 4 — Logging · Evaluation · Báo cáo

**Mục tiêu cuối tuần**: Agent traces được lưu MongoDB, so sánh định lượng agent vs RAG v2.

---

## Ngày 1 — MongoDB Agent Traces

### `pipeline/mongo_logger.py` — Thêm agent logging

```python
# pipeline/mongo_logger.py — thêm vào class MongoLogger hiện tại

from datetime import datetime

class MongoLogger:

    # ... code hiện tại ...

    def log_agent_trace(self, session_id: str, trace_dict: dict):
        """
        Lưu agent trace vào collection 'agent_traces'.
        trace_dict từ AgentState.to_log_dict()
        """
        doc = {
            "session_id": session_id,
            "created_at": datetime.utcnow(),
            **trace_dict
        }
        try:
            self.db["agent_traces"].insert_one(doc)
        except Exception as e:
            logger.error(f"Failed to log agent trace: {e}")
            # Không raise — logging failure không được crash chatbot

    def get_agent_stats(self, limit: int = 100) -> dict:
        """
        Thống kê hiệu suất agent — dùng cho evaluation.
        """
        traces = list(self.db["agent_traces"].find(
            {}, {"_id": 0},
            sort=[("created_at", -1)], limit=limit
        ))
        if not traces:
            return {}

        avg_iterations = sum(t.get("iterations", 0) for t in traces) / len(traces)
        tool_freq = {}
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

### Index MongoDB (chạy 1 lần)

```python
# scripts/setup_mongo_indexes.py
"""Chạy 1 lần để tạo indexes cho agent_traces."""
from pymongo import MongoClient, DESCENDING

client = MongoClient("YOUR_MONGO_URI")
db = client["YOUR_DB_NAME"]

db["agent_traces"].create_index([("session_id", 1)])
db["agent_traces"].create_index([("created_at", DESCENDING)])
db["agent_traces"].create_index([("tool_names_sequence", 1)])  # để query theo tool
print("Indexes created for agent_traces")
```

### Checklist Ngày 1
- [ ] `log_agent_trace()` không crash khi MongoDB unavailable
- [ ] Query kiểm tra: `db.agent_traces.find_one()` có document sau khi test
- [ ] Index được tạo trên `session_id` và `created_at`

---

## Ngày 2 — Chuẩn bị bộ câu hỏi Evaluation

### Tạo 2 bộ câu hỏi

```json
// eval/question_sets/simple_questions.json
[
  {
    "id": "S01",
    "query": "Điều kiện xét học bổng KKHT là gì?",
    "category": "policy",
    "expected_keywords": ["GPA", "tín chỉ", "học bổng"],
    "expected_route": "simple"
  },
  {
    "id": "S02",
    "query": "Môn Toán cao cấp 1 có bao nhiêu tín chỉ?",
    "category": "curriculum",
    "expected_keywords": ["tín chỉ"],
    "expected_route": "simple"
  },
  {
    "id": "S03",
    "query": "Lịch thi kết thúc học phần học kỳ 1 khi nào?",
    "category": "schedule",
    "expected_keywords": ["thi", "học kỳ"],
    "expected_route": "simple"
  }
]
```

```json
// eval/question_sets/complex_questions.json
[
  {
    "id": "C01",
    "query": "So sánh điều kiện nhận học bổng KKHT giữa K65 và K70",
    "category": "comparison",
    "expected_keywords": ["K65", "K70", "học bổng"],
    "expected_route": "complex",
    "expected_tools": ["compare_cohorts"]
  },
  {
    "id": "C02",
    "query": "Tôi đã tích lũy đủ tín chỉ và không có môn F, tôi đủ điều kiện tốt nghiệp chưa?",
    "category": "synthesis",
    "expected_keywords": ["tốt nghiệp", "điều kiện"],
    "expected_route": "complex",
    "expected_tools": ["multi_rag_search"]
  },
  {
    "id": "C03",
    "query": "Chương trình đào tạo K70 và K68 khác nhau như thế nào?",
    "category": "comparison",
    "expected_keywords": ["K70", "K68"],
    "expected_route": "complex",
    "expected_tools": ["compare_cohorts"]
  }
]
```

> **Ghi chú**: Thêm đủ **10 câu simple** và **10 câu complex** cho kết quả evaluation có ý nghĩa thống kê.

---

## Ngày 3-4 — Script Evaluation

### `eval/evaluate.py`

```python
# eval/evaluate.py
"""
So sánh RAG v2 vs Agent trên bộ câu hỏi thực.
Chạy: python eval/evaluate.py
"""
import json
import time
import logging
from pathlib import Path
from pipeline.rag_pipeline import RAGPipeline
from config.settings import Settings

logging.basicConfig(level=logging.WARNING)  # Tắt bớt log khi eval


def load_questions(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def evaluate_answer(answer: str, expected_keywords: list[str]) -> dict:
    """Đánh giá cơ bản dựa trên keyword presence."""
    if not answer:
        return {"keyword_score": 0.0, "has_content": False}
    answer_lower = answer.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return {
        "keyword_score": found / len(expected_keywords) if expected_keywords else 0.0,
        "has_content": len(answer) > 50,
        "answer_length": len(answer)
    }


def run_evaluation():
    settings = Settings()
    pipeline = RAGPipeline(settings)

    results = {"simple": [], "complex": []}

    for category, filepath in [
        ("simple", "eval/question_sets/simple_questions.json"),
        ("complex", "eval/question_sets/complex_questions.json")
    ]:
        questions = load_questions(filepath)
        print(f"\n{'='*50}")
        print(f"Evaluating {category.upper()} questions ({len(questions)} total)")
        print('='*50)

        for q in questions:
            query = q["query"]
            expected_keywords = q.get("expected_keywords", [])
            expected_tools = q.get("expected_tools", [])

            # ── RAG v2 (baseline) ────────────────────────
            t0 = time.time()
            rag_result = pipeline.query(query)
            rag_time = time.time() - t0
            rag_eval = evaluate_answer(rag_result.get("answer", ""), expected_keywords)

            # ── Agent (new) ───────────────────────────────
            t0 = time.time()
            agent_result = pipeline.query_v3(query)
            agent_time = time.time() - t0
            agent_eval = evaluate_answer(agent_result.get("answer", ""), expected_keywords)

            # Tool correctness (chỉ cho complex)
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

            # Print inline
            winner = "AGENT" if agent_eval["keyword_score"] > rag_eval["keyword_score"] else "RAG"
            if agent_eval["keyword_score"] == rag_eval["keyword_score"]:
                winner = "TIE"
            print(f"[{q['id']}] {winner} | RAG: {rag_eval['keyword_score']:.1f} ({rag_time:.1f}s) | Agent: {agent_eval['keyword_score']:.1f} ({agent_time:.1f}s)")

    # ── Tổng hợp ─────────────────────────────────────────
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)

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

    # Save kết quả
    with open("eval/results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nResults saved to eval/results.json")


if __name__ == "__main__":
    run_evaluation()
```

### Checklist Ngày 3-4
- [ ] 10 simple + 10 complex questions trong JSON files
- [ ] `python eval/evaluate.py` chạy không lỗi
- [ ] Kết quả được save ra `eval/results.json`
- [ ] Agent keyword score cho câu complex ≥ RAG v2 score

---

## Ngày 5 — Phân tích kết quả & Báo cáo

### Template phân tích kết quả

```markdown
## Kết quả Evaluation — Agentic RAG vs RAG v2

### Simple Questions (n=10)
| Metric | RAG v2 | Agent |
|---|---|---|
| Keyword Score | X.XX | X.XX |
| Avg Latency | X.Xs | X.Xs |

**Nhận xét**: Agent không cải thiện đáng kể câu đơn giản (expected).
Latency tăng thêm ~Xs do qua Complexity Router.

### Complex Questions (n=10)
| Metric | RAG v2 | Agent |
|---|---|---|
| Keyword Score | X.XX | X.XX |
| Tool Selection Accuracy | N/A | X% |
| Avg Latency | X.Xs | X.Xs |

**Nhận xét**: Agent cải thiện rõ rệt câu phức tạp (dự kiến +20-40% keyword score).
```

### Checklist Ngày 5
- [ ] So sánh keyword scores simple vs complex
- [ ] Xác nhận: với câu simple, agent không tệ hơn RAG v2 (không regression)
- [ ] Ghi nhận: tool selection accuracy cho câu complex
- [ ] Ghi nhận: latency overhead của agent so với RAG v2
- [ ] Snapshot MongoDB `agent_traces` để có data thực cho báo cáo thesis

### Deliverable cuối Tuần 4
> ✅ MongoDB lưu đầy đủ agent traces  
> ✅ Bảng so sánh định lượng RAG v2 vs Agent  
> ✅ Kết quả evaluation chứng minh agent tốt hơn với câu phức tạp  
> ✅ Data sẵn sàng cho chương "Kết quả thực nghiệm" của thesis

---

## Checklist tổng kết toàn dự án

### Files được tạo mới
- [ ] `agent/__init__.py`
- [ ] `agent/state.py`
- [ ] `agent/tools.py`
- [ ] `agent/tool_adapters.py`
- [ ] `agent/react_agent.py`
- [ ] `agent/prompts.py`
- [ ] `agent/complexity_router.py`

### Files được chỉnh sửa
- [ ] `pipeline/rag_pipeline.py` — thêm `query_v3()`, KHÔNG sửa `query()` cũ
- [ ] `pipeline/mongo_logger.py` — thêm `log_agent_trace()`
- [ ] `api/routes/chat.py` — thêm endpoint `/api/chat/v3`
- [ ] `config/settings.py` — thêm agent settings

### Tests
- [ ] `tests/test_adapters.py` — all pass
- [ ] `tests/test_agent_mock.py` — all pass
- [ ] `tests/test_router.py` — all pass
- [ ] `tests/test_e2e.py` — all pass (cần Qdrant + LM Studio)

### Evaluation
- [ ] `eval/question_sets/simple_questions.json` — 10 câu
- [ ] `eval/question_sets/complex_questions.json` — 10 câu
- [ ] `eval/evaluate.py` — chạy được, có results
- [ ] `eval/results.json` — saved

---

*Kế hoạch này được thiết kế cho Qwen 2.5 8B · LM Studio · Qdrant · MongoDB  
Option A: Agent là layer bổ sung — câu đơn giản vẫn dùng RAG v2 pipeline cũ*
