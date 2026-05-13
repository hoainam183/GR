# Bug Report: Agent không retrieval được điều kiện tốt nghiệp

> Phát hiện qua test thực tế — so sánh 2 conversation trace

---

## Tóm tắt

Vector search và embedding hoạt động đúng. Bug nằm ở **query được đưa vào `rag_search`
bị nhiễu bởi mã sinh viên** do reflection inject identifier cá nhân vào tool call.

---

## Bằng chứng

| | Conversation cũ (Agent) | Conversation mới (RAG) |
|---|---|---|
| Query gốc | "tôi có đủ điều kiện tốt nghiệp không?" | "điều kiện tốt nghiệp" |
| Reflection output | "Sinh viên IT-E6, KK67, **Mã SV 20225653** có đủ ĐK tốt nghiệp không?" | "Điều kiện tốt nghiệp là gì?" |
| Retrieval kết quả | Không tìm thấy ✗ | Tìm thấy đầy đủ ✓ |
| Collection | quy_dinh | quy_dinh (score: 0.700) |
| Latency | 54.79s | 11.33s |

Cùng collection `quy_dinh`, cùng dữ liệu đã embed — nhưng kết quả trái ngược nhau.

---

## Root Cause

Reflection module inject `Mã SV 20225653` vào query trước khi agent gọi tool:

```
# Query thực sự được đưa vào rag_search:
"Sinh viên IT-E6, KK67, Mã SV 20225653 có đủ điều kiện tốt nghiệp không?"
```

Chuỗi số `20225653` không xuất hiện trong bất kỳ document nào trong `quy_dinh`.
Vector embedding của query bị kéo lệch khỏi vùng semantic của "điều kiện tốt nghiệp"
vì model tìm kiếm document liên quan đến mã số sinh viên cụ thể — không tồn tại trong DB.

---

## Phân tích code

`_rag_search` trong `tool_adapters.py` có bước làm sạch query:

```python
raw_query = query.strip()
major_codes = extract_major_codes(raw_query)

retrieval_query = raw_query
if effective_resolved_major or len(major_codes) <= 1:
    retrieval_query = strip_major_from_query_for_retrieval(
        raw_query,
        resolved_major=effective_resolved_major,
    )
```

`strip_major_from_query_for_retrieval` chỉ xử lý:
- Mã ngành: `IT-E6`, `IT-E7`, `MI-E10`...
- Mã khóa: `K65`, `K67`, `KK67`...

**Không xử lý:**
- Mã sinh viên 8 chữ số: `20225653`
- Prefix nhận dạng: `Mã SV`, `MSSV`, `sinh viên mã`
- Tên sinh viên (nếu có)

Kết quả: `retrieval_query` sau khi strip vẫn còn `20225653` gây noise embedding.

---

## Các vấn đề liên quan phát hiện thêm

### Vấn đề 1 — Latency 54.79s cho 1 tool call

```
Agent Total:  54.80s
Reflection:    1.44s   ← OK
History Load:  0.01s   ← OK
Routing:       0.00s   ← OK
→ ~53s nằm trong LLM call + rag_search
```

Khả năng cao nhất: LM Studio cold start — Qwen 8B chưa được load vào VRAM
khi query đầu tiên đến. Cần warm-up trước khi nhận request.

### Vấn đề 2 — Agent dừng sau 1 tool call thất bại

Agent gọi `rag_search` với query bị nhiễu → không tìm thấy → dừng luôn.
Đáng lẽ phải fallback: thử lại với query đã rút gọn về từ khóa cốt lõi.

### Vấn đề 3 — Reflection context leaking (Query 3: "môn ITSS")

```
Query gốc:   "môn ITSS"
Reflected:   "Điều kiện tốt nghiệp đối với môn ITSS trong chương trình IT-E6 là gì?"
```

Reflection inject intent từ query trước ("điều kiện tốt nghiệp") vào query mới,
làm lệch hướng retrieval. Kết quả: không tìm thấy thông tin về ITSS.

