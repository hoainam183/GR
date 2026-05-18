# Phân Tích Chiến Lược Web Search — RAG Fallback & Agent Tool

> **Scope:** `flows.py`, `tool_adapters.py`, `react_agent.py`, `tavily_search.py`, `settings.py`  
> **Ngày phân tích:** 2025

---

## 1. Tổng Quan Kiến Trúc

Hệ thống hiện có **hai pipeline web search độc lập**:

| Pipeline | Trigger | File chính | Mục đích |
|---|---|---|---|
| **RAG Fallback** (`rag_flow`) | Vector DB không đủ context | `flows.py` | Augment context trước/sau generation |
| **Agent Web Search Tool** | Agent quyết định gọi tool | `tool_adapters.py`, `react_agent.py` | Tool call trong ReAct loop |

Cả hai đều dùng Tavily làm backend, nhưng có config và xử lý kết quả **hoàn toàn khác nhau**.

---

## 2. Điểm Yếu — Phân Tích Chi Tiết

### 2.1 Recall quá thấp: `tavily_max_results = 3`

**Vị trí:** `settings.py:159`, `flows.py:1425`, `flows.py:2418`, `tool_adapters.py:579`

**Vấn đề:**  
Với chỉ 3 documents từ Tavily, nếu top-3 results không relevant (do keyword mismatch, SEO noise, hoặc domain bias), LLM nhận context kém mà không có cơ chế fallback thêm.

```
Query: "điều kiện xét tuyển thẳng ngành CNTT 2024"
Tavily top-3:
  [1] Trang tổng quan tuyển sinh (không có điều kiện cụ thể)
  [2] Tin tức unrelated từ domain HUST
  [3] Trang 2022 — stale data

→ LLM trả lời sai hoặc hallucinate, dù trang chính xác nằm ở result #5
```

**Hệ quả kép:**  
Vì không có reranker, 3 docs này được đưa thẳng vào context mà không qua bộ lọc semantic. Một doc kém chất lượng chiếm 1/3 context window dành cho web.

---

### 2.2 Content truncation 500 chars — quá ngắn cho nội dung thực tế

**Vị trí:** `tool_adapters.py:773`

```python
# Hiện tại
content[:500]  # ≈ 2–3 câu
```

**Vấn đề:**  
500 ký tự không đủ cho bất kỳ thông tin có cấu trúc nào — điều kiện xét tuyển, quy trình đăng ký, danh sách học phí, v.v. LLM thấy phần đầu câu rồi bị cắt đứt, dễ dẫn đến hallucination để "hoàn thiện" thông tin.

```
Nội dung gốc (1200 chars):
"Điều kiện xét tuyển thẳng bao gồm: (1) Học sinh giỏi cấp tỉnh/thành phố trở lên;
(2) Điểm thi THPT ≥ 27; (3) Hạnh kiểm Tốt toàn bộ lớp 10–12; (4) Không có môn
dưới 6.5; (5) Nộp hồ sơ trước ngày..."

Sau truncate 500 chars:
"Điều kiện xét tuyển thẳng bao gồm: (1) Học sinh giỏi cấp tỉnh/thành phố trở lên;
(2) Điểm thi THPT ≥ 27; (3) Hạnh ki..."

→ LLM chỉ thấy 2/5 điều kiện, có thể bịa điều kiện (4) và (5)
```

---

### 2.3 Bottleneck kép: truncation + `agent_tool_result_limit = 3000`

**Vị trí:** `react_agent.py:412`, `settings.py:92`

**Vấn đề:**  
Hai giới hạn này không được thiết kế phối hợp với nhau:

```
Budget thực tế của 3 results:
  agent_tool_result_limit = 3000 chars (toàn bộ ToolMessage)
  Metadata overhead (title + url + separator) ≈ 100–150 chars/result × 3 = ~400 chars
  Còn lại cho content: ~2600 chars → ~867 chars/result

→ Tăng content[:500] lên content[:1000] KHÔNG có tác dụng
   vì bị cap lại ở agent_tool_result_limit trước khi tới LLM
```

Hai tham số này cần được **tune cùng nhau** theo công thức:

```
agent_tool_result_limit ≥ (content_per_result + metadata_overhead) × num_results
```

---

### 2.4 Không có validity filter và freshness check

**Vị trí:** `tool_adapters.py` (dedup logic), `flows.py:2329`

