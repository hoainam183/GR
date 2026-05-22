# Module: `retrieval`

Source-verified: 2026-05-22 from every `retrieval/*.py` file, `config/settings.py`, `pipeline/flows.py`, and `agent/tool_adapters.py`.

## Purpose

`retrieval` owns the entire document search stack:

- **Vector search** — Qdrant with dual named BGE-M3 + E5 vectors.
- **Keyword search** — Elasticsearch BM25 with Vietnamese-friendly analysis.
- **Metadata pre-filtering** — per-collection ES filter chains that constrain both Qdrant and ES keyword search.
- **Multi-collection fusion** — parallel per-collection search → global pooling → score normalisation → weighted fusion.
- **Adaptive fusion weights** — automatically shift toward keyword-heavy scoring for course-like queries.
- **Recency boost** — `kehoach` documents get a score bonus proportional to freshness.
- **Structured query processing** — exclusion terms (`-keyword`) are parsed and applied as `must_not` clauses.
- **Validity filtering** — removes superseded regulation documents via `data/document_lineage.json`.
- **Cross-reference resolution** — detects Vietnamese legal references (Điều/Khoản) and injects same-document chunks.
- **Collection selection** — maps domain classification results to target collections with confidence-aware fallback.
- **`RetrievalService`** — shared singleton wrapping all infrastructure, injected into both pipeline and agent tools.

---

## File Map

```text
retrieval/
  __init__.py                  Public exports and create_retriever() factory.
  base.py                      BaseRetriever abstract interface.
  service.py                   RetrievalService — unified singleton for search operations.
  qdrant_store.py              QdrantStore — dual named-vector collection (BGE-M3 + E5).
  elasticsearch_store.py       ElasticsearchStore — BM25 keyword + metadata filter search.
  hybrid_search.py             Per-collection vector/keyword RRF fusion.
  multi_collection_search.py   Parallel global multi-collection search and fusion.
  metadata_filters.py          Per-collection filter extraction, major/cohort/date helpers, recency bonus.
  collection_selector.py       Domain → collection selection with confidence fallback.
  validity_filter.py           Drop superseded documents using data/document_lineage.json.
  reference_resolver.py        Resolve legal references such as Điều/Khoản.
  search_stsv.py               STSV hybrid search demo utility.
  index_stsv_to_es.py          ES indexing utility (scroll Qdrant → bulk-index to ES).
  config.py                    Retrieval configuration placeholder.
```

---

## RetrievalService

`RetrievalService.from_settings(settings)` is the canonical entry-point. It builds and holds:

| Component | Class | Purpose |
|-----------|-------|---------|
| `bge_embedder` | `BGEm3Embedder` | 1024-dim BGE-M3 dense embeddings |
| `e5_embedder` | `E5MultilingualEmbedder` | 1024-dim E5-multilingual dense embeddings |
| `searcher` | `MultiCollectionSearch` | Parallel hybrid search across all collections |
| `reranker` | `create_reranker(settings)` | Optional cross-encoder reranker |
| `tavily_tool` | `TavilySearchTool` | Optional web search tool |

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `embed_query` | `(query) → (bge_vec, e5_vec)` | Embed with both models |
| `search` | `(query, *, collections, top_k, resolved_major, resolved_cohort, rerank=True) → List[Dict]` | Full hybrid search + optional reranking |
| `web_search` | `(query, max_results=3) → Any` | Tavily web search |

### `search()` internals

1. Compute `effective_top_k` from `top_k` param or `settings.top_k`.
2. Set `raw_candidate_k = max(effective_top_k × 4, 20)` for over-fetching before rerank.
3. Embed query with both BGE-M3 and E5.
4. Call `searcher.search()` with `vector_top_k`, `keyword_top_k`, `vector_pool_k`, `keyword_pool_k` from settings.
5. If `rerank=True` and reranker exists → `reranker.rerank(query, documents, top_k)`.
6. Otherwise → truncate to `effective_top_k`.

This service is created once by `RAGPipeline` and injected into agent tools via `tool_adapters.set_retrieval_service()`.

---

## Store Contracts

### Qdrant (`QdrantStore`)

- One collection per domain (e.g. `stsv`, `quydinh`, `kehoach`, `ctdt`).
- **Named vectors**:
  - `bge_m3` — 1024 dimensions, cosine distance.
  - `e5` — 1024 dimensions, cosine distance.