---

## Hướng fix

### Fix 1 — Strip personal identifiers (BẮT BUỘC)

Fix ở tầng infrastructure, không phụ thuộc LLM behavior.

```python
# tool_adapters.py — thêm vào đầu file

import re

_STUDENT_ID_RE = re.compile(r'\b\d{8}\b')
_STUDENT_ID_PREFIX_RE = re.compile(
    r'(mã\s*sv|mssv|sinh\s*viên\s*mã?)\s*:?\s*\d+',
    re.IGNORECASE
)

def strip_personal_identifiers(query: str) -> str:
    """Xóa mã sinh viên và các identifier cá nhân khỏi retrieval query."""
    q = _STUDENT_ID_PREFIX_RE.sub('', query)
    q = _STUDENT_ID_RE.sub('', q)
    q = re.sub(r',\s*,', ',', q)
    q = re.sub(r'\s{2,}', ' ', q).strip().strip(',').strip()
    return q
```

Tích hợp vào `_rag_search`:

```python
def _rag_search(query, collection, ...):
    raw_query = query.strip()
    raw_query = strip_personal_identifiers(raw_query)   # ← thêm dòng này
    major_codes = extract_major_codes(raw_query)
    ...
```

### Fix 2 — System prompt hướng dẫn query formulation (DEFENSE-IN-DEPTH)

Thêm vào `AGENT_SYSTEM_PROMPT` trong `prompts.py`:

```
- Khi gọi rag_search: rút gọn thành từ khóa cốt lõi.
  KHÔNG đưa mã sinh viên, tên sinh viên vào query.
  ✓ Đúng: "điều kiện tốt nghiệp IT-E6"
  ✗ Sai:  "SV 20225653 IT-E6 có đủ điều kiện tốt nghiệp không?"
```

### Fix 3 — Agent retry khi tool trả về không có kết quả

Khi `rag_search` trả về `[Khong tim thay...]`, agent nên thử lại
với query rút gọn thay vì dừng:

```python
# Trong _agent_node, thêm vào system message khi detect empty result:
if "[Khong tim thay" in last_tool_result:
    retry_hint = SystemMessage(
        content="Kết quả trống. Hãy thử lại với query ngắn hơn, "
                "chỉ giữ từ khóa cốt lõi, bỏ thông tin cá nhân."
    )
    messages.append(retry_hint)
```

### Fix 4 — Reflection chỉ inject user profile, không inject intent

Reflection module cần phân biệt:
- **User profile** (ngành, khóa, mã SV): inject vào `user_context`, KHÔNG inject vào query
- **Query intent**: lấy từ query hiện tại, không carry over từ query trước

```python
# Reflection output nên là:
"Điều kiện tốt nghiệp"   # chỉ core intent, không có identifier

# user_context được truyền riêng:
user_context = {"cohort": "K67", "major_code": "IT-E6", "student_id": "20225653"}
```

### Fix 5 — LM Studio warm-up

```python
# Khi khởi động server, gửi 1 dummy request để load model vào VRAM
async def warmup_llm():
    await asyncio.sleep(2)   # đợi server ready
    try:
        agent._llm.invoke([HumanMessage(content="hello")])
        logger.info("[Warmup] LLM warmed up successfully")
    except Exception as e:
        logger.warning("[Warmup] Failed: %s", e)

# Trong FastAPI startup event:
@app.on_event("startup")
async def startup():
    asyncio.create_task(warmup_llm())
```

---

## Test cases bổ sung

### TC-STRIP01: Personal identifier bị strip trước khi embed