**Vấn đề:**  
Hiện tại chỉ có:
- Dedup theo `url/id/title` (structural dedup)
- Bỏ item không có `title/content` (null check)
- Domain whitelist `HUST_OFFICIAL_DOMAINS`

**Thiếu:**

| Filter | Tác động nếu thiếu |
|---|---|
| Semantic similarity threshold | Doc không liên quan vẫn vào context |
| Freshness filter (năm/ngày) | Trang 2020–2022 trả lời câu hỏi về 2024 |
| Semantic dedup | Mirror sites / cached pages trùng nội dung chiếm nhiều slots |
| Low-quality signal | Trang index, sitemap, error page lọt vào |

---

### 2.5 `web_context_override` prepend không có source hierarchy

**Vị trí:** `flows.py:1497`, `flows.py:1526`

```python
# Hiện tại
full_context = web_context_override + "\n" + vector_db_context
```

**Vấn đề:**  
LLM không có signal để phân biệt:
- Web context: fresh hơn nhưng ít curated, có thể có noise
- Vector DB context: curated hơn nhưng có thể stale

Khi hai nguồn mâu thuẫn nhau (ví dụ học phí năm 2022 vs 2024), LLM không biết tin nguồn nào, thường chọn theo position bias (phần đầu được ưu tiên hơn).

---

### 2.6 Post-generation fallback thiếu early-exit guard

**Vị trí:** `flows.py:2498`

**Vấn đề:**  
Post-generation fallback gọi LLM lại với `context=web_context`, nhưng không kiểm tra:
- Web search có trả về context có chất lượng không?
- Score/confidence của web results có đủ threshold không?

Nếu Tavily trả về kết quả kém (low relevance score, empty content), pipeline vẫn trigger thêm một LLM call — tốn token và latency mà không cải thiện chất lượng.

---

## 3. Ma Trận Rủi Ro

| Điểm yếu | Xác suất xảy ra | Mức độ ảnh hưởng | Risk Score |
|---|---|---|---|
| Content truncation 500 chars | Cao | Cao (hallucination) | 🔴 9/10 |
| Bottleneck kép truncation + cap | Cao | Cao | 🔴 8/10 |
| Recall thấp (max_results=3) | Trung bình | Cao | 🔴 7/10 |
| Không có freshness filter | Trung bình | Trung bình | 🟡 5/10 |
| Thiếu source hierarchy | Trung bình | Trung bình | 🟡 5/10 |
| Post-gen fallback không có guard | Thấp | Thấp (chi phí) | 🟢 3/10 |

---

## 4. Hướng Phát Triển

### 4.1 Tăng recall + thêm reranker (Priority: HIGH)

**Thay đổi config:**

```python
# settings.py
TAVILY_MAX_RESULTS = 8  # tăng từ 3 lên 8 để có candidate pool lớn hơn
TAVILY_RERANK_TOP_K = 3  # chỉ đưa top-3 sau rerank vào LLM
```

**Thêm reranker sau Tavily:**

```python
# flows.py — sau khi nhận kết quả từ Tavily
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_results(query: str, results: list[dict], top_k: int = 3) -> list[dict]:
    pairs = [(query, r.get("content", "")) for r in results]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
    return [r for _, r in ranked[:top_k]]
```

**Trade-off:** Thêm ~50–100ms latency cho reranking. Có thể dùng lightweight model như `ms-marco-MiniLM-L-6-v2` để giảm latency.

---

### 4.2 Tune truncation + agent_tool_result_limit phối hợp (Priority: HIGH)

```python
# settings.py — tune cùng nhau
AGENT_TOOL_CONTENT_PER_RESULT = 1500   # tăng từ 500
AGENT_TOOL_NUM_RESULTS = 3
AGENT_TOOL_METADATA_OVERHEAD = 150     # title + url + separator
AGENT_TOOL_RESULT_LIMIT = (
    AGENT_TOOL_CONTENT_PER_RESULT + AGENT_TOOL_METADATA_OVERHEAD
) * AGENT_TOOL_NUM_RESULTS  # = 4950, tăng từ 3000

# tool_adapters.py
content[:AGENT_TOOL_CONTENT_PER_RESULT]
```

**Công thức tổng quát:**

```
result_limit = (content_chars + metadata_chars) × num_results × safety_factor(1.1)
```

---

