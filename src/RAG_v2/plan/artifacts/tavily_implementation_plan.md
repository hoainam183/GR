# Audit report — Module `tools` (Web Search Layer)

**Ngày:** 2026-05-17  
**Phạm vi:** `tools/tavily_search.py` · `pipeline/flows.py` · `agent/tool_adapters.py`  
**Kết luận chung:** Module viết tốt về mặt engineering (resilience, error handling, lifecycle). Vấn đề tập trung ở routing logic và một số lỗ hổng kiến trúc ảnh hưởng trực tiếp đến chất lượng answer.

---

## Tổng quan

| Mức độ | Số lượng | Tác động |
|:---|:---:|:---|
| P1 — Critical | 2 | Kiến trúc, ảnh hưởng toàn bộ user |
| P2 — High | 3 | Logic & data quality |
| P3 — Medium | 3 | Config, observability, UX |
| **Tổng** | **8** | |

---

## P1 — Critical

### 1. Self-eval fallback kích hoạt quá muộn

**Vấn đề:**  
Flow hiện tại yêu cầu LLM sinh answer trước, sau đó mới chạy self-eval, rồi mới gọi Tavily nếu thất bại. Đây là vấn đề hai mặt:

- Nếu LLM hallucinate nhưng answer nghe có vẻ hợp lý, `SelfEvaluator` không catch được → Tavily không bao giờ được gọi, answer sai được trả về.
- Worst-case latency: `self-eval (~2–5s)` + `Tavily API (~0.5–2s)` + `re-generate (~1–3s)` = **4–10 giây overhead** cộng thêm vào response time.

```
# Flow hiện tại (3 LLM calls worst-case)
generate() → self_eval → [fail] → tavily_search → re-generate()

# Flow đề xuất (pre-flight routing)
classify_intent() → [time-sensitive?] → tavily_search → generate_with_context()
                 → [conceptual?]     → vector_search → generate()
```

**Cách fix:**  
Thêm `_classify_time_sensitive(question: str) -> bool` dùng rule-based (regex match năm học như `202\d{2}`, từ khóa "lịch", "deadline", "thông báo", "hạn nộp"...) trước bước `generate()`. Không cần thêm LLM call. Self-eval giữ vai trò safety-net, không phải primary trigger.

---

### 2. Streaming path bỏ qua toàn bộ fallback

**Vấn đề:**  
`/chat/stream` không chạy self-eval và Tavily fallback. Nếu frontend dùng streaming là chính, toàn bộ cơ chế này gần như vô hiệu với phần lớn user. Đây là gap chất lượng answer nghiêm trọng giữa streaming và non-streaming path.

> Trích doc: *"Streaming path KHÔNG chạy self-eval/Tavily fallback — giữ UX streaming real-time."*

**Cách fix:**  
Tách Tavily enrichment ra khỏi answer generation. Với streaming: pre-fetch Tavily context *trước* khi bắt đầu stream nếu intent classifier flag query là time-sensitive, inject context vào system prompt. User vẫn thấy UX streaming, nhưng answer đã được enriched với web context.

```python
# pipeline/flows.py — stream path
async def rag_flow_stream(question, ...):
    # Pre-flight: chạy trước khi stream bắt đầu
    web_ctx = None
    if self._classify_time_sensitive(question) and self._tavily:
        web_ctx = await self._tavily_prefetch(question)

    async for chunk in self._chat_model.stream(
        question,
        context=web_ctx or vector_context,
        ...
    ):
        yield chunk
```

---

## P2 — High

### 3. EDU_DOMAINS chứa báo tin tức phổ thông

**Vấn đề:**  
`vnexpress.net`, `tuoitre.vn`, `thanhnien.vn`, `dantri.com.vn` không phải nguồn authoritative cho thông tin HUST. Các trang này đăng tin giáo dục nhưng thường không chính xác về chi tiết (deadline cụ thể, điểm chuẩn, học phí theo năm). Khi agent dùng Tier 1+2, kết quả từ báo tin tức có thể override thông tin chính thống nếu Tavily rank chúng cao hơn.

**Cách fix:**  
Tổ chức lại thành 3 tiers với mức độ tin cậy rõ ràng:

```python
# tools/tavily_search.py

HUST_OFFICIAL: list[str] = [
    "hust.edu.vn",
    "sis.hust.edu.vn",
    "ctt.hust.edu.vn",
    "ctsv.hust.edu.vn",
    "sv-ctt.hust.edu.vn",
    "soict.hust.edu.vn",
]

HUST_EXTENDED: list[str] = [
    "see.hust.edu.vn",
    "sem.hust.edu.vn",
    "fee.hust.edu.vn",
    "fme.hust.edu.vn",
    # Thêm subdomain viện/khoa khi cần
]

EDU_AUTHORITATIVE: list[str] = [
    "moet.gov.vn",   # Bộ GD-ĐT — authoritative về chính sách
    # Loại bỏ hoàn toàn các trang báo tin tức
]
```

Agent dùng `HUST_OFFICIAL + HUST_EXTENDED + EDU_AUTHORITATIVE`. Self-eval fallback dùng `HUST_OFFICIAL` only.

---

### 4. BGE threshold 100.0 là magic number chưa được calibrate

**Vấn đề:**  
BGE raw logit scores không có upper bound cố định — chúng phụ thuộc vào query length, document length, và softmax temperature. Threshold `100.0` trong `SELF_EVAL_MIN_TOP_SCORE` có thể quá cao (self-eval luôn chạy, tốn LLM call) hoặc quá thấp (self-eval luôn bị skip, chất lượng không được kiểm soát). Hiện tại không có data để biết phần trăm query thực sự skip self-eval.