```python
from tool_adapters import strip_personal_identifiers

cases = [
    (
        "Sinh viên IT-E6, KK67, Mã SV 20225653 có đủ điều kiện tốt nghiệp không?",
        "20225653",   # phải bị xóa
    ),
    (
        "MSSV: 20225653 học bổng KKHT yêu cầu gì?",
        "20225653",
    ),
    (
        "mã sv 20215678 có được miễn học phí không?",
        "20215678",
    ),
]

for raw, identifier in cases:
    stripped = strip_personal_identifiers(raw)
    assert identifier not in stripped, f"Identifier not stripped: '{stripped}'"
    assert len(stripped.strip()) > 5, f"Query quá ngắn sau strip: '{stripped}'"
    print(f"OK: '{raw[:50]}...' → '{stripped}'")
```

### TC-STRIP02: Mã ngành và khóa không bị strip nhầm

```python
cases_preserve = [
    "điều kiện tốt nghiệp IT-E6 K67",
    "học bổng KKHT K65 và K70",
    "chương trình đào tạo IT-E7",
]
for q in cases_preserve:
    stripped = strip_personal_identifiers(q)
    assert stripped == q, f"Stripped quá nhiều: '{q}' → '{stripped}'"
```

### TC-STRIP03: End-to-end — agent retrieval thành công sau fix

```python
# Mock: agent được gọi với query có mã sinh viên
state = agent.run(
    query="tôi có đủ điều kiện tốt nghiệp không?",
    complexity_subtype="personal_check",
    user_context={
        "student_id": "20225653",
        "cohort": "K67",
        "major_code": "IT-E6",
    }
)

# Sau khi fix: phải tìm được thông tin điều kiện tốt nghiệp
assert state.final_answer is not None
assert "không tìm thấy" not in state.final_answer.lower()
# Phải có ít nhất 1 tool result có nội dung thực
assert any(
    len(tr.result) > 100 and not tr.result.startswith("[Loi")
    for tr in state.tool_results
), "Không có tool result hợp lệ — query vẫn bị nhiễu"
```

### TC-REFLECT01: Reflection không carry over intent từ query trước

```python
# Simulate conversation với 2 queries
history = [
    {"role": "user", "content": "điều kiện tốt nghiệp"},
    {"role": "assistant", "content": "Điều kiện tốt nghiệp bao gồm..."},
]

state = agent.run(
    query="môn ITSS",
    history=history,
    user_context={"major_code": "IT-E6", "cohort": "K67"},
)

# Tool call của agent không được chứa "điều kiện tốt nghiệp"
for tr in state.tool_results:
    args_query = tr.args.get("query", "").lower()
    assert "điều kiện tốt nghiệp" not in args_query, (
        f"Reflection leaked intent from previous query: '{args_query}'"
    )
```

---

## Checklist fix

```
[ ] Fix 1: Implement strip_personal_identifiers() trong tool_adapters.py
[ ] Fix 1: Tích hợp vào _rag_search() trước extract_major_codes()
[ ] Fix 2: Cập nhật AGENT_SYSTEM_PROMPT với hướng dẫn query formulation
[ ] Fix 3: Agent retry logic khi tool trả về [Khong tim thay...]
[ ] Fix 4: Reflection chỉ inject user profile, không carry over query intent
[ ] Fix 5: LM Studio warm-up trong FastAPI startup event

[ ] TC-STRIP01: Strip mã sinh viên 8 chữ số
[ ] TC-STRIP02: Không strip nhầm mã ngành và khóa
[ ] TC-STRIP03: End-to-end agent retrieval thành công
[ ] TC-REFLECT01: Reflection không leak intent từ query trước
```

---

## Thứ tự ưu tiên

```
Ngay lập tức:  Fix 1 (strip_personal_identifiers) — 1 giờ implement, impact cao nhất
Tiếp theo:     Fix 2 (system prompt) — 15 phút, defense-in-depth
               Fix 5 (warm-up) — 30 phút, fix UX latency cold start
Sau đó:        Fix 4 (reflection) — cần hiểu rõ reflection module trước
               Fix 3 (retry logic) — cần test kỹ để tránh infinite retry
```