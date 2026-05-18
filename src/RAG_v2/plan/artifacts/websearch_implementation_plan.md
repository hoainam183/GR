# Cải Thiện Tavily Web Search — Implementation Plan (Final)

## Mục Tiêu

Cải thiện chất lượng web search fallback trong RAG pipeline: **tăng recall, bỏ bottleneck truncation, thêm result filtering, cải thiện source hierarchy**, và thêm observability. Tất cả thay đổi đã được cross-check với source code thực tế.

## Quyết Định Đã Xác Nhận

| Quyết định | Giá trị |
|---|---|
| `tavily_max_results` | `5` (fetch 5, filter/display top 3) |
| CrossEncoder reranker | ❌ Bỏ — dùng lightweight filter thay thế |
| `agent_search_result_char_limit` | Tăng `700` → `1200` (RAG results) |
| Web search content limit | Tăng `500` → `1500` (web results) |
| `agent_tool_result_limit` | Tăng `3000` → `5000` |

---

## Proposed Changes

### Phase 1 — Quick Wins (config + hardcode fixes)

---

#### [MODIFY] [settings.py](file:///d:/GR/src/RAG_v2/config/settings.py)

**3 thay đổi:**

**1a. Tăng `agent_tool_result_limit`** (line 92)

```diff
-    agent_tool_result_limit: int = 3000  # max chars per ToolMessage
+    agent_tool_result_limit: int = 5000  # max chars per ToolMessage (tăng từ 3000 để chứa web results dài hơn)
```

**1b. Tăng `agent_search_result_char_limit`** (line 138)

```diff
-    agent_search_result_char_limit: int = 700
+    agent_search_result_char_limit: int = 1200  # tăng từ 700 để giảm truncation cho RAG results
```

**1c. Thay đổi `tavily_max_results` và thêm 2 config mới** (lines 158-164)

```diff
     tavily_fallback_enabled: bool = False
     tavily_search_depth: str = "basic"    # basic (1 credit) | advanced (2 credits)
-    tavily_max_results: int = 3           # results per search
+    tavily_max_results: int = 5           # fetch pool size (filter xuống web_result_count)
+    tavily_web_content_char_limit: int = 1500  # per-result content char limit cho web results
+    tavily_web_result_count: int = 3      # số results giữ lại sau filter (≤ max_results)
     web_fallback_dynamic_collections: List[str] = ["kehoach"]
     web_fallback_on_dynamic: bool = True
     web_fallback_on_no_info: bool = True
     tavily_cache_ttl_seconds: int = 3600
     tavily_cache_maxsize: int = 200
```

> [!NOTE]
> **Budget analysis (agent path):**
> ```
> Mỗi web result: ~1500 content + ~150 metadata = ~1650 chars
> 3 results × 1650 = ~4950 chars
> agent_tool_result_limit = 5000 → vừa đủ
> 
> Mỗi RAG result: ~1200 content + ~100 metadata = ~1300 chars
> 4 results × 1300 = ~5200 → bị trim nhẹ ở cuối (chấp nhận được)
> ```

---

#### [MODIFY] [tool_adapters.py](file:///d:/GR/src/RAG_v2/agent/tool_adapters.py)

**2 thay đổi trong `_format_web_results()`:**

**2a. Thay hardcoded `all_results[:3]` và `content[:500]`** (lines 772-777)

Trước ([lines 772-777](file:///d:/GR/src/RAG_v2/agent/tool_adapters.py#L772-L777)):
```python
    chunks: list[str] = []
    for index, item in enumerate(all_results[:3], 1):
        title = str(item.get("title", "")).strip() or f"Ket qua {index}"
        content = " ".join(str(item.get("content", "")).split())
        if len(content) > 500:
            content = content[:500].rstrip() + "..."
```

Sau:
```python
    runtime = _get_runtime()
    web_count = int(getattr(runtime.settings, "tavily_web_result_count", 3) or 3)
    web_char_limit = int(getattr(runtime.settings, "tavily_web_content_char_limit", 1500) or 1500)

    chunks: list[str] = []
    for index, item in enumerate(all_results[:web_count], 1):
        title = str(item.get("title", "")).strip() or f"Ket qua {index}"
        content = " ".join(str(item.get("content", "")).split())
        if len(content) > web_char_limit:
            content = content[:web_char_limit].rstrip() + "..."
```

> [!IMPORTANT]
> `_format_web_results()` là function riêng biệt khỏi `_format_search_results()`. `_format_search_results()` đã dùng `agent_search_result_char_limit` config (line 689), nhưng `_format_web_results()` hardcode `500` và `3`. Thay đổi này chỉ fix `_format_web_results()`.

---

### Phase 2 — Result Filtering + Source Hierarchy

---

#### [MODIFY] [tavily_search.py](file:///d:/GR/src/RAG_v2/tools/tavily_search.py)

**3 thay đổi:**

**3a. Parse `score` field trong `_parse_results()`** (lines 381-393)

Trước ([lines 381-393](file:///d:/GR/src/RAG_v2/tools/tavily_search.py#L381-L393)):
```python
    @staticmethod
    def _parse_results(response: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract structured results from the raw Tavily response."""
        parsed: List[Dict[str, str]] = []
        for item in response.get("results", []):
            parsed.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                }
            )
        return parsed
```

Sau:
```python
    @staticmethod
    def _parse_results(response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract structured results from the raw Tavily response."""
        parsed: List[Dict[str, Any]] = []
        for item in response.get("results", []):
            parsed.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": float(item.get("score", 0.0) or 0.0),
                }
            )
        return parsed
```

**3b. Thêm method `filter_results()` vào class `TavilySearchTool`** (sau `_parse_results`, trước `_format_context`)

```python
    @staticmethod
    def filter_results(
        results: List[Dict[str, Any]],
        *,
        min_content_length: int = 100,
        min_score: float = 0.0,
        query_year: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Filter out low-quality or stale web results.

        Args:
            results: Parsed result list from ``_parse_results()``.
            min_content_length: Drop results with content shorter than this.
            min_score: Drop results with Tavily relevance score below this.
            query_year: If set, drop results whose content only mentions
                years more than 1 year older than this.

        Returns:
            Filtered list (may be empty).
        """
        import re as _re

        filtered: List[Dict[str, Any]] = []
        for r in results:
            content = r.get("content", "")

            # 1. Drop empty / ultra-short results (index pages, error pages)
            if len(content) < min_content_length:
                continue

            # 2. Score threshold (when Tavily provides scores)
            if float(r.get("score", 1.0) or 1.0) < min_score:
                continue

            # 3. Freshness: if query mentions a year, drop 2+ year old results
            if query_year:
                years_in_content = _re.findall(r'\b(20\d{2})\b', content)
                if years_in_content:
                    max_year = max(int(y) for y in years_in_content)
                    if max_year < query_year - 1:
                        continue

            filtered.append(r)

        return filtered
```

**3c. Tích hợp `filter_results()` vào `search()` method** (sau line 252, trước format)

Trước ([lines 252-253](file:///d:/GR/src/RAG_v2/tools/tavily_search.py#L252-L253)):
```python
                results = self._parse_results(response)
                context = self._format_context(results)
```

Sau:
```python
                results = self._parse_results(response)
                raw_count = len(results)
                results = self.filter_results(
                    results,
                    min_content_length=100,
                )
                if raw_count != len(results):
                    logger.info(
                        "Tavily filter: %d → %d results",
                        raw_count, len(results),
                    )
                context = self._format_context(results)
```

---

#### [MODIFY] [flows.py](file:///d:/GR/src/RAG_v2/pipeline/flows.py)

**2 thay đổi:**

**4a. Source hierarchy cho web context prepend** (lines 1497-1502)

Trước ([lines 1497-1502](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L1497-L1502)):
```python
    if web_context_override:
        context = (
            f"{web_context_override}\n\n---\n\n{context}"
            if context
            else web_context_override
        )
```

Sau:
```python
    if web_context_override:
        if context:
            context = (
                f"## Nguồn Web (thông tin mới nhất từ trang chính thức HUST)\n"
                f"{web_context_override}\n\n---\n\n"
                f"## Nguồn Cơ Sở Dữ Liệu Nội Bộ (thông tin đã được kiểm duyệt)\n"
                f"{context}\n\n"
                f"Lưu ý: Nếu hai nguồn mâu thuẫn về thời gian/năm học, ưu tiên Nguồn Web."
            )
        else:
            context = web_context_override
```

> [!NOTE]
> Lưu ý: block này nằm trong `rag_flow()` (line 934). Có **thêm 1 copy** ở `rag_flow_streaming()`. Cần kiểm tra xem streaming path có cần cập nhật không. Theo `MODULE.md`, streaming path **KHÔNG** chạy Tavily fallback, nên chỉ cần sửa ở `rag_flow()`.

**4b. Post-gen fallback early-exit guard** (lines 2486-2494 trong `_tavily_fallback_result`)

Trước ([lines 2486-2494](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L2486-L2494)):
```python
    web_context = str(search_info.get("context") or "")
    tavily_sources = list(search_info.get("sources") or [])
    if not web_context:
        return {
            "answer": answer,
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": False,
        }
```

Sau:
```python
    web_context = str(search_info.get("context") or "")
    tavily_sources = list(search_info.get("sources") or [])
    # Early-exit: web context empty or too short → don't waste an LLM call
    if not web_context or len(web_context.strip()) < 200:
        if web_context:
            logger.info(
                "Tavily web context too short (%d chars), skipping re-generation",
                len(web_context),
            )
        return {
            "answer": answer,
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": False,
        }
```

---

### Phase 3 — Observability

---

#### [MODIFY] [flows.py](file:///d:/GR/src/RAG_v2/pipeline/flows.py)

**5a. Thêm observability vào `_tavily_search_context()`** (sau search, trước return — lines 2424-2427)

Trước ([lines 2424-2427](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L2424-L2427)):
```python
            timings_ms["tavily_search"] = _elapsed_ms(search_t0)

            web_context = str(search_result.get("context") or "")
            tavily_sources = _tavily_results_to_docs(search_result)
```

Sau:
```python
            timings_ms["tavily_search"] = _elapsed_ms(search_t0)

            raw_results = search_result.get("results") or []
            timings_ms["web_results_raw_count"] = float(len(raw_results))
            content_lengths = [
                len(str(r.get("content", "")))
                for r in raw_results
                if isinstance(r, dict)
            ]
            if content_lengths:
                timings_ms["web_avg_content_length"] = round(
                    sum(content_lengths) / len(content_lengths), 1
                )

            web_context = str(search_result.get("context") or "")
            tavily_sources = _tavily_results_to_docs(search_result)
```

---

## Tổng Hợp Tất Cả File Thay Đổi

| # | File | Thay đổi | Phase | Lines |
|---|---|---|---|---|
| 1a | `config/settings.py` | `agent_tool_result_limit`: `3000` → `5000` | 1 | 92 |
| 1b | `config/settings.py` | `agent_search_result_char_limit`: `700` → `1200` | 1 | 138 |
| 1c | `config/settings.py` | `tavily_max_results`: `3` → `5`, thêm 2 config mới | 1 | 158-164 |
| 2a | `agent/tool_adapters.py` | `_format_web_results()`: config thay hardcode | 1 | 772-777 |
| 3a | `tools/tavily_search.py` | `_parse_results()`: thêm `score` field | 2 | 381-393 |
| 3b | `tools/tavily_search.py` | Thêm `filter_results()` method | 2 | (mới) |
| 3c | `tools/tavily_search.py` | Tích hợp filter vào `search()` | 2 | 252-253 |
| 4a | `pipeline/flows.py` | Source hierarchy headers | 2 | 1497-1502 |
| 4b | `pipeline/flows.py` | Post-gen early-exit guard | 2 | 2486-2494 |
| 5a | `pipeline/flows.py` | Observability metrics | 3 | 2424-2427 |

---

## Verification Plan

### Automated Tests

```bash
# 1. Chạy existing tests — verify không break
cd d:\GR\src\RAG_v2
python -m pytest tests/test_adapters.py -v
python -m pytest pipeline/test_flows_major_fallback.py -v

# 2. Quick smoke test — verify config changes loaded
python -c "from config.settings import Settings; s = Settings(); print(f'max_results={s.tavily_max_results}, char_limit={s.tavily_web_content_char_limit}, result_count={s.tavily_web_result_count}')"

# 3. Verify filter_results works
python -c "
from tools.tavily_search import TavilySearchTool
results = [
    {'content': 'x' * 50, 'score': 0.8},   # too short → filtered
    {'content': 'x' * 200, 'score': 0.9},   # OK
    {'content': 'x' * 300, 'score': 0.1},   # low score nhưng vẫn pass (min_score=0.0 default)
]
filtered = TavilySearchTool.filter_results(results, min_content_length=100)
assert len(filtered) == 2, f'Expected 2, got {len(filtered)}'
print('filter_results OK')
"
```

### Manual Verification

1. Query dynamic: `"lịch đăng ký học phần 20261"` → verify Tavily fetch 5, hiện 3 results
2. Verify web context có headers `## Nguồn Web` / `## Nguồn Cơ Sở Dữ Liệu Nội Bộ`
3. Verify `timings_ms` có `web_results_raw_count`, `web_avg_content_length`
4. Agent path: verify `_format_web_results()` dùng `1500` char limit thay vì `500`
5. Post-gen: test với empty/short web context → verify không trigger LLM re-generate

### Cập nhật sau khi hoàn thành

- Cập nhật [MODULE.md](file:///d:/GR/src/RAG_v2/tools/MODULE.md) — reflect new config values
- Cập nhật `.env.example` nếu có