- **Search params**: `hnsw_ef=128, exact=False`.
- **Per-vector over-fetch**: `per_vector_k = min(top_k × 2, 100)`.
- **Dual-vector fusion** (within Qdrant): runs two separate queries (one per vector), then fuses results via **weighted score fusion**:
  ```
  fused_score = bge_weight × bge_score + e5_weight × e5_score
  ```
  Default: `bge_weight=0.5, e5_weight=0.5`.
- Payload includes all metadata fields plus `text`.

### Elasticsearch (`ElasticsearchStore`)

- Index name matches collection name.
- **Analyzer**: Vietnamese-friendly — prefers `icu_tokenizer` + `icu_folding`; falls back to `standard` + `asciifolding` if ICU plugin is unavailable.
- **Mapped fields**:

  | Field | Type | Purpose |
  |-------|------|---------|
  | `text` | text | Main chunk content for BM25 scoring |
  | `title` | text + keyword | Document title; boosted 1.5× in keyword search |
  | `doc_id` | integer | Document-level identifier |
  | `type_doc` | keyword | Document type |
  | `time_create` | keyword | Creation timestamp |
  | `section_context` | keyword | Section context label |
  | `section_h2` | text | H2 heading; used for keyword boosting on curriculum queries |
  | `section_h3` | text | H3 heading; used for keyword boosting on curriculum queries |
  | `item_label` | keyword | Item label |
  | `chunk_index` | integer | Chunk position within document |
  | `total_chunks` | integer | Total chunks in source document |
  | `chunk_size` | integer | Chunk token/char count |
  | `has_links` | boolean | Whether chunk contains links |
  | `has_table` | boolean | Whether chunk contains tables |
  | `major_code` | keyword | Major programme code (e.g. `IT-E10`) |
  | `applicable_major` | keyword | Cohort applicability list (e.g. `["K63", "K64"]`) |
  | `date_str` | keyword | Posting date in `D/M/YYYY` format |
  | `document_type` | keyword | Document type label |
  | `major_name` | text + keyword | Full programme name |
  | `course_code` | keyword | Course code (e.g. `IT3080`) |
  | `course_name` | text + keyword | Course name |
  | `semester` | text + keyword | Semester label (e.g. `Học kỳ I`) |

- **BM25 keyword search** uses `multi_match` over `text^1.0` + `title^1.5` with `fuzziness=AUTO`.
- **Metadata-only search** (`metadata_filter_search`) uses `{bool: {filter: [...]}}` (no text scoring) — returns only `_id` strings.
- **Chunk ID resolution** (`resolve_chunk_ids_for_qdrant`): maps ES `_id` values to Qdrant point IDs. Fast path: direct `_id` match. Fallback path: tries `chunk_id`, `chunk_id.keyword`, `doc_id.keyword`, `doc_id` (int) fields.
- **Freshness query** (`get_latest_chunk_ids_by_date`): fetches up to 1000 docs with `date_str`, parses dates in Python, sorts descending, returns top `max_n` IDs.

---

## HybridSearch (Per-Collection)

`HybridSearch` fuses vector + keyword results for a **single collection** using **Reciprocal Rank Fusion (RRF)**.

### Flow

```text
1. Qdrant vector search (bge_m3 + e5 fused internally) → vector_top_k candidates
2. Parse structured query (exclusion terms)
3. ES BM25 keyword search → keyword_top_k candidates
4. Apply exclusion filter to both result sets
5. RRF fusion:
     fused_score = vector_weight × 1/(k + vector_rank)
                 + keyword_weight × 1/(k + keyword_rank)
   where k = rrf_k (default 60)
6. Optional filter by hybrid_score_threshold
7. Return top-K
```

### RRF formula

```
rrf_score(rank) = 1 / (k + rank)    # rank is 1-based
```

Documents appearing in only one list receive `0.0` for the missing component.

### Output fields

Each result dict contains: `id`, `text`, `metadata`, `score` (fused), `vector_score`, `keyword_score`, `vector_rank`, `keyword_rank`, `bge_score`, `e5_score`.

---

## MultiCollectionSearch (Global)

`MultiCollectionSearch` is the top-level search engine. It orchestrates parallel per-collection searches, then applies **global score fusion** across all collections.

### Full Search Pipeline

```text
Query + BGE/E5 vectors + active_collections
  │
  ├── Step 0: Structured query parsing (extract exclusion terms)
  ├── Step 0: Resolve adaptive fusion weights (course-query detection)
  │
  ├── Step 1: build_collection_filters() → per-collection CollectionFilter specs
  │           For each collection:
  │             → run ES metadata pre-search (fallback chain)
  │             → resolve Qdrant HasIdCondition filter + ES term filter
  │             → freshness path: fetch latest chunk IDs by date_str
  │
  ├── Step 2: Parallel per-collection fetch (ThreadPoolExecutor, max_workers=4)
  │           For each target collection:
  │             → Qdrant vector search (with optional HasIdCondition filter)
  │             → ES keyword search (with optional filter clause)
  │           Prefix all IDs with "{collection}/{id}" for global uniqueness.
  │
  ├── Step 3: Apply exclusion term filter to both result pools
  │
  ├── Step 4: Global vector pool
  │           → Sort all vector results by raw cosine score (desc)
  │           → Dedup by ID, keep top vector_pool_k
  │
  ├── Step 5: Global keyword pool
  │           → Sort all keyword results by BM25 score (desc)
  │           → Dedup by ID, keep top keyword_pool_k
  │
  ├── Step 6: Score fusion (linear or RRF mode)
  │           → See "Score Fusion" section below
  │
  ├── Step 7: kehoach recency bonus applied (+0.05 max)
  │
  ├── Step 8: Text-level deduplication (identical stripped text)
  │
  └── Step 9: Return top-K candidates
```

### Score Fusion

Two fusion modes are supported (selected via `fusion_mode` parameter):

#### Mode `"linear"` (default)

Min-max normalisation + weighted linear combination:

```
norm_vec = (score - v_min) / (v_max - v_min)     # [0, 1]
norm_kw  = (score - k_min) / (k_max - k_min)     # [0, 1]

final_score = vector_weight × norm_vec
            + keyword_weight × norm_kw
            + kehoach_recency_bonus(doc)
```

If all scores in a pool are identical, the range is treated as `1.0` (avoid division by zero).

#### Mode `"rrf"`

Rank-based Reciprocal Rank Fusion:

```
vector_rrf  = vector_weight × 1/(rrf_k + vector_rank)
keyword_rrf = keyword_weight × 1/(rrf_k + keyword_rank)

final_score = vector_rrf + keyword_rrf + kehoach_recency_bonus(doc)
```

`rrf_k` defaults to `60`.

### Adaptive Fusion Weights

For **course-like queries**, the system automatically shifts to keyword-heavy fusion to improve exact matching of course codes/names:

**Detection signals** (any triggers the shift):
- Course code regex: `\b(IT|MI|EE|ET|ME|CH|PH|MA|TL|FL|PE|ED)\d{4}[A-Z]?\b`
- Vietnamese keywords (case-insensitive): `"môn "`, `"môn học"`, `"mon "`, `"học phần"`, `"hoc phan"`, `"tín chỉ"`, `"tin chi"`, `"tiên quyết"`, `"tien quyet"`, `"song hành"`, `"song hanh"`, `"khối lượng"`, `"khoi luong"`

**Adaptive weight adjustment**:
```python
vector_weight = min(default_vector_weight, 0.4)
keyword_weight = max(default_keyword_weight, 0.6)
```

When no course signal is detected, the configured defaults are used.

### Default Parameters (from `config/settings.py`)

The `MultiCollectionSearch` constructor has its own defaults, but at runtime these are always overridden by values from `Settings`:

| Parameter | Settings default | Constructor default | Description |
|-----------|-----------------|--------------------|--------------|
| `vector_weight` | **0.8** | 0.7 | Weight for vector scores in fusion |
| `keyword_weight` | **0.2** | 0.3 | Weight for keyword scores in fusion |
| `rrf_k` | — | **60** | RRF constant |
| `max_workers` | — | **4** | Thread pool size for parallel collection search |
| `vector_top_k` | **50** | 20 | Candidates fetched from Qdrant per collection |
| `keyword_top_k` | **50** | 20 | Candidates fetched from ES per collection |
| `vector_pool_k` | **40** | 15 | Size of global vector candidate pool after dedup |
| `keyword_pool_k` | **40** | 15 | Size of global keyword candidate pool after dedup |
| `top_k` | **5** | 10 | Final number of results (before reranking, `×4` over-fetch) |
| `collections` | `["stsv", "quydinh", "kehoach", "ctdt"]` | — | Active collections |

> **Important**: The Settings values (`0.8`/`0.2`) are what actually run in production. The constructor defaults only apply when `MultiCollectionSearch` is instantiated directly without settings.

### Tracing

When `trace_out` dict is supplied to `search()`, the following fields are populated:

```python
trace_out = {
    "filters": {col_name: {"applied": bool, "matched_ids": int, "filter_desc": str}},
    "collection_counts": {col_name: {"vector": int, "keyword": int}},
    "fusion_weights": {"vector": float, "keyword": float, "reason": str, "mode": str},
    "structured_query": {"original": str, "cleaned": str, "exclude_terms": [str]},
    "excluded_counts": {"vector": int, "keyword": int},
}
```

---

## Metadata Filters

`metadata_filters.py` is the largest file in the module. It implements:

### Architecture (Pre-Search Flow)

```text
1. build_collection_filters(query, collections, resolved_major, resolved_cohort)
   → For each active collection, extract an ordered ES-filter fallback chain.

2. MultiCollectionSearch._resolve_filter_with_fallback()
   → Try each ES filter query in order.
   → First query returning ≥ 1 doc ID wins.

3. Winning IDs become:
   → Qdrant: HasIdCondition (restrict vector search to pre-filtered subset)
   → ES:    Filter clause (restrict keyword search to same subset)

4. If ALL queries in the chain return 0 results:
   → No filter applied (search entire collection).
```

### Per-Collection Filter Logic

#### `ctdt` — Curriculum / Programme

Extractor: `CtdtFilterExtractor`

Filter key: `major_code` (programme code like `IT-E10`, `ME1`, etc.)

Fallback chain (tried in order):
1. **`major_code` exact match** — `{term: {major_code: "IT-E10"}}` (most precise).
2. **`major_name` fuzzy match** — `{match: {major_name: {query: "...", fuzziness: "AUTO"}}}` (handles name variations).
3. **`major_code` exact OR `major_code` missing** — includes generic chunks that have no major-specific tag.
4. **No filter** — searched when all above return zero hits.

When no major signal is detected in query or `resolved_major` → no filter (empty `CollectionFilter`).

#### `quydinh` — Regulations

Extractor: `QuyDinhFilterExtractor`

Filter key: `applicable_cohort` (cohort codes like `["K63", "K64"]`).

Fallback chain:
1. **`applicable_cohort` match OR missing** — includes both cohort-specific and generic regulation chunks.
2. **No filter** — when no cohort signal is available.

Cohort detection priority:
1. Extract from query text (regex `\bK\s*\d{2,3}\b` or `khoá\s*K?\s*\d{2,3}`).
2. Fall back to `resolved_cohort` parameter.
3. Fall back to `resolved_major` (may contain cohort info).

#### `kehoach` — Plans / Notices

Extractor: `KeHoachFilterExtractor`

Filter key: `date_str` (posting date in `D/M/YYYY` format).

Priority order:
1. **Explicit month/year in query** → ES wildcard filter:
   - `"tháng 3 năm 2026"` → `{wildcard: {date_str: "*/3/2026"}}`
   - `"năm 2025"` → `{wildcard: {date_str: "*/2025"}}`
   - Academic terms like `2025.2`, `20252`, `2025-2` are **NOT** treated as posting dates (stripped before parsing).
   - School year patterns `2025-2026` or `năm học 2025-2026` are also stripped.
2. **Freshness intent** without explicit date → `sort_by_date_desc=True`:
   - Detection keywords (accent-folded): `mới nhất`, `gần đây`, `hiện tại`, `kỳ này`, `học kỳ mới`, `thông báo mới`, `latest`, `recent`, `newest`, `current semester`.
   - `MultiCollectionSearch` fetches the most-recent chunk IDs via `get_latest_chunk_ids_by_date(max_n=200)` and uses them as a hard `HasIdCondition`.
   - Both Qdrant vector search AND ES keyword search are constrained to these latest IDs.
3. **No signal** → empty filter; the **recency bonus** (+0.05 max) still applies at fusion time.

#### `stsv` — Student Support

No metadata pre-filter defined. `stsv` is intentionally omitted from `_COLLECTION_FILTER_REGISTRY`.

### Freshness Intent for Other Collections

`build_collection_filters()` also checks for freshness intent globally. If a query has freshness intent and the collection is in `_DATE_STR_FRESHNESS_COLLECTIONS = {"kehoach", "quydinh"}`, and the collection's extractor returned no filter, it upgrades to `sort_by_date_desc=True`.

### `kehoach` Recency Bonus

After fusion, every `kehoach` document receives an additive score bonus based on its `date_str`:

```python
KEHOACH_RECENCY_BONUS_MAX = 0.05      # maximum bonus
KEHOACH_RECENCY_DECAY_DAYS = 365      # full decay window

age_days = (today - doc_date).days
ratio = max(0, 1 - age_days / 365)
bonus = ratio × 0.05
```

- A document posted today gets `+0.05`.
- A document posted 6 months ago gets `+0.025`.
- A document older than 365 days gets `+0.0`.
- Non-`kehoach` documents always get `+0.0`.
- The bonus is added in **both** `linear` and `rrf` fusion modes.

### Major Code Handling

The module contains extensive normalisation and detection for HUST programme codes:

- **37+ programme codes** registered in `MAJOR_CODE_TO_NAME` (e.g. `IT-E10`, `ME1`, `BF-E12`, etc.).
- **Regex-based detection** via `MAJOR_PATTERNS`: list of `(regex, code)` tuples tried in order.
- **Alias mapping** via `MAJOR_NAME_ALIAS_MAPPING`: maps canonical names to accepted aliases/codes.
- **Unicode dash normalisation**: handles `–` (en dash), `—` (em dash), `−` (minus sign), `‐` (hyphen), etc.
- **Fuzzy code matching**: `IT E10`, `IT–E10`, `IT-E10`, `ITE10` all normalise to `IT-E10`.

Resolution priority for major:
1. `resolved_major` → direct code lookup → alias mapping → regex detection.
2. Query text → regex detection.

### Comparison Query Helpers

For multi-cohort or multi-major comparison queries:

- `build_cohort_comparison_subqueries_for_retrieval()`: splits `"so sánh quy định K70 và K67"` into separate per-cohort queries.
- `build_major_comparison_subqueries_for_retrieval()`: splits `"môn mạng máy tính của IT-E7 và IT-E6"` into separate per-major queries.
- `strip_major_from_query_for_retrieval()`: removes major mentions when major filtering is already applied via metadata, so keyword/semantic search focuses on the course intent.
- `expand_major_in_query_for_reranking()`: replaces codes with full names for better cross-encoder scoring.

### Adding a New Collection Filter

1. Subclass `BaseFilterExtractor` and implement `extract(query, resolved_major, resolved_cohort) → CollectionFilter`.
2. Register the instance in `_COLLECTION_FILTER_REGISTRY`.
3. No other files need to change.

---

## Collection Selection

`CollectionSelector` maps routed domains to collection names.

### Domain → Collections Mapping

```python
DOMAIN_TO_COLLECTIONS = {
    "ctdt":    ["ctdt"],
    "quydinh": ["quydinh", "stsv"],     # regulations ↔ student support overlap
    "kehoach": ["kehoach"],
    "stsv":    ["stsv", "quydinh"],      # student support ↔ regulations overlap
}
```

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `ALL_COLLECTIONS` | `["stsv", "quydinh", "kehoach", "ctdt"]` | All known collections |
| `MULTI_DOMAIN_FALLBACK` | `["quydinh", "stsv", "ctdt"]` | Low-confidence fallback set (includes `ctdt` for borderline course queries) |
| `CONFIDENCE_THRESHOLD` | `0.55` | Minimum confidence to trust domain prediction |

### Selection Logic

```text
Input: domain(s) from router, confidence score
  │
  ├─ No active domains
  │    → Search ALL collections
  │
  ├─ Active domains + confidence ≥ 0.55
  │    → Union of mapped collections (dedup, order preserved)
  │
  ├─ Active domains + confidence < 0.55
  │    → Keep mapped collections first (priority ordering)
  │    → Broaden with MULTI_DOMAIN_FALLBACK collections
  │    → (e.g. kehoach-routed query at low confidence → kehoach + quydinh + stsv + ctdt)
  │
  └─ Unknown domain label
       → Skip that domain, log warning
       → If all domains unknown → search ALL collections
```

Key design: when the route is locked to `kehoach` for freshness/dynamic plan queries, the confidence-based fallback broadening preserves `kehoach` first in the list, ensuring plan/notice results are prioritised over unrelated regulation/curriculum results.

---

## Validity Filter

`ValidityFilter` uses `data/document_lineage.json` to identify and remove superseded documents from search results.

### How It Works

1. On init, loads the lineage JSON and builds:
   - `_superseded_ids`: set of `doc_id` values with `status == "superseded"`.
   - `_superseded_patterns`: list of lowered filename stems for fuzzy matching.

2. During filtering, checks each result's `source` (or `title`) field against known superseded patterns (substring match).

3. **Safety guard**: if filtering would leave fewer than `min_results` (default `2`), the original unfiltered results are returned to avoid empty contexts.

4. `reload()` method supports hot-reloading after data updates.

---

## Reference Resolver

`ReferenceResolver` detects Vietnamese legal cross-references (e.g. `Điều 5`, `khoản 1 Điều 5`, `khoản 1 và khoản 2 Điều 5`) in retrieved chunks and inserts matching same-document chunks directly after the referencing chunk.

### Reference Detection

Two regex patterns:
- **Clause-first**: `"khoản 1 [và khoản 2] Điều 5"` — matches optional reference prefixes (`theo`, `xem`, `tại`, `căn cứ`, `quy định tại`, `nêu tại`).
- **Article-first**: `"Điều 5 [khoản 1 [và khoản 2]]"` — same prefix support.

Multiple references to the same article are merged (clause lists combined).

### Resolution Strategy

For each reference in each result chunk:

1. **Metadata lookup** (preferred, fast ~5ms):
   - Get the `document_id` and `collection` from the source chunk's metadata.
   - Scroll Qdrant by `document_id` filter (page_size=128, max_points=500).
   - Match chunks where `section_h3` heading or text body contains `Điều {article}` heading.
   - Sort: prefer non-parent chunks; prefer chunks containing the target clause number; sort by `chunk_index`.

2. **Semantic search fallback**:
   - Build query: `"Điều {article} {filename}"`.
   - Run `RetrievalService.search()` with `rerank=True`, constrained to the source collection.
   - Filter results to same document (by `document_id`, or `source`/`filename` match).
   - Filter to chunks matching the article heading.

### Limits

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_refs_per_chunk` | `2` | Max references resolved per source chunk |
| `max_total_refs` | `3` | Max total reference chunks added across all results |
| `scroll_page_size` | `128` | Qdrant scroll batch size |
| `scroll_max_points` | `500` | Max Qdrant points scanned per metadata lookup |

### Deduplication

- By `{collection}/{id}` composite keys.
- By raw `id` (handles both prefixed and unprefixed forms).
- By text content (first 200 chars) to avoid duplicate parent/child chunks.

Resolved chunks are marked with `_cross_reference=True`, `_referenced_from`, and `_reference` metadata.

---

## Structured Query Processing

`MultiCollectionSearch` uses `parse_structured_query()` (from `query.structured_query`) to detect explicit exclusion terms in the query (e.g. `"quy định -tín chỉ"`).

- Exclusion terms are applied as:
  - Qdrant: post-filter on vector result text + title + course_code + course_name fields.
  - ES: `must_not` clauses via `build_es_must_not_clauses()`.

---

## ID Conventions

- **Within a collection**: raw Qdrant point ID (UUID string) = ES `_id`.
- **Across collections** (runtime): `"{collection}/{point_id}"` composite format.
- `resolve_chunk_ids_for_qdrant()` guards against ID-level mismatches between metadata filtering and vector search.

---

## Maintenance Notes

- Preserve `{collection}/{id}` style runtime IDs when merging across collections.
- Keep metadata field names aligned with `data/MODULE.md` and indexing scripts.
- When adding a collection:
  1. Update settings / `.env` collections list.
  2. Add extractor class in `metadata_filters.py` and register in `_COLLECTION_FILTER_REGISTRY`.
  3. Add domain mapping in `collection_selector.py`.
  4. Update agent aliases, indexing scripts, eval data, and docs.
- When changing fusion/scoring, run current policy eval and search strategy benchmark.
- `date_str` is stored as keyword `"D/M/YYYY"` — not a native ES date field, so sorting requires Python-side parsing.
- The `fallback_analyzer` in ES uses `standard` tokenizer as a safe fallback when the ICU plugin is missing.

---

## Useful Checks

```bash
python -m py_compile retrieval/*.py
python -m pytest tests/test_multi_collection_fusion.py tests/test_reference_resolver.py retrieval/test_metadata_filters.py retrieval/test_hybrid_search.py -q -m "not integration"
```
