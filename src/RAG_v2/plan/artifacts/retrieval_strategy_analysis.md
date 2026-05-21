# Kế hoạch Cải thiện RAG v2 Retrieval — v5 (Final)

> [!NOTE]
> **Phiên bản cuối** — 5 vòng iteration, 3 vòng source-code validation, 1 live test (Gemini logprobs), 1 chunk-size analysis. Mỗi quyết định có evidence-based justification.

---

## Corrections Log — Những gì đã thay đổi

| # | Nhận định trước | Evidence mới | Kết luận |
|---|----------------|-------------|----------|
| 1 | Score cliff `min_gap=2.0` hợp lý | kehoach scores cluster trong range 1.09 (5.2-6.3) → cliff **KHÔNG bao giờ trigger** cho kehoach | ❌ Cần adaptive per-collection |
| 2 | Logprobs là alternative cho no-info detection | Gemini (primary provider) **KHÔNG expose logprobs** | ❌ Không khả thi |
| 3 | Context budget 8000 chars | Production values: **12000** chars (settings override code default) | Sửa con số |
| 4 | Routing khi confidence thấp chưa rõ | < 0.55 → all collections; 0.55-0.65 → Tier 3 LLM; > 0.65 → commit | ✅ Có fallback, nhưng có gap |
| 5 | Self-eval disabled chưa rõ lý do | **Latency**: +3-5s/query (comment in settings + timing logs) | ✅ Intentional trade-off |
| 6 | `date_str` luôn có cho kehoach | **CÓ THỂ null** — older pre-crawler docs thiếu, crawler đôi khi fail extract | ⚠️ Cần xử lý |
| 7 | Recency bonus magnitude chưa rõ | `max(0, 1 - age_days/365) × 0.05` → max **+0.05** (today's doc). Linear decay, 0 after 365d | ✅ Nhỏ hơn dự kiến, chỉ là tiebreaker |

---

## Kiến trúc Routing đã validate

```mermaid
flowchart TD
    Q[User Query] --> T1["Tier 1: ML Classifier<br/>CalibratedLogReg + TF-IDF"]
    T1 --> C{confidence}
    C -->"|> 0.65<br/>OR margin ≥ 0.25"| D1["Commit to domain(s)"]
    C -->"|< 0.55<br/>AND margin < 0.25"| T3["Tier 3: LLM Override<br/>Gemini<br/>(+2-12s)"]
    C -->"|Low conf<br/>fallback"| ALL["Broaden: active +<br/>MULTI_DOMAIN_FALLBACK"]
    T3 --> D2["LLM domain committed"]
    
    D1 --> H["Tier 2: Heuristic Override<br/>keyword rules, freshness lock"]
    D2 --> H
    H --> CS["CollectionSelector.select()"]
    
    CS -->|"Freshness + kehoach"| LOCK["🔒 Lock to kehoach<br/>(even if low conf)"]
    CS -->|"Normal"| SEL["Selected collection(s)"]
    
    style C fill:#f59e0b,stroke:#d97706
    style ALL fill:#22c55e,stroke:#16a34a
    style LOCK fill:#ef4444,stroke:#dc2626
```

> [!WARNING]
> **Tier 3 trigger**: `confidence < 0.55 AND dominant_margin < 0.25`. Khi triggered, Gemini classify query → override routing. Nếu LLM sai ở vùng ambiguous, mọi optimization downstream đều vô nghĩa. Chỉ ~5% queries trigger Tier 3 (theo source comments). **Lưu ý**: Low-confidence fallback **KHÔNG** search all collections — thay vào đó dùng `MULTI_DOMAIN_FALLBACK = ["quydinh", "stsv", "ctdt"]` kèm active domain.

---

## Validated Score Distributions (từ eval data thực)

```
                    kehoach              ctdt               quydinh
                    ┌─────┐              ┌─────┐            ┌─────┐
Score 8.0           │     │              │█████│            │     │
Score 7.0           │     │              │█████│            │     │
Score 6.0           │█████│ ← cluster    │  █  │            │     │
Score 5.0           │█████│ (spread 1.1) │  █  │            │█████│
Score 4.0           │     │              │     │ ← cliff    │  █  │
Score 3.0           │     │              │     │            │  █  │
Score 2.0           │     │              │█    │            │     │ ← cliff
Score 1.0           │     │              │█    │            │     │
Score 0.0 --------- │-----│ ------------ │-----│ ---------- │-----│ ---
Score -1.0          │     │              │     │            │█████│
                    └─────┘              └─────┘            └─────┘
                    Cliff: NONE          Cliff: ~4.0        Cliff: ~2.0
```

**Implications cho Score Cliff strategy**:
- `min_gap=2.0` → ❌ **never triggers** cho kehoach (tight clusters)
- `min_gap=2.0` → ✅ works cho ctdt/quydinh (clear cliffs)
- Need **per-collection OR adaptive** approach

---

## Kế hoạch — Reorganized by Decision Category

### 🟢 LÀM NGAY — Không cần debate (Day 1-2)

#### A1. Web Query Enrichment + Homepage Filter

**Files**: [flows.py:367-405](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L367), [tavily_search.py:410](file:///d:/GR/src/RAG_v2/tools/tavily_search.py#L410)

```python
def _build_web_search_query(question: str, search_query: str) -> str:
    # ... existing logic ...
    
    # ── Academic year injection ──────────────────────────────
    now = datetime.now()
    current_year = now.year
    
    # HUST academic year: Aug → Jul
    if now.month >= 8:
        ay_start, ay_end = current_year, current_year + 1
    else:
        ay_start, ay_end = current_year - 1, current_year
    
    # ── Transition period override ─────────────────────────
    # "kỳ hè" queries: always refer to CURRENT academic year's summer
    # (no override needed — base logic already correct)
    # "năm học mới/tới" or "kỳ tới": only override in Jul+ (actual transition)
    folded = _fold_vietnamese(query)
    wants_next_year = any(kw in folded for kw in (
        "nam hoc moi", "nam hoc toi",       # new/next academic year  
        "ky toi", "ki toi", "hoc ky toi",   # next semester
    ))
    # Month >= 7 (July): actual transition period.
    # Month 5-6: still in current AY, "kỳ tới" = current AY's summer.
    if wants_next_year and now.month >= 7:
        ay_start, ay_end = current_year, current_year + 1
    
    academic_year_str = f"{ay_start}-{ay_end}"
    
    if has_freshness:
        if not re.search(r"\b20\d{2}\b", folded):
            extras.append(f"năm học {academic_year_str}")
        extras.append("CTT ĐHBKHN")
    
    # ── Content-type signal ──────────────────────────────────
    if any(kw in folded for kw in ("lich", "ke hoach", "thong bao", "dang ky")):
        if "thong bao" not in folded and "ke hoach" not in folded:
            extras.append("thông báo kế hoạch")
    
    # ... rest of existing logic ...
```

**Homepage filter** — [tavily_search.py:410](file:///d:/GR/src/RAG_v2/tools/tavily_search.py#L410):

```python
@staticmethod
def filter_results(results, *, min_content_length=100, min_score=0.0,
                   query_year=None, exclude_homepages=True):
    filtered = []
    for r in results:
        content = r.get("content", "")
        if len(content) < min_content_length:
            continue
        if float(r.get("score", 1.0) or 1.0) < min_score:
            continue
        
        # ── NEW: Homepage filter ──────────────────────────
        if exclude_homepages:
            url = r.get("url", "")
            parsed = urlparse(url)
            path = (parsed.path or "").rstrip("/")
            if path in ("", "/vi", "/en", "/index", "/index.html"):
                logger.debug("Filtered homepage: %s", url)
                continue
        
        # ... existing year filter ...
        filtered.append(r)
    return filtered
```

---

#### A2. Mở rộng No-Info Patterns

**File**: [flows.py:88-97](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L88)

> [!NOTE]
> User đúng rằng đây là symptom mitigation, không phải root cause fix. Root cause = `self_eval_enabled=False` (disabled vì +3-5s latency). Patterns là **cost-effective defense layer** khi self-eval off. Intentional trade-off đã được document.

```python
_WEB_FALLBACK_NO_INFO_PATTERNS = (
    # ── Existing (8) ──────────────────────────────────────
    "toi khong tim thay thong tin nay trong tai lieu hien co",
    "khong tim thay thong tin",
    "khong co thong tin",
    "chua co thong tin",
    "khong du co so",
    "khong du thong tin",
    "tai lieu hien co khong",
    "chua tim thay",
    # ── New: Rephrase variants (11) ───────────────────────
    "khong the xac nhan",
    "chua duoc cap nhat",
    "khong nam trong tai lieu",
    "ngoai pham vi",
    "khong co du lieu",
    "chua co du lieu",
    "khong the tra loi",
    "chua the xac dinh",
    "tai lieu khong de cap",
    "thong tin con han che",
    "can kiem tra them",
)
```

---

#### A3. Regression Test Suite (song song với A1-A2)

**File**: New `eval/regression_tests.py`

```python
"""Known failure cases — run before and after each retrieval change."""
import json
from urllib.parse import urlparse

REGRESSION_CASES = [
    {
        "id": "freshness_homepage",
        "query": "Lịch học kỳ mới nhất?",
        "assertions": [
            ("no_homepage_urls", lambda r: not any(
                urlparse(s.get("url", "")).path.rstrip("/") in ("", "/vi")
                for s in r.get("sources", []) if s.get("url")
            )),
            ("has_web_or_local_content", lambda r: 
                len(r.get("sources", [])) > 0 or 
                "tavily" in str(r.get("tools_used", []))
            ),
        ],
    },
    {
        "id": "specific_kehoach",
        "query": "kế hoạch đăng kí học tập kì hè",
        "assertions": [
            ("has_high_rerank_score", lambda r: any(
                (s.get("rerank_score") or 0) > 4.0
                for s in r.get("sources", [])
            )),
            ("routes_to_kehoach", lambda r: 
                "kehoach" in str(r.get("target_collections", []))
            ),
        ],
    },
]

def run_regression(api_url="http://localhost:8000"):
    """Run all cases, return pass/fail summary."""
    import requests
    results = []
    for case in REGRESSION_CASES:
        resp = requests.post(f"{api_url}/api/chat",
            json={"query": case["query"]}).json()
        passed = all(check(resp) for _, check in case["assertions"])
        failed_checks = [
            name for name, check in case["assertions"] if not check(resp)
        ]
        results.append({
            "id": case["id"], "passed": passed, "failed": failed_checks
        })
    return results
```

---

### 🟡 VALIDATE TRƯỚC — Cần data/benchmark trước khi implement

#### B1. Adaptive Score Cliff — Per-Collection Strategy

**Why static 2.0 doesn't work**: Validated score distributions show:
- kehoach: spread ~1.1 → gap 2.0 **never triggers** → docs never pruned
- ctdt: spread ~5.75, cliff at ~4.0 → gap 2.0 works
- quydinh: spread ~6.62, cliff at ~2.0 → gap 2.0 works marginally

**Revised approach**: Apply cliff **per-collection** rồi merge — giải quyết vấn đề multi-collection mixed thresholds:

> [!IMPORTANT]
> **Cliff operates on `rerank_score`** (cross-encoder logit từ BGE-reranker-v2-m3), **KHÔNG** phải fusion score. Cross-encoder đã so sánh tất cả docs cùng query nên scores globally comparable. Tuy nhiên per-collection cliff vẫn có giá trị vì **distribution patterns** khác nhau: kehoach docs thường cluster chặt (spread ~1.1) trong khi ctdt/quydinh có wide spreads (~5-6). Một gap 0.5 ở kehoach là significant (33% of total range), còn ở ctdt là noise (8% of range).

```python
_CLIFF_MIN_GAP_BY_COLLECTION = {
    "kehoach": 0.5,    # Tight clusters → smaller gap is significant
    "ctdt":    2.0,    # Wide spreads → need larger gap
    "quydinh": 1.5,    # Moderate spreads
    "stsv":    1.5,    # Moderate
}
_CLIFF_MIN_GAP_DEFAULT = 1.5
_CLIFF_MIN_KEEP_PER_COLL = 1   # Keep at least 1 per collection
_CLIFF_MIN_KEEP_TOTAL = 2      # Keep at least 2 total

def _apply_score_cliff_per_collection(
    reranked: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Apply cliff detection per-collection, then merge results."""
    if len(reranked) <= _CLIFF_MIN_KEEP_TOTAL:
        return reranked
    
    # Group by collection
    by_collection: Dict[str, List[Dict]] = {}
    for doc in reranked:
        coll = doc.get("collection", "_unknown")
        by_collection.setdefault(coll, []).append(doc)
    
    kept: List[Dict[str, Any]] = []
    for coll, docs in by_collection.items():
        min_gap = _CLIFF_MIN_GAP_BY_COLLECTION.get(coll, _CLIFF_MIN_GAP_DEFAULT)
        scores = [_safe_float(d.get("rerank_score", 0)) for d in docs]
        
        if len(docs) <= _CLIFF_MIN_KEEP_PER_COLL or all(s <= 0 for s in scores):
            kept.extend(docs)
            continue
        
        # Find cliff within this collection's docs
        best_cut = len(scores)
        max_gap_val = 0.0
        for i in range(_CLIFF_MIN_KEEP_PER_COLL, len(scores)):
            gap = scores[i - 1] - scores[i]
            if gap > max_gap_val and gap > min_gap:
                max_gap_val = gap
                best_cut = i
        
        if best_cut < len(docs):
            logger.info(
                "Score cliff [%s] at pos %d (gap=%.2f, min_gap=%.1f), "
                "keeping %d/%d docs",
                coll, best_cut, max_gap_val, min_gap, best_cut, len(docs),
            )
        kept.extend(docs[:best_cut])
    
    # Re-sort by rerank score (global order)
    kept.sort(key=lambda d: _safe_float(d.get("rerank_score", 0)), reverse=True)
    
    # Safety: keep at least _CLIFF_MIN_KEEP_TOTAL docs total
    if len(kept) < _CLIFF_MIN_KEEP_TOTAL:
        kept = reranked[:_CLIFF_MIN_KEEP_TOTAL]
    
    return kept
```

> [!NOTE]
> **Tại sao per-collection?** Khi query trả 3 kehoach (scores 6.3, 6.1, 5.9) + 2 quydinh (scores 3.4, 0.8):
> - **Old (dominant=kehoach, min_gap=0.5)**: Gap 2.5 giữa kehoach→quydinh triggers cliff → cắt cả 2 quydinh (có thể relevant)
> - **New**: kehoach cliff (min_gap=0.5): keep all 3 (no 0.5 gap). quydinh cliff (min_gap=1.5): gap 2.6 → cắt doc 0.8 → keep 3.4. Result: [6.3, 6.1, 5.9, 3.4] ✅

**Validation step trước implement**: Chạy histogram trên eval set:

```bash
# Generate rerank score histogram from existing eval results
python -c "
import json
with open('retrieval_test_result.json') as f:
    data = json.load(f)
for case in data:
    scores = [r.get('rerank_score', 0) for r in case.get('results', [])]
    coll = case.get('expected_collection', '?')
    if len(scores) >= 2:
        gaps = [scores[i]-scores[i+1] for i in range(len(scores)-1)]
        print(f'{coll}: scores={[round(s,1) for s in scores]} max_gap={max(gaps):.1f}')
"
```

---

#### B2. Per-Collection Fusion — Normalization + Weights (ĐỒNG THỜI)

User đúng: per-collection weights **PHẢI** đi kèm per-collection normalization. Làm riêng lẻ không giải quyết bias.

**File**: [multi_collection_search.py `_score_fusion()`](file:///d:/GR/src/RAG_v2/retrieval/multi_collection_search.py#L638)

**Strategy**: Thay thế global min-max bằng per-collection min-max → per-collection weighted sum → global merge:

```python
def _score_fusion_per_collection(self, vector_pool, keyword_pool):
    """Per-collection normalization + weighted fusion."""
    
    # 1. Group by collection
    collections = set(d.get("collection", "") for d in vector_pool + keyword_pool)
    
    all_scored = {}  # doc_id → {score, collection, ...}
    
    for coll in collections:
        coll_vec = [d for d in vector_pool if d.get("collection") == coll]
        coll_kw = [d for d in keyword_pool if d.get("collection") == coll]
        
        # 2. Per-collection min-max normalization
        norm_vec = self._min_max_normalize(coll_vec)  # {id: 0.0-1.0}
        norm_kw = self._min_max_normalize(coll_kw)
        
        # 3. Per-collection weights
        weights = self._collection_weights.get(coll, {
            "vector": self.vector_weight,
            "keyword": self.keyword_weight,
        })
        
        # 4. Weighted sum within collection
        all_ids = set(norm_vec) | set(norm_kw)
        for doc_id in all_ids:
            score = (
                weights["vector"] * norm_vec.get(doc_id, 0.0) +
                weights["keyword"] * norm_kw.get(doc_id, 0.0)
            )
            # Apply kehoach recency bonus (existing logic)
            score += self._recency_bonus(doc_id, coll)
            all_scored[doc_id] = score
    
    # 5. Global sort — scores are now comparable because each
    # collection was independently normalized to [0,1]
    return sorted(all_scored.items(), key=lambda x: x[1], reverse=True)
```

**Validation**: Before/after benchmark trên eval set:

```bash
python -m evaluation.search_strategy_benchmark \
    --strategy hybrid_reranked \
    --output eval/baseline_global_norm.json

# Apply per-collection normalization, re-run:
python -m evaluation.search_strategy_benchmark \
    --strategy hybrid_reranked \
    --output eval/after_per_collection_norm.json

# Compare nDCG@10, MRR@10
python -c "
import json
b = json.load(open('eval/baseline_global_norm.json'))
a = json.load(open('eval/after_per_collection_norm.json'))
print(f'Baseline nDCG: {b[\"ndcg@10\"]:.4f}')
print(f'After    nDCG: {a[\"ndcg@10\"]:.4f}')
"
```

---

### 🔴 CẦN QUYẾT ĐỊNH KIẾN TRÚC — Resolve trước khi code

#### C1. Sibling Chunk Expansion — TRƯỚC Rerank (Resolved)

**Decision**: Expand **TRƯỚC rerank** — đồng ý với user reasoning:

> Nếu chunk 5 score thấp (chỉ là phần dẫn nhập) và bị cắt bởi score cliff, expansion SAU rerank không còn cơ hội chạy. Expand TRƯỚC cho phép reranker đánh giá siblings cùng query.

**Latency impact**: Reranker đã xử lý `max(top_k * 4, 40) = 40` candidates. Thêm tối đa 6 siblings → **46 candidates** → latency tăng ~15% (chấp nhận được).

**Implementation** — thêm sibling expansion **giữa search và rerank**:

```python
# flows.py — sau line 1503 (sau "Retrieved %d raw candidates")
# TRƯỚC line 1506 (rerank_t0)

if _cfg_bool(cfg, "sibling_expansion_enabled", False):
    expansion_t0 = time.perf_counter()
    raw_results = _expand_with_siblings_pre_rerank(
        candidates=raw_results,
        searcher=searcher,
        expand_top_n=3,    # Only top 3 candidates by fusion score
        window=1,           # ±1 sibling
        max_expansion=6,    # Budget: max 6 extra chunks
    )
    timings_ms["sibling_expansion"] = _elapsed_ms(expansion_t0)
    timings_ms["candidates_after_expansion"] = float(len(raw_results))
```

```python
def _expand_with_siblings_pre_rerank(
    candidates: List[Dict[str, Any]],
    searcher: Any,
    *,
    expand_top_n: int = 3,
    window: int = 1,
    max_expansion: int = 6,
) -> List[Dict[str, Any]]:
    """Expand top candidates with sibling chunks BEFORE reranking."""
    # Sort by fusion score to identify top candidates
    sorted_candidates = sorted(
        candidates, key=lambda d: d.get("score", 0.0), reverse=True
    )
    
    existing_ids = {str(d.get("id", "")) for d in candidates}
    new_siblings: List[Dict[str, Any]] = []
    added = 0
    
    for doc in sorted_candidates[:expand_top_n]:
        if added >= max_expansion:
            break
        meta = doc.get("metadata", {}) or {}
        source = meta.get("source")
        chunk_idx = meta.get("chunk_index")
        collection = doc.get("collection")
        
        if source is None or chunk_idx is None or collection is None:
            continue
        
        for offset in [-1, 1]:
            if added >= max_expansion:
                break
            target_idx = chunk_idx + offset
            if target_idx < 0:
                continue
            total = meta.get("total_chunks")
            if total is not None and target_idx >= total:
                continue
            
            siblings = searcher.get_by_metadata(
                collection=collection,
                filters={"source": source, "chunk_index": target_idx},
                limit=1,
            )
            for sib in siblings:
                sib_id = str(sib.get("id", ""))
                if sib_id and sib_id not in existing_ids:
                    sib["_expansion_source"] = str(doc.get("id", ""))
                    new_siblings.append(sib)
                    existing_ids.add(sib_id)
                    added += 1
    
    if new_siblings:
        logger.info("Sibling expansion: added %d chunks", len(new_siblings))
    
    return candidates + new_siblings
```

> [!IMPORTANT]
> **Dependency**: Cần thêm `get_by_metadata()` vào searcher. Qdrant `scroll()` với payload filter:
> ```python
> def get_by_metadata(self, collection, filters, limit=1):
>     """Lookup points by payload filter (very fast ~5ms)."""
>     from qdrant_client.models import Filter, FieldCondition, MatchValue
>     conditions = [
>         FieldCondition(key=k, match=MatchValue(value=v))
>         for k, v in filters.items()
>     ]
>     result = self.qdrant_client.scroll(
>         collection_name=collection,
>         scroll_filter=Filter(must=conditions),
>         limit=limit,
>         with_payload=True,
>         with_vectors=False,
>     )
>     return [self._point_to_doc(p, collection) for p in result[0]]
> ```

---

#### C2. Context Budget Strategy với Sibling Expansion

**Vấn đề**: Current budget = 12000 chars cho ~5 docs. Với siblings, có thể 8-11 docs → vượt budget → silent drop.

**Vấn đề mới (v4)**: Interleave siblings cạnh parent **phá vỡ rerank order** → lost-in-the-middle effect. Sibling ít relevant chiếm slot của doc relevant hơn ở vị trí attention tốt.

**Chunk size evidence** (v5 — validated từ data thực):

| Collection | Count | Median | P75 | Max |
|-----------|-------|--------|-----|-----|
| kehoach | 139 | 828 | 1042 | 1128 |
| ctdt | 1771 | 765 | 947 | 10010 |
| quydinh | 979 | 762 | 983 | 8197 |
| stsv | 374 | 781 | 997 | 1174 |

**Budget implication**: Median chunk ~780 chars. Với 500 chars/sibling (25% × 12000 / 6 siblings) → truncate ~35-50% content mỗi sibling → context không đầy đủ còn tệ hơn không có.

**Giải pháp v5**: Siblings SAU ranked docs, **budget 70/30**, sibling per-doc limit **800 chars** (phủ median chunk size):

```python
def _order_with_siblings(
    reranked: List[Dict[str, Any]],
    *,
    primary_budget_ratio: float = 0.70,
    total_budget: int = 16000,  # expanded budget when siblings enabled
) -> tuple[List[Dict[str, Any]], int, int]:
    """Order docs: ranked originals first, then siblings grouped by parent.
    
    Returns:
        (ordered_docs, primary_char_budget, sibling_char_budget)
    """
    originals = []
    sibling_map: Dict[str, List[Dict]] = {}  # expansion_source → siblings
    
    for doc in reranked:
        expansion_source = doc.get("_expansion_source")
        if expansion_source:
            sibling_map.setdefault(expansion_source, []).append(doc)
        else:
            originals.append(doc)
    
    # Siblings: grouped by parent, sorted by chunk_index within group
    # Groups ordered by parent's position in originals (best parent first)
    sibling_section = []
    for doc in originals:
        doc_id = str(doc.get("id", ""))
        siblings = sibling_map.pop(doc_id, [])
        siblings.sort(
            key=lambda s: s.get("metadata", {}).get("chunk_index", 0)
        )
        sibling_section.extend(siblings)
    
    # Orphan siblings (parent cut by cliff)
    for orphans in sibling_map.values():
        sibling_section.extend(orphans)
    
    ordered = originals + sibling_section
    
    # Budget allocation: 70/30 split
    primary_budget = int(total_budget * primary_budget_ratio)   # 11200 chars
    sibling_budget = total_budget - primary_budget               # 4800 chars
    
    return ordered, primary_budget, sibling_budget
```

**`_format_context()` cần update** để respect budget split:

```python
def _format_context(documents, *, per_doc_limit, total_budget,
                    sibling_budget=None,
                    sibling_per_doc_limit=800):  # Covers median chunk size
    # ... existing logic ...
    primary_budget = total_budget - (sibling_budget or 0)
    in_sibling_section = False
    current_budget = primary_budget
    current_per_doc = per_doc_limit  # 2000 for originals
    
    for doc in documents:
        if doc.get("_expansion_source") and not in_sibling_section:
            in_sibling_section = True
            current_budget = sibling_budget or 0
            current_per_doc = sibling_per_doc_limit  # 800 for siblings
            used = 0  # Reset counter for sibling section
        
        # Truncate to current_per_doc (2000 originals, 800 siblings)
        # ... existing truncation + budget check against current_budget ...
```

**Settings**:

```python
# settings.py
sibling_expansion_enabled: bool = False
sibling_budget_ratio: float = 0.30        # 30% of total budget for siblings
sibling_per_doc_limit: int = 800          # Per-sibling char limit (covers median chunk)
context_total_char_budget_with_expansion: int = 16000  # Expanded total
```

> [!NOTE]
> **Tại sao 70/30 và 800 chars?**
> - Median chunk size = ~780 chars → 800 limit keeps ~100% of median chunks intact
> - 30% × 16000 = 4800 chars → 4800 / 800 = **6 siblings** at full size
> - 70% × 16000 = 11200 chars → 5 originals × 2000 = 10000 (fits comfortably)
> - **Old (v4 75/25)**: 500 chars/sibling truncate 35-50% → incoherent context

---

#### C3. Freshness-Aware Tavily Suppression (với date_str null handling)

**File**: [flows.py:431-434](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L431)

User đúng: nếu kehoach docs có nhưng `date_str` null → silent failure → suppress Tavily sai.

**Conservative approach**: Nếu kehoach docs tồn tại nhưng KHÔNG có `date_str` → mặc định cho phép Tavily:

```python
# After computing high_local_confidence and freshness_query...

if freshness_query and high_local_confidence:
    local_kehoach = [
        d for d in reranked if d.get("collection") == "kehoach"
    ]
    if local_kehoach:
        dates = [
            d.get("metadata", {}).get("date_str")
            for d in local_kehoach
            if d.get("metadata", {}).get("date_str")  # non-null, non-empty
        ]
        
        if not dates:
            # kehoach docs exist but NO date metadata → can't verify freshness
            # Conservative: allow Tavily
            high_local_confidence = False
            logger.info(
                "Freshness override: %d kehoach docs but none have date_str, "
                "allowing Tavily (conservative)",
                len(local_kehoach),
            )
        else:
            has_recent = any(_is_date_within_days(ds, days=90) for ds in dates)
            if not has_recent:
                high_local_confidence = False
                logger.info(
                    "Freshness override: kehoach dates %s all >90 days, "
                    "allowing Tavily",
                    dates,
                )

def _is_date_within_days(date_str: str, days: int) -> bool:
    """Check if date_str (dd/mm/yyyy) is within N days of now."""
    try:
        doc_date = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return (datetime.now() - doc_date).days <= days
    except (ValueError, TypeError, AttributeError):
        return False  # Malformed → treat as old
```

---

#### C4. Routing Confidence Safeguard — Candidate Pool Increase (Revised)

**Vấn đề**: Khoảng 0.55-0.65 — Tier 3 LLM triggered, nếu LLM sai thì pipeline commit sai collection.

**Approach trước (v3 — REJECTED)**: Hedge bằng top-2 collections. **Lý do reject**: Cross-collection contamination. Khi kehoach là đúng và ctdt là hedge, ctdt docs có score spread lớn hơn sẽ cạnh tranh bất cân xứng với kehoach docs sau normalization. Hedge làm *giảm* quality thay vì tăng.

**Approach mới (v4)**: Giữ single collection nhưng **tăng candidate pool** khi confidence thấp. Nếu collection sai thì không có gì để retrieve dù pool lớn — ít nhất không contaminate:

```python
# flows.py — trong _retrieval_candidate_k() hoặc trước search
def _resolve_candidate_pool(
    cfg: dict,
    top_k: int, 
    routing_confidence: float,
) -> int:
    """Increase candidate pool when routing is uncertain."""
    base_pool = max(top_k * 4, 40)  # Current logic
    
    if routing_confidence < 0.65:  # Tier 3 zone
        # 2x pool → reranker has more material to work with
        expanded = base_pool * 2
        logger.info(
            "Low routing confidence (%.3f) → expanding candidate pool %d → %d",
            routing_confidence, base_pool, expanded,
        )
        return expanded
    
    return base_pool
```

> [!NOTE]
> **Tại sao pool increase thay vì collection hedge?**
> - Pool increase = thêm candidates từ **đúng collection** → reranker chọn tốt hơn
> - Collection hedge = thêm candidates từ **collection khác** → cross-collection normalization bias
> - Latency: pool 80 vs 40 → rerank +~30ms (chấp nhận được trong Tier 3 zone)

---

### ⏸️ DEPRIORITIZE — Chờ đủ data

#### D1. Automated Feedback → Benchmark Pipeline

**Blocker**: Cần biết số lượng thumbs-down records. Nếu < 50 → statistical noise.

**Action**: Kiểm tra MongoDB count trước khi invest:

```bash
# Check feedback volume
python -c "
from pymongo import MongoClient
db = MongoClient('mongodb://localhost:27017')['rag_chatbot']
total = db.feedback.count_documents({})
down = db.feedback.count_documents({'rating': 'down'})
print(f'Total feedback: {total}, Thumbs down: {down}')
if down < 50: print('⚠️  Insufficient data for benchmark calibration')
"
```

#### D2. LLM No-Info Detection

**Rejected approaches**:
- ❌ **Logprobs: CONFIRMED không khả thi** — Live test trả `400 Bad Request`:
  ```
  Error code: 400 - Unknown name "logprobs": Cannot find field.
  Unknown name "top_logprobs": Cannot find field.
  ```
  Gemini OpenAI compatibility endpoint (`v1beta/openai/`) **không support** `logprobs` parameter.
- ❌ Extra LLM call: +200ms latency quá cao cho defensive check

**Remaining option**: Bật `self_eval_enabled=True` (trade latency +3-5s cho accuracy). Chỉ recommend khi total pipeline latency giảm xuống < 30s.

**Documented trade-off**: Self-eval disabled = accept hallucination risk. Pattern matching = partial mitigation. Đây là **intentional architecture decision**, không phải bug.

---

## Self-Eval Trade-off Documentation

> [!WARNING]
> **Documented Decision**: `self_eval_enabled = False`
> 
> **Reason**: +3-5s latency per query (confirmed from timing logs)
> **Risk**: Only pattern matching detects insufficient answers. Confident hallucinations → no fallback.
> **Mitigation**: Expanded no-info patterns (A2). Long-term: evaluate if Gemini flash-lite self-eval can run < 1s.
> **Re-evaluate when**: Total pipeline latency < 30s (currently 60-76s), OR hallucination rate measured > 5% from feedback data.

---

## Production Monitoring Strategy

> [!IMPORTANT]
> Verification catches issues **before rollout**. Monitoring catches issues **after** — khi query distribution thực tế khác eval data, khi data pipeline thay đổi, khi external services (Tavily, ctt.hust.edu.vn) thay đổi behavior.

### 3 Metrics — inject vào existing `timings_ms` dict

Existing infrastructure: mỗi query flow đã produce `timings_ms: Dict[str, Any]` chứa key-value metrics, được log qua `_log_timings()` ([flows.py:120](file:///d:/GR/src/RAG_v2/pipeline/flows.py#L120)). Chỉ cần thêm 3 keys:

#### M1. Score Cliff Detection Rate

```python
# flows.py — sau _apply_score_cliff_per_collection()
if _cfg_bool(cfg, "score_cliff_enabled", False):
    pre_cliff_count = len(reranked)
    reranked = _apply_score_cliff_per_collection(reranked)
    cliff_dropped = pre_cliff_count - len(reranked)
    timings_ms["cliff_triggered"] = 1.0 if cliff_dropped > 0 else 0.0
    timings_ms["cliff_dropped_count"] = float(cliff_dropped)
```

**Alert**: Nếu `cliff_triggered` rate = 0% sau 7 ngày production (>500 queries) → threshold quá cao hoặc eval data không đại diện. Review `_CLIFF_MIN_GAP_BY_COLLECTION`.

---

#### M2. Sibling Expansion Hit Rate

```python
# flows.py — sau _expand_with_siblings_pre_rerank()
if _cfg_bool(cfg, "sibling_expansion_enabled", False):
    raw_results = _expand_with_siblings_pre_rerank(...)
    siblings_added = timings_ms.get("candidates_after_expansion", 0) - len(original_candidates)
    timings_ms["sibling_expansion_hit"] = 1.0 if siblings_added > 0 else 0.0
    timings_ms["sibling_expansion_count"] = float(siblings_added)
```

**Alert**: Nếu `sibling_expansion_hit` rate < 10% sau 7 ngày → `chunk_index`/`source` metadata không được populate đúng trên production Qdrant index. Regression test chỉ check type, không check population rate → đây là gap mà monitoring bắt được.

---

#### M3. Tavily Homepage Filter Rate

```python
# tavily_search.py — trong filter_results()
filtered_homepage_count = 0
for r in results:
    # ... existing filter logic ...
    if exclude_homepages:
        url = r.get("url", "")
        parsed = urlparse(url)
        path = (parsed.path or "").rstrip("/")
        if path in ("", "/vi", "/en", "/index", "/index.html"):
            filtered_homepage_count += 1
            continue
    # ...

# Return count as part of filter stats
return filtered, {"homepage_filtered": filtered_homepage_count}
```

```python
# flows.py — nơi gọi filter_results()
filtered, filter_stats = TavilySearch.filter_results(raw_results, ...)
timings_ms["tavily_homepage_filtered"] = float(filter_stats.get("homepage_filtered", 0))
```

**Alert**: Nếu `tavily_homepage_filtered` > 0 liên tục trong 2+ tuần rồi đột ngột về 0 → homepage URL structure đã thay đổi, filter cần update.

---

### Dashboard Card — AdminPage.tsx

Thêm tab `monitoring` vào [AdminPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/AdminPage.tsx):

```typescript
// AdminPage.tsx — thêm vào AdminTab type
type AdminTab = 'documents' | 'feedback' | 'monitoring';

// Tab definition
{ id: 'monitoring' as AdminTab, label: 'Monitoring' },
```

**API endpoint** (new):

```python
# routers/admin.py
@router.get("/admin/retrieval-metrics")
async def get_retrieval_metrics(days: int = 7):
    """Aggregate retrieval improvement metrics from query logs."""
    # Query MongoDB query_logs collection for timings_ms fields
    pipeline = [
        {"$match": {"created_at": {"$gte": datetime.now() - timedelta(days=days)}}},
        {"$group": {
            "_id": None,
            "total_queries": {"$sum": 1},
            "cliff_triggered_count": {
                "$sum": {"$cond": [{"$eq": ["$timings_ms.cliff_triggered", 1.0]}, 1, 0]}
            },
            "sibling_hit_count": {
                "$sum": {"$cond": [{"$eq": ["$timings_ms.sibling_expansion_hit", 1.0]}, 1, 0]}
            },
            "homepage_filtered_total": {
                "$sum": {"$ifNull": ["$timings_ms.tavily_homepage_filtered", 0]}
            },
        }},
    ]
    result = await db.query_logs.aggregate(pipeline).to_list(1)
    # ... format and return ...
```

**Frontend card** (4 stat cards matching existing pattern):

```tsx
// MonitoringTab component — follows same pattern as FeedbackTab stats cards
<div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
  <MetricCard
    label="Score Cliff Rate"
    value={`${metrics.cliffRate}%`}
    alert={metrics.cliffRate === 0 && metrics.totalQueries > 500}
    alertText="Cliff never triggers — review thresholds"
  />
  <MetricCard
    label="Sibling Hit Rate"
    value={`${metrics.siblingHitRate}%`}
    alert={metrics.siblingHitRate < 10}
    alertText="Low hit rate — check chunk_index metadata"
  />
  <MetricCard
    label="Homepage Filtered"
    value={metrics.homepageFiltered}
    alert={metrics.homepageFiltered === 0 && metrics.prevWeekFiltered > 0}
    alertText="Filter stopped catching — URL structure changed?"
  />
  <MetricCard
    label="Total Queries"
    value={metrics.totalQueries}
  />
</div>
```

**Effort**: ~2-3h (logging: 30m, API endpoint: 1h, dashboard card: 1h)
**Dependency**: None — uses existing `timings_ms` + MongoDB query_logs + AdminPage tab pattern

---

## Final Priority Matrix

| # | Task | Category | Effort | Impact | Dependency | Feature Flag |
|---|------|----------|--------|--------|------------|-------------|
| **A1** | Web query enrichment + homepage filter | 🟢 Do Now | 2h | 🔴 Critical | None | `web_query_enrichment_enabled` |
| **A2** | Expand no-info patterns | 🟢 Do Now | 30m | 🟡 Medium | None | N/A (additive) |
| **A3** | Regression test suite | 🟢 Do Now | 4h | 🔴 High | None | N/A (test-only) |
| **B1** | Adaptive score cliff (per-collection) | 🟡 Validate | 2h + histogram | 🟡 Medium | Eval data | `score_cliff_enabled` |
| **B2** | Per-collection normalization + weights | 🟡 Validate | 1-2d + benchmark | 🟡 Medium | Baseline bench | `per_collection_norm_enabled` |
| **C1** | Sibling expansion (before rerank) | 🔴 Arch Decision | 2-3d | 🔴 High | `get_by_metadata()` | `sibling_expansion_enabled` |
| **C2** | Context budget for expansion | 🔴 Arch Decision | 4h | 🟡 Medium | C1 | (follows C1 flag) |
| **C3** | Freshness Tavily suppression + null fix | 🟢 Do Now | 2h | 🟡 Medium | None | `freshness_tavily_check_enabled` |
| **C4** | Routing confidence pool increase | 🔴 Arch Decision | 4h | 🟡 Medium | None | `low_conf_pool_expand_enabled` |
| **D1** | Feedback→benchmark automation | ⏸️ Deferred | 3-5d | 🔴 High | ≥50 thumbs-down |
| **D2** | LLM no-info detection | ⏸️ Deferred | — | — | Provider change |
| **M** | Production monitoring (3 metrics + dashboard) | 🟢 Do Now | 2-3h | 🔴 High | A1+B1+C1 deployed | N/A (observability) |

---

## Feature Flags

> [!IMPORTANT]
> Mọi thay đổi ranking/retrieval behavior **PHẢI** có feature flag độc lập để rollback từng thành phần nếu có regression. Pattern từ C1 (`sibling_expansion_enabled: bool = False`) được áp dụng cho tất cả.

```python
# settings.py — thêm các flags
class Settings:
    # ... existing ...
    
    # ── Retrieval improvement flags (all default OFF) ──────────────
    web_query_enrichment_enabled: bool = False    # A1: academic year + homepage filter
    score_cliff_enabled: bool = False             # B1: per-collection score cliff
    per_collection_norm_enabled: bool = False     # B2: per-collection normalization
    sibling_expansion_enabled: bool = False       # C1: sibling chunk expansion
    freshness_tavily_check_enabled: bool = False  # C3: date_str freshness check
    low_conf_pool_expand_enabled: bool = False    # C4: 2x candidate pool in Tier 3
```

**Usage pattern** trong `flows.py`:

```python
if _cfg_bool(cfg, "score_cliff_enabled", False):
    reranked = _apply_score_cliff_per_collection(reranked)
# else: no cliff, original behavior preserved
```

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation | Rollback |
|------|--------|-----------|------------|----------|
| **C1**: `get_by_metadata()` returns empty (chunk_index stored as string, not int) | Sibling expansion silently produces nothing | Medium | Unit test `get_by_metadata()` trước khi wire vào pipeline. Verify chunk_index type in Qdrant payload. | Disable `sibling_expansion_enabled` |
| **B2**: Per-collection normalization thay đổi toàn bộ ranking | Regression trên các query đã hoạt động tốt | High | Benchmark before/after (nĐCG, MRR). Chỉ enable sau khi ΔnDCG ≥ 0 | Disable `per_collection_norm_enabled` |
| **C4**: 2x candidate pool tăng rerank latency | +~800ms-1s per query ở Tier 3 zone | Certain | Document as intentional trade-off. Chỉ Tier 3 zone (~5% queries) nên overall P50 latency không bị ảnh hưởng. | Disable `low_conf_pool_expand_enabled` |
| **B1**: Per-collection cliff cắt sai docs khi collection assignment sai | Relevant doc bị drop | Low | Score cliff chỉ cắt docs dưới gap lớn — nếu doc relevant thì score cao, không bị cắt | Disable `score_cliff_enabled` |
| **A1**: Academic year injection sai (edge case chưa anticipate) | Web search miss relevant results | Low | Homepage filter vẫn hoạt động độc lập. Regression test A3 catch failures. | Disable `web_query_enrichment_enabled` |

### C1 Pre-flight Check: `get_by_metadata()` Unit Test

```python
def test_get_by_metadata_chunk_index():
    """Verify chunk_index is int in Qdrant payload before enabling expansion."""
    from qdrant_client import QdrantClient
    client = QdrantClient(url="http://localhost:6333")
    
    # Sample a kehoach doc that has parent_id
    results, _ = client.scroll(
        collection_name="kehoach",
        limit=10,
        with_payload=True,
        with_vectors=False,
    )
    
    has_chunk_index = False
    for point in results:
        meta = point.payload.get("metadata", {})
        chunk_idx = meta.get("chunk_index")
        if chunk_idx is not None:
            has_chunk_index = True
            assert isinstance(chunk_idx, int), (
                f"chunk_index is {type(chunk_idx).__name__}, expected int. "
                f"Point ID: {point.id}, value: {chunk_idx!r}"
            )
            # Test actual lookup
            source = meta.get("source")
            if source and chunk_idx > 0:
                siblings, _ = client.scroll(
                    collection_name="kehoach",
                    scroll_filter={
                        "must": [
                            {"key": "metadata.source", "match": {"value": source}},
                            {"key": "metadata.chunk_index", "match": {"value": chunk_idx - 1}},
                        ]
                    },
                    limit=1,
                    with_payload=True,
                    with_vectors=False,
                )
                # If source has multiple chunks, sibling should exist
                total = meta.get("total_chunks", 0)
                if total > 1:
                    assert len(siblings) > 0, (
                        f"Sibling lookup failed for source={source}, "
                        f"chunk_index={chunk_idx-1}. Check Qdrant payload filter."
                    )
                break  # One successful test is enough
    
    assert has_chunk_index, "No kehoach docs have chunk_index metadata!"
    print("\u2705 get_by_metadata() pre-flight check passed")
```

---

## Execution Order (v5 — fixed dependency chain)

```
Day 1:  A1 (web query) + A2 (patterns) + A3 (regression tests) + C3 (freshness fix)
        → All behind feature flags, enable one-by-one after Day 1 verification

Day 2:  B1 (run histogram → decide cliff thresholds → implement behind flag)

Day 3:  C4 (candidate pool increase — behind flag)
        Note: C4 works independently of B2 because pool increase stays within
        single collection (no cross-collection normalization needed).

Day 4-5: C1 (sibling expansion) + C2 (context budget)
         Pre-flight: run get_by_metadata() unit test FIRST

Day 6-7: B2 (per-collection normalization — needs benchmark baseline)
         → B2 is the LAST ranking change: run full benchmark before/after
         → If B2 regresses, disable flag and investigate

Day 7+:  M (monitoring dashboard + logging)
         Wire 3 metrics into timings_ms, add AdminPage tab
         Start monitoring after all flags enabled

Later:  D1 (when feedback data sufficient), D2 (if provider changes)
```

> [!IMPORTANT]
> **Dependency clarification**: C4 (**pool increase**) và B2 (**per-collection normalization**) độc lập về mặt logic.
> - C4 chỉ tăng số candidates từ **cùng 1 collection** → không bị normalization bias
> - B2 thay đổi cách merge scores **giữa collections** → chỉ nhữ khi multi-collection search
> - C4 implement trước B2 là safe vì với v3 approach (top-2 collections) thì sẽ có dependency, nhưng v4+ approach (same collection pool increase) thì không.

---

## Verification Plan

### Day 1 Verification
```bash
# After A1+A2+C3 (all behind flags, enable one at a time):
python eval/regression_tests.py  # A3

# Web query should contain academic year
python -c "
from pipeline.flows import _build_web_search_query
q = _build_web_search_query('Lịch học kỳ mới nhất?', 'Lịch học kỳ mới nhất')
assert '2025' in q or '2026' in q, f'Missing year: {q}'
assert 'ĐHBKHN' in q, f'Missing CTT: {q}'
print(f'✅ {q}')
"

# Existing tests still pass
python -m pytest tests/ -q -m "not integration"
```

### Day 2-3 Verification
```bash
# B1: Histogram analysis before implementing cliff
python -c "
import json
# ... histogram code from B1 section ...
"

# C4: Pool increase doesn't break existing tests
python -m pytest tests/test_phase8.py -q

# C4 latency check (Tier 3 zone only):
# Verify rerank latency with 80 vs 40 candidates
# Expected: +800ms-1s (acceptable in Tier 3 zone where LLM call already adds 2-12s)
```

### Day 4-5 Verification
```bash
# C1 Pre-flight: MUST pass before enabling sibling expansion
python -m pytest tests/test_get_by_metadata.py -v

# C1+C2: Sibling expansion E2E
python -c "
# Test with known multi-chunk document
# Verify siblings appear in context AFTER all ranked docs
# Verify sibling budget does not exceed 30% of total
"
```

### Day 6-7 Verification
```bash
# B2: Full benchmark before/after
python -m evaluation.search_strategy_benchmark \
    --strategy hybrid_reranked \
    --output eval/baseline_global_norm.json

# Enable per_collection_norm_enabled, re-run:
python -m evaluation.search_strategy_benchmark \
    --strategy hybrid_reranked \
    --output eval/after_per_collection_norm.json

# Compare: MUST have ΔnDCG >= 0 to ship
python -c "
import json
b = json.load(open('eval/baseline_global_norm.json'))
a = json.load(open('eval/after_per_collection_norm.json'))
delta = a['ndcg@10'] - b['ndcg@10']
status = '✅' if delta >= 0 else '❌ REGRESSION'
print(f'{status} Baseline nDCG: {b[\"ndcg@10\"]:.4f}')
print(f'{status} After    nDCG: {a[\"ndcg@10\"]:.4f}')
print(f'Delta: {delta:+.4f}')
if delta < 0:
    print('⚠️  Disable per_collection_norm_enabled and investigate!')
"
```
