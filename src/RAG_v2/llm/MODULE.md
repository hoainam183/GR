# Module: `llm` — Language Model Layer

## Tổng quan

Module `llm` chịu trách nhiệm **tạo ra câu trả lời cuối cùng** từ context đã được retrieve. Đây là module **tốn thời gian nhất** trong toàn bộ pipeline do phụ thuộc vào API call đến Gemini hoặc local model LM Studio. Module cũng cung cấp khả năng **tự đánh giá** (self-evaluation) câu trả lời.

---

## Cấu trúc file

```
llm/
├── __init__.py    # Factory registry: create_llm(), register_llm()
├── base.py        # BaseLLM abstract class
├── gemini.py      # GeminiLLM — Gemini via OpenAI-compatible endpoint
├── lm_studio.py   # LMStudioLLM — Local LM Studio server
├── prompts.py     # System prompts cho RAG, chitchat, self_eval modes
├── self_eval.py   # SelfEvaluator — LLM-as-judge
└── chat_model.py  # Alias/backward compatibility
```

---

## Nhiệm vụ chi tiết

### `gemini.py` — `GeminiLLM` (Provider mặc định)

**Model mặc định:** `gemini-3.1-flash-lite-preview`
**Endpoint:** `https://generativelanguage.googleapis.com/v1beta/openai/`

**3 chế độ generation:**

| Mode | System Prompt | Dùng khi |
|---|---|---|
| `"rag"` | Trợ lý học vụ ĐHBK với context tài liệu | intent == "rag" |
| `"chitchat"` | Trợ lý thân thiện, không có context | intent == "chitchat" |
| `"self_eval"` | Judge: đánh giá relevance/faithfulness | SelfEvaluator |

**Non-streaming (`generate()`):**
```python
response = gemini_client.chat.completions.create(
    model="gemini-3.1-flash-lite-preview",
    messages=build_rag_messages(query, context, history),
    temperature=0.3,
    max_tokens=1024,
)
```

**Streaming (`generate_stream()`):**
```python
stream = gemini_client.chat.completions.create(..., stream=True)
for chunk in stream:
    yield chunk.choices[0].delta.content
```

**Retry logic:** 3 lần với exponential backoff (2s, 4s) khi rate-limit.

---

### `lm_studio.py` — `LMStudioLLM`

**Dùng khi:** Deploy local, không muốn dùng Gemini API.
**Endpoint:** `http://127.0.0.1:1234/v1` (LM Studio local server)
**Model:** Qwen2.5, Llama, hoặc bất kỳ model nào được load trong LM Studio.

Cùng interface với `GeminiLLM` — swap seamlessly qua settings.

---

### `prompts.py` — System Prompts

**`build_rag_messages(query, context, history)`:**
```
[SYSTEM]
Bạn là trợ lý tư vấn học vụ của Đại học Bách Khoa Hà Nội...
Chỉ trả lời dựa trên thông tin được cung cấp...
Nếu không có thông tin, hãy nói rõ...

[USER: history turn 1]
[ASSISTANT: history turn 1]
...
[USER]
<context>
--- Văn bản: [source]
[retrieved text]
</context>

Câu hỏi: {query}
```

**`build_chitchat_messages(query, history)`:**
Prompt ngắn hơn, không có context section.

**`build_self_eval_messages(query)`:**
Prompt yêu cầu LLM output JSON với các key: `pass`, `relevance`, `faithfulness`, `completeness`, `reason`.

---

### `self_eval.py` — `SelfEvaluator`

**Nhiệm vụ:** Đánh giá chất lượng câu trả lời đã generate bằng cách dùng LLM làm "judge".

**Khi nào kích hoạt?**
```python
run_self_eval = (
    self_evaluator is not None
    and top_reranker_score < 0.72  # threshold
)
```
→ Chỉ chạy khi retrieval confidence thấp (top reranker score < 0.72).