**Cách fix:**  
1. Log distribution của `top_reranker_score` trong production trong 1–2 tuần.
2. Vẽ histogram → chọn threshold tại percentile 85–90 (skip self-eval khi retrieval rõ ràng tốt).
3. Expose metric `reranker_score_p50`, `reranker_score_p90` vào observability dashboard.
4. Đặt threshold theo percentile thực tế thay vì hardcode giá trị tuyệt đối.

---

### 5. Không có query transformation trước khi gọi Tavily

**Vấn đề:**  
Raw conversational query được truyền thẳng vào Tavily. Query kiểu `"em muốn hỏi về lịch đăng ký học phần học kỳ này"` cho kết quả kém hơn nhiều so với `"lịch đăng ký học phần HUST 20261 tháng 5 2026"`.

**Cách fix:**  

```python
# tools/tavily_search.py hoặc pipeline/flows.py

def _build_search_query(question: str, semester_hint: str = "") -> str:
    """Rule-based query rewrite — không tốn LLM call."""
    query = question.strip("?!. ")

    # Đảm bảo context HUST luôn có trong query
    if "hust" not in query.lower() and "bách khoa" not in query.lower():
        query = f"HUST {query}"

    # Thêm semester nếu không có trong query gốc
    if semester_hint and semester_hint not in query:
        query = f"{query} {semester_hint}"

    return query
```

---

## P3 — Medium

### 6. `tavily_fallback_enabled` flag không gate logic thực sự

**Vấn đề:**  
Khi operator set `TAVILY_FALLBACK_ENABLED=false`, họ kỳ vọng Tavily không chạy. Nhưng fallback vẫn trigger nếu `self_eval_enabled=true` và API key hợp lệ. Flag này hiện chỉ dùng cho logging/metrics, không được check trong `flows.py`. Đây là footgun khi team mở rộng.

**Cách fix:**  

```python
# pipeline/flows.py — _tavily_fallback() caller
if (
    self._tavily is not None
    and self._settings.tavily_fallback_enabled   # ← thêm check này
    and self._settings.self_eval_enabled
):
    result = await self._tavily_fallback(question, context)
```

---

### 7. Không có result cache — Tavily credits tốn cho duplicate queries

**Vấn đề:**  
Cùng câu hỏi hỏi lại nhiều lần (phổ biến với câu hỏi về lịch học, deadline) → mỗi lần gọi Tavily API tốn 1 credit + thêm latency.

**Cách fix:**  

```python
# tools/tavily_search.py
from cachetools import TTLCache

_search_cache: TTLCache = TTLCache(maxsize=200, ttl=3600)  # Cache 1 giờ

def search(self, query: str, include_domains=None, **kwargs) -> dict:
    cache_key = f"{query}|{sorted(include_domains or [])}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    result = self._do_search(query, include_domains=include_domains, **kwargs)
    _search_cache[cache_key] = result
    return result
```

TTL 1 giờ phù hợp với thông tin lịch học (thay đổi theo ngày, không theo giây). Với free tier 1,000 credits/tháng, cache tiết kiệm đáng kể trong giờ cao điểm.

---

### 8. Agent tool description quá vague

**Vấn đề:**  
Description hiện tại không cung cấp đủ signal để agent biết *khi nào không nên* gọi `web_search`, dẫn đến over-calling hoặc under-calling tool.

**Description hiện tại:**
```
"Tìm thông tin mới nhất trên internet qua Tavily.
Chỉ dùng khi database không có kết quả hoặc cần thông tin rất mới."
```

**Description đề xuất:**
```python
description=(
    "Tìm thông tin HUST real-time từ web (hust.edu.vn và nguồn giáo dục chính thống). "
    "Dùng khi query chứa: năm học cụ thể (20261, 20262...), deadline/thời hạn, "
    "lịch thi/đăng ký học phần, thông báo mới nhất, hoặc khi rag_search trả về "
    "score thấp hoặc không có kết quả liên quan. "
    "KHÔNG dùng cho câu hỏi khái niệm, quy trình chung, hoặc thông tin "
    "ổn định đã có trong database nội bộ."
)
```

---

## Những gì đang tốt — không cần thay đổi

| Component | Đánh giá |
|:---|:---|
| Retry logic với exponential backoff | Tốt — 1s → 2s → 4s, tách biệt auth error vs transient error |
| Shared instance qua `RetrievalService` | Tốt — không tạo instance thừa, lifecycle rõ ràng |
| Key validation (reject placeholder) | Tốt — fail fast thay vì silent error |
| Error handling graceful degrade | Tốt — mọi lỗi đều return answer gốc, không crash |
| Observability timings | Tốt — `tavily_search`, `tavily_generate`, `tavily_total` đầy đủ |
| Lazy import Tavily package | Tốt — không block startup nếu không cài |
| Domain URL normalization | Tốt — strip path trước khi gửi API call |

---

## Thứ tự ưu tiên thực hiện

```
Tuần 1 (Critical):
  [1] Thêm _classify_time_sensitive() — rule-based, không tốn LLM call
  [2] Pre-fetch Tavily trước stream nếu query time-sensitive

Tuần 2 (High):
  [3] Tổ chức lại domain tiers, loại báo tin tức khỏi EDU_DOMAINS
  [4] Thêm _build_search_query() rewrite function
  [5] Log reranker score distribution → calibrate threshold

Tuần 3 (Medium):
  [6] Gate tavily_fallback_enabled flag trong flows.py
  [7] Thêm TTL cache cho Tavily results
  [8] Cập nhật agent tool description
```