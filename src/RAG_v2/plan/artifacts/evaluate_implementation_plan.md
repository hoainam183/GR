# Phân Tích Chính Xác & Plan Cải Thiện RAG v2 — Incorrect Results

## Tổng Quan Kết Quả Đánh Giá

| Metric | Value |
|--------|-------|
| Tổng samples | 499 |
| Correct | 260 (52.1%) |
| Partial | 60 (12.0%) |
| Incorrect | 180 (36.1%) |

| Backend Mode | Total | Correct | Fail | Accuracy |
|--------------|-------|---------|------|----------|
| **rag_v2** | 444 | 238 | 206 | 53.6% |
| **agent** | 39 | 30 | 9 | 76.9% |
| **clarify** | 14 | 0 | 14 | **0.0%** |
| rag_v2_decomposed | 1 | 1 | 0 | 100% |

---

## 🐛 BUG #1: ComplexityRouter `personal_check` False Positive — 14 cases (100% fail)

> [!CAUTION]
> Đây là bug nghiêm trọng nhất: 14 câu hỏi hoàn toàn **factual về quy chế** bị route sai vào `personal_check` → trả canned response hardcoded → 100% incorrect.

### Nguyên nhân gốc

Trong [rag_pipeline.py](file:///d:/GR/src/RAG_v2/pipeline/rag_pipeline.py#L759-L779), khi `route == "complex" and subtype == "personal_check"`, hệ thống trả **hardcoded response** mà không hề gọi RAG:

```python
# rag_pipeline.py:759-779
if route == "complex" and subtype == "personal_check":
    return {
        "answer": "Để kiểm tra điều kiện tốt nghiệp cá nhân, mình cần thêm "
                  "CPA/GPA, số tín chỉ đã tích lũy...",
        "mode": "clarify",
        ...
    }
```

Kết hợp với `signals.py` và `complexity_router.py`, 2 nguồn trigger false positive:

**Nguồn 1** — [complexity_router.py:L174-L186](file:///d:/GR/src/RAG_v2/query/complexity_router.py#L174-L186): Signal-based override:
```python
if query_signals.personal_reference and query_signals.eligibility_check:
    → "personal_check"
```

**Nguồn 2** — [complexity_router.py:L76-L78](file:///d:/GR/src/RAG_v2/query/complexity_router.py#L76-L78): Regex pattern:
```python
r"\b(tôi|mình|em)\b.{0,80}\b(có thể|đủ điều kiện|...)\b"
```

### Các câu bị false positive

| # | Question | Lý do bị bắt nhầm |
|---|----------|-------------------|
| 1 | "Điểm bảo vệ đồ án **tốt nghiệp** cử nhân tính tối đa bao nhiêu nếu có thành viên chấm dưới 5?" | `eligibility_check=true` (chứa "tốt nghiệp") nhưng **KHÔNG có personal_reference** → bị bắt bởi regex `\b(tôi\|mình\|em)` ở nguồn 2 vì query khác |
| 2 | "**Mình** là sinh viên K67, nếu **mình** không đạt chuẩn ngoại ngữ..." | `personal_reference=true` + regex "mình...có thể" → false positive. Nhưng đây là **policy question**, không phải personal eligibility check |
| 3 | "**Tôi** là sinh viên K67, **tôi** muốn hỏi về điều kiện miễn học phần tiếng Anh." | "tôi" + "điều kiện" + "miễn" → trigger |
| 4-13 | "K66: Nếu **tôi** đạt TOEIC 400 thì **có được** miễn học phần nào không?" | "tôi" + "có được/có thể" → regex match |
| 14 | "Điểm rèn luyện tối thiểu để đạt **học bổng** loại B là bao nhiêu?" | `eligibility_check=true` (chứa "học bổng") + possible signal match |

### Fix đề xuất

**Option A (Recommended):** Thay đổi hành vi `personal_check` — thay vì hardcode answer, **vẫn chạy RAG flow** nhưng prepend profile context nếu có:

```python
# rag_pipeline.py:759
if route == "complex" and subtype == "personal_check":
    # Fallback to RAG with profile enrichment instead of canned response
    result = self.query(question=question, history=history, ...)
    result["mode"] = "rag_v2_personal"
    return result
```

**Option B:** Tighten regex — thêm condition: chỉ trigger khi query **thực sự hỏi "tôi có đủ/đạt không"** (câu hỏi yes/no về bản thân), KHÔNG trigger khi query hỏi thông tin quy chế chung:

```python
# Chỉ trigger khi CẢ HAI điều kiện đúng:
# 1. Personal reference ("tôi", "mình", "em")
# 2. Actual eligibility question (asking "do I qualify?", not "what are the rules?")
```

---

## 🐛 BUG #2: LLM Cache Returns Stale Incorrect Answers — 22 cases

> [!WARNING]
> 22 cases trong incorrect results có `cache_hit=true` và **không có `rerank_trace`, `answer_quality_gate`** → cache trả lại answer đã sai từ request trước, bypass toàn bộ pipeline.

### Nguyên nhân gốc

[flows.py:L2131-L2162](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L2131-L2162): LLM cache check sau rerank nhưng **trước self-eval và answer_quality_gate**:

```python
# flows.py:2131-2162
if llm_cache is not None and not dynamic_web_query ...:
    cached = llm_cache.get(question, doc_ids, chat_model.model)
    if cached is not None:
        if _answer_has_no_info_signal(...):
            pass  # Skip no-info cached answers
        else:
            return cached  # ← BUG: Returns without quality check!
```

Và [flows.py:L1606-L1636](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L1606-L1636): Pre-retrieval query cache:

```python
# flows.py:1606
if llm_cache.get_by_query(question, chat_model.model):
    return cached  # ← BUG: Returns without ANY retrieval!
```

**Vấn đề:** Cache lưu answer sai → request tiếp theo cùng question trả lại answer sai mà không qua self-eval.

### Fix đề xuất

1. **Invalidate cache khi self-eval fails:** Không cache answers có `answer_status="insufficient"`
2. **TTL-based cache:** Giảm cache TTL hoặc invalidate khi index thay đổi
3. **Trong eval mode:** Disable cache hoàn toàn (`llm_cache=None`)

---

## 🐛 BUG #3: Agent Mode Incorrect — 9 cases (23.1% fail rate)

| Aspect | Value |
|--------|-------|
| Agent total | 39 |
| Agent correct | 30 (76.9%) |
| Agent incorrect | 9 (23.1%) |

9 cases trong incorrect results có `backend_mode=agent`. Các queries này là **simple policy questions** ("Sinh viên có thể điều chỉnh ĐKHP bao nhiêu lần?") bị route vào `complex` → agent path.

### Nguyên nhân

[complexity_router.py](file:///d:/GR/src/RAG_v2/query/complexity_router.py) route các câu chứa "có thể" vào `complex/multi_source` hoặc `complex/general` khi regex match:
```python
r"\b(có\s+thể|có\s+được)\b.{0,30}\b(tốt nghiệp|đăng ký|...)\b"
```

Nhưng "Sinh viên có thể đăng ký bao nhiêu tín chỉ?" là câu factual đơn giản → RAG v2 xử lý tốt hơn.

### Fix đề xuất

Tighten `multi_source` regex: chỉ trigger khi query thực sự multi-domain, không phải simple factual.

---

## 📊 Retrieval Quality Analysis (Remaining 195 cases)

### Breakdown theo Answer Status

```
insufficient: 137/240 (57.1%) — LLM không có đủ context
answered:       51/240 (21.3%) — có context nhưng answer sai
stale_risk:      7/240 (2.9%)  — freshness concern
N/A:            45/240 (18.8%) — clarify(14) + cache(22) + agent(9)
```

### Retrieval Confidence

```
context_chars = 0:        43 cases (17.9%) — hoàn toàn không có context
rerank passing ≤ 2:      137 cases (57.1%) — rất ít context
rerank passing > 2:       60 cases (25.0%) — đủ context nhưng answer vẫn sai
```

### Self-Eval & Tavily

```
Self-eval failed:        129/240 (53.8%) — hệ thống tự biết answer yếu
Tavily search used:      151/240 (62.9%) — nhưng 63% vẫn incorrect!
Pre-gen web fallback:     48 cases — kéo Tavily trước khi generate
```

> [!NOTE]
> **QC 2025 đã được index** — accuracy 58.5% cho QC 2025 questions chứng minh document có trong Qdrant. Vấn đề là chunk matching + reranker threshold khiến 41.5% QC 2025 queries vẫn fail.

### Judge Reason Analysis

```
missing_info:     118 (49.2%) — thiếu facts cụ thể
hallucination:     14 (5.8%)  — bịa thông tin
contradictory:     10 (4.2%)  — sources mâu thuẫn (Tavily vs local)
vague_inaccurate:  10 (4.2%)  — trả lời chung chung
outdated_source:    8 (3.3%)  — trích nguồn cũ
excessive_info:     5 (2.1%)  — thêm info ngoài scope
```

---

## 🛠️ Proposed Fixes — Priority Order

### P0 — Quick Wins (Impact: ~35-50 samples recovered)

#### Fix 1: Sửa ComplexityRouter `personal_check` → RAG fallback

**Files:**
- [rag_pipeline.py](file:///d:/GR/src/RAG_v2/pipeline/rag_pipeline.py#L759-L779) — Thay hardcoded response bằng RAG flow
- [complexity_router.py](file:///d:/GR/src/RAG_v2/query/complexity_router.py#L74-L78) — Tighten regex
- [signals.py](file:///d:/GR/src/RAG_v2/query/signals.py#L59-L63) — Narrow `eligibility_check` patterns

**Impact:** +14 samples (hiện tại 100% fail → dự kiến ~70-80% correct)

#### Fix 2: Disable LLM Cache trong Eval hoặc Fix Cache Logic

**File:** [flows.py](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L2131-L2162)

- Option A: Eval harness truyền `llm_cache=None`
- Option B: Không cache answers có `answer_status != "answered"`
- Option C: Thêm `_answer_has_no_info_signal` check trước khi cache

**Impact:** +22 samples nếu underlying RAG correct (ước tính ~12-15 recovered)

#### Fix 3: Tighten Agent Routing — Simple Questions Nên Dùng RAG v2

**File:** [complexity_router.py](file:///d:/GR/src/RAG_v2/query/complexity_router.py#L82-L84)

Thêm exclusion condition cho `multi_source` pattern: nếu query chỉ hỏi 1 fact đơn giản (không có "và", "đồng thời") → giữ `simple`.

**Impact:** ~5-7 samples (9 agent fails → route sang RAG v2)

---

### P1 — Retrieval Quality (Impact: ~20-40 samples)

#### Fix 4: Hạ Reranker Score Threshold

**File:** [settings.py](file:///d:/GR/src/RAG_v2/config/settings.py)

```diff
- reranker_score_threshold: float = 0.0
+ reranker_score_threshold: float = -2.0
```

Hoặc thêm dynamic threshold: nếu tất cả candidates < 0.0 → dùng top-k by raw score (fallback đã có nhưng chỉ trigger khi ALL negative):

**Hiện tại** (line 2018): `_rerank_quality_ok = best_score >= 0.0`
- Fallback chỉ trigger khi **best score < 0.0**
- Nhưng 43 cases có 0 candidates qua rerank → `reranked = []` → fallback không trigger vì `raw_results and not _rerank_quality_ok` check `_best_explicit_rerank_score(reranked)` trên empty list → returns `None` → `_rerank_quality_ok = True` (vì `None >= 0.0` is False nhưng `None is None` is True → `_best_rerank_score is None or ...` → True!)

> [!CAUTION]
> **BUG trong fallback logic!** Khi `reranked = []`, `_best_explicit_rerank_score([])` returns `None`, và `_rerank_quality_ok = None is None or None >= 0.0` = `True`. Nên fallback **KHÔNG trigger** khi cần nhất (0 reranked docs). Fix: thêm check `not reranked` trước.

#### Fix 5: Tavily Source Version Filtering

**File:** [tools/tavily_search.py](file:///d:/GR/src/RAG_v2/tools/tavily_search.py)

- Filter web results chứa URL PDF QC 2023 khi đã có QC 2025 local
- Thêm warning trong merged context: "Nguồn web có thể outdated"

#### Fix 6: Generation Prompt — Concise Answers

**File:** [llm/prompts.py](file:///d:/GR/src/RAG_v2/llm/prompts.py)

Thêm instruction để LLM:
- Trả lời ngắn gọn, đúng câu hỏi
- Không liệt kê trường hợp ngoại lệ trừ khi được hỏi
- Khi nhiều nguồn mâu thuẫn → chọn nguồn nội bộ

---

### P2 — Long-term (Monitoring & Index Quality)

#### Fix 7: Fix `_rerank_quality_ok` Bug

**File:** [flows.py](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L2017-L2019)

```diff
  _best_rerank_score = _best_explicit_rerank_score(reranked)
- _rerank_quality_ok = _best_rerank_score is None or _best_rerank_score >= 0.0
+ _rerank_quality_ok = (
+     bool(reranked)
+     and (_best_rerank_score is None or _best_rerank_score >= 0.0)
+ )
```

Khi `reranked` rỗng → `_rerank_quality_ok = False` → trigger raw fallback.

#### Fix 8: AB Test Framework

- Set up eval chạy so sánh config A vs B
- Track `correct%`, `context_chars`, `retrieval_precision`

---

## 📋 Summary — Priority & Impact

| # | Bug/Fix | Cases Affected | Expected Recovery | Effort | Priority |
|---|---------|---------------|-------------------|--------|----------|
| 1 | **ComplexityRouter personal_check** → RAG fallback | 14 | +10-12 correct | 1h | 🔴 P0 |
| 2 | **Cache stale answers** → disable/fix cache | 22 | +12-15 correct | 1h | 🔴 P0 |
| 3 | **Agent over-routing** → tighten regex | 9 | +5-7 correct | 1h | 🔴 P0 |
| 4 | **Reranker threshold** → lower to -2.0 | ~100 | +15-25 correct | 1h | 🟡 P1 |
| 5 | **Tavily source filtering** → version check | ~50 | +5-10 correct | 2h | 🟡 P1 |
| 6 | **Generation prompt** → concise answers | ~20 | +3-5 correct | 1h | 🟡 P1 |
| 7 | **Rerank fallback bug** → fix empty list check | 43 | +5-10 correct | 30m | 🔴 P0 |
| 8 | AB test framework | — | eval quality | 4h | 🟢 P2 |

> [!TIP]
> **P0 fixes (#1, #2, #3, #7)** sẽ recover **~32-44 samples** ngay lập tức mà không cần thay đổi retrieval logic. Ước tính accuracy tăng từ **52.1% → 58-61%**.
> 
> Kết hợp P1 fixes (#4-6): ước tính tổng accuracy **65-72%**.

## Verification Plan

### Automated Tests
1. Re-run full eval suite sau mỗi fix: `python -m evaluation.sft_backend_eval`
2. Specifically test 14 clarify cases → should become correct
3. Test 22 cache-hit cases với `llm_cache=None`
4. Check `rerank_raw_fallback` triggers cho 43 zero-context cases

### Manual Verification
- "Điểm bảo vệ đồ án tốt nghiệp cử nhân tính tối đa bao nhiêu nếu có thành viên chấm dưới 5?" → should answer "4.9 điểm"
- "K66: Nếu tôi đạt TOEIC 400 thì có được miễn học phần nào không?" → should lookup QĐ ngoại ngữ K66
- "Sinh viên có thể điều chỉnh đăng ký học tập bao nhiêu lần?" → should route to RAG, not agent