**Output:**
```json
{
  "pass": false,
  "relevance": "good",
  "faithfulness": "partial",
  "completeness": "incomplete",
  "reason": "Câu trả lời thiếu thông tin về điều kiện GPA..."
}
```

Nếu `pass=False` → trigger **Tavily web search fallback**.

---

### `__init__.py` — LLM Factory

```python
@register_llm("gemini")
class GeminiLLM(BaseLLM): ...

@register_llm("lm_studio")
class LMStudioLLM(BaseLLM): ...

# Usage:
llm = create_llm(settings)  # settings.llm_provider = "gemini"
```

---

## Luồng generation trong RAG

```
reranked_documents + query + history
    │
    ▼
_format_context()
→ Tạo context string (budget-limited: 8000 chars tổng, 1500 chars/doc)

    │
    ▼
build_rag_messages(query, context, history)
→ Tạo message list cho API

    │
    ▼
GeminiLLM.generate() OR generate_stream()
→ API call đến Gemini

    │
    ▼
answer: str  (hoặc Generator[str] cho streaming)

    │
    ├── if self_eval và top_score < 0.72:
    │       SelfEvaluator.evaluate(query, context, answer)
    │       if not pass:
    │           TavilySearch → enhanced answer
    │
    ▼
Final answer
```

---

## LLM involvement — **CỐT LÕI CỦA MODULE**

Module `llm` chứa TẤT CẢ các LLM calls trong pipeline RAG thông thường:

| Call | Latency điển hình | Tần suất |
|---|---|---|
| `generate(mode="rag")` — answer generation | **2000-15000ms** | Mỗi query |
| `generate(mode="chitchat")` — chitchat | **500-3000ms** | Chitchat queries |
| `generate(mode="self_eval")` — judge | **500-3000ms** | ~20-30% queries |
| `generate(mode="chitchat")` — Tier-3 classify | **300-800ms** | ~5% queries |
| `generate(mode="chitchat")` — Reflection | Xem module query | Mỗi RAG query |

---

## Latency contribution

| Component | Thời gian điển hình |
|---|---|
| `generate_stream()` TTFT (Gemini) | **1000-5000ms** ⚠️ |
| `generate()` non-streaming (Gemini) | **2000-15000ms** ⚠️ |
| `SelfEvaluator.evaluate()` | **500-3000ms** (thường skip) |
| **Tổng module llm (non-streaming)** | **2000-15000ms** |
| **Tổng module llm (streaming, TTFT)** | **~1000-5000ms** |

> ⚠️ **Module `llm` là bottleneck CHÍNH của hệ thống** — chiếm 60-90% tổng latency.

---

## Optimization suggestions

| Vấn đề | Giải pháp |
|---|---|
| Generation quá chậm | Dùng `gemini-3.1-flash-lite-preview` thay `gemini-3.1-flash-lite-preview` |
| Token budget quá lớn | Giảm `max_tokens` (default 1024) |
| Self-eval add latency | Tăng `self_eval_min_top_score` để skip thường xuyên hơn |
| Context quá dài | Giảm `_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET` (hiện 8000 chars) |

---

## Recent Changes

* 2026-05-16: Cập nhật `RAG_SYSTEM_PROMPT` trong `prompts.py` để khi context tham khảo là tiếng Anh (thường gặp ở chương trình quốc tế/song ngữ), câu trả lời dịch phần cần thiết sang tiếng Việt và giữ thuật ngữ gốc trong ngoặc khi cần.
* 2026-05-06: Cập nhật `RAG_SYSTEM_PROMPT` trong `prompts.py` yêu cầu LLM ẩn nguyên bản các đường link chứa khoảng trắng (URL) vào trong văn bản theo chuẩn markdown (ví dụ `[tại đây](URL)`) và encode `%20` khoảng trắng để chống lỗi đứt link.
* 2026-05-05: Cập nhật `RAG_SYSTEM_PROMPT` trong `prompts.py` để yêu cầu LLM giữ nguyên và đưa URL (nếu có) vào trong câu trả lời thay vì rút gọn các đường link như trước.