### 4.3 Thêm freshness và validity filter (Priority: MEDIUM)

```python
# tavily_search.py — thêm vào _format_context() hoặc post-processing

from datetime import datetime
import re

def _filter_results(
    results: list[dict],
    query_year: int | None = None,
    min_content_length: int = 100,
    similarity_threshold: float = 0.3,
) -> list[dict]:
    filtered = []
    for r in results:
        content = r.get("content", "")
        
        # 1. Bỏ content quá ngắn (likely index/error pages)
        if len(content) < min_content_length:
            continue
        
        # 2. Freshness filter — nếu query có năm cụ thể
        if query_year:
            years_in_content = re.findall(r'\b(20\d{2})\b', content)
            if years_in_content:
                max_year = max(int(y) for y in years_in_content)
                if max_year < query_year - 1:  # cho phép lệch 1 năm
                    continue
        
        # 3. Score threshold từ Tavily (nếu có)
        if r.get("score", 1.0) < similarity_threshold:
            continue
        
        filtered.append(r)
    
    return filtered
```

---

### 4.4 Source hierarchy trong context (Priority: MEDIUM)

```python
# flows.py — thay vì prepend đơn giản

def build_full_context(
    web_context: str,
    vector_db_context: str,
    web_freshness_note: str = "",
) -> str:
    return f"""## Nguồn Web (ưu tiên cho thông tin thời gian thực{', ' + web_freshness_note if web_freshness_note else ''})
{web_context}

## Nguồn Cơ Sở Dữ Liệu Nội Bộ (ưu tiên cho thông tin được kiểm duyệt)
{vector_db_context}

Lưu ý: Nếu hai nguồn mâu thuẫn nhau về thời gian (năm học, học phí, quy định), 
ưu tiên nguồn Web. Nếu mâu thuẫn về tính chính xác, ưu tiên nguồn Nội Bộ."""
```

---

### 4.5 Early-exit guard cho post-generation fallback (Priority: LOW)

```python
# flows.py:2498 — thêm quality check trước khi trigger fallback

MIN_WEB_CONTEXT_LENGTH = 200  # chars
MIN_TAVILY_SCORE = 0.4

def should_trigger_post_gen_fallback(web_results: list[dict]) -> bool:
    if not web_results:
        return False
    
    # Kiểm tra có ít nhất 1 result đủ chất lượng
    has_quality_result = any(
        len(r.get("content", "")) >= MIN_WEB_CONTEXT_LENGTH
        and r.get("score", 0) >= MIN_TAVILY_SCORE
        for r in web_results
    )
    
    return has_quality_result
```

---

### 4.6 Roadmap ưu tiên

```
Phase 1 — Quick Wins (1–2 ngày)
├── [HIGH] Tăng content[:500] → content[:1500]
├── [HIGH] Tune agent_tool_result_limit từ 3000 → 5000
└── [HIGH] Tăng tavily_max_results từ 3 → 8

Phase 2 — Quality Improvement (1 tuần)
├── [HIGH] Tích hợp CrossEncoder reranker (top-8 → top-3)
├── [MEDIUM] Thêm freshness + validity filter
└── [MEDIUM] Source hierarchy trong context string

Phase 3 — Robustness (2–3 tuần)
├── [LOW] Early-exit guard cho post-gen fallback
├── [LOW] Monitoring/logging chất lượng web context (avg score, avg length)
└── [LOW] A/B test reranker vs. no-reranker trên eval set
```

---

## 5. Tóm Tắt

| # | Điểm yếu | Fix ngắn hạn | Fix dài hạn |
|---|---|---|---|
| 1 | Recall thấp (3 docs) | Tăng lên 5–8 | Thêm reranker |
| 2 | Truncation 500 chars | Tăng lên 1500 | Tune cùng result_limit |
| 3 | Bottleneck kép | Đồng bộ 2 tham số | Công thức dynamic |
| 4 | Không có validity filter | Filter by content length | Semantic threshold + freshness |
| 5 | Thiếu source hierarchy | Thêm section headers | Explicit trust scoring |
| 6 | Post-gen fallback tốn kém | Quality threshold check | Confidence-based routing |

**Ưu tiên tổng thể:** Fix #2 và #3 trước — effort thấp, impact cao nhất. Sau đó #1 + reranker để cải thiện recall-precision. #4, #5, #6 là polish layer sau khi baseline ổn định.