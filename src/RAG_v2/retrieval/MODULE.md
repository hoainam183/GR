# Module: `retrieval`

Source-verified: 2026-06-24 from every `retrieval/*.py` file (`__init__.py`, `base.py`, `service.py`, `qdrant_store.py`, `elasticsearch_store.py`, `exam_schedule_store.py`, `hybrid_search.py`, `multi_collection_search.py`, `metadata_filters.py`, `collection_selector.py`, `query_expander.py`, `hyde.py`, `parent_context.py`, `validity_filter.py`, `reference_resolver.py`, `config.py`), plus routing integration points in `query/router.py`, `query/complexity_router.py`, `query/signals.py`, `pipeline/rag_pipeline.py`, `pipeline/flows.py`, `config/settings.py`, and `tools/tavily_search.py`.

## Purpose

`retrieval` owns the entire document search stack:

- **Vector search** — Qdrant with dual named BGE-M3 + E5 vectors, batched in one round-trip and fused via per-model max-normalised weighting.
- **Keyword search** — Elasticsearch BM25 with a CocCoc Vietnamese-tokenizer analyzer (synonyms, stopwords, ASCII-folding), custom BM25 similarity, phrase boosting and a fuzzy fallback pass.
- **Metadata pre-filtering** — per-collection ES filter fallback chains that constrain both Qdrant (`HasIdCondition`) and ES keyword search.
- **Multi-collection fusion** — parallel per-collection search → global pooling → score normalisation → weighted fusion (linear or RRF).
- **Adaptive fusion weights** — shift toward keyword-heavy scoring for course-like and exact-policy queries.
- **Recency boost** — `kehoach` documents get an additive score bonus proportional to freshness.
- **Parent/child handling** — parent chunks are excluded from search; child results are optionally enriched with parent content.
- **Structured query processing** — exclusion terms (`-keyword`) are parsed and applied as `must_not` clauses + post-filters.
- **Validity filtering** — removes superseded regulation documents via `data/document_lineage.json` (invoked by the pipeline, not by `RetrievalService.search()`).
- **Cross-reference resolution** — detects Vietnamese legal references (Điều/Khoản) and injects same-document chunks (pipeline-invoked).
- **Collection selection** — maps domain classification + query signals to target collections with confidence-aware fallback.
- **`RetrievalService`** — shared singleton wrapping all infrastructure, with a TTL search cache, multi-query and HyDE paths, injected into both pipeline and agent tools.

---

## Routing Boundary

Routing is split across `query`, `pipeline`, and `retrieval`; `retrieval` owns only collection selection and metadata-scoped search.

### End-to-End Classic RAG Route

```text
Chat/API request
  -> RAGPipeline.query_v3/query_stream
  -> ComplexityRouter.route(query)
       - chitchat: canned/LLM chitchat flow, no retrieval
       - simple: classic RAG flow
       - complex: planner/agent path, with fallback to classic RAG when allowed
  -> QueryRouter.route(query, chat_history)
       - default mode: local DomainClassifier, not LLM
       - returns intent, primary domain, domains, confidence, probabilities
  -> optional Tier-3 LLM domain fallback
       - only when confidence < 0.55 and top-vs-second margin < 0.25
  -> optional QueryReflector
       - rewrites follow-up queries and extracts entities before retrieval
  -> RAGPipeline._reroute_reflected(search_query)
       - reroutes the reflected standalone query without history to reduce topic bleed
  -> CollectionSelector.select(...)
       - deterministic domain/probability/query-signal to collection mapping
  -> pipeline `_should_lock_kehoach_route(...)`
       - may force target_collections = ["kehoach"] for clear schedule/freshness routes
  -> MultiCollectionSearch.search(active_collections=target_collections)
       - metadata filters, vector+keyword search, global fusion
```

### Upstream Query Routing Details

`ComplexityRouter` (`query/complexity_router.py`) is the first route gate:

- `chitchat` is matched by hardcoded greeting/acknowledgement/identity/thanks/bye regexes and does not enter retrieval.
- `simple` is the default route when no complex signal is found.
- Single-fact policy/table lookups stay `simple` when they have lookup signals (`bao nhieu`, `may`, `muc nao`, `diem ren luyen`, table/code signals, etc.) and do not look comparative/multi-topic. This is why one-shot questions such as "co bao nhieu ..." should not automatically require an agent.
- `complex` is triggered by hardcoded comparison, multi-source, personal eligibility, repeated request connector, multi-step connector, multiple-question, long multi-topic, or high conjunction-count patterns. Complex routes go to the planner/agent path when available.

`QueryRouter` (`query/router.py`) is the domain/intent classifier:

- Valid intents are `chitchat`, `rag`, `tool_search`; fallback intent is `rag`.
- Valid RAG domains are `ctdt`, `quydinh`, `kehoach`, `stsv`.
- Default mode is `classifier`, which uses `DomainClassifier`; `llm` mode exists but is not the production default.
- The classifier route is two-pass: pass 1 classifies the raw query. Pass 2 prepends up to the last 5 history messages only when raw confidence `< 0.65` and the query has fewer than 6 words; the history-augmented result is kept only if its confidence is higher.
- The route result supplies `domain`, `domains`, `confidence`, `label`, and `probabilities`; `CollectionSelector` consumes these values later.

### Does Routing Need an LLM?

Normal local routing does **not** require an LLM:

- `ComplexityRouter` is regex/signal/heuristic based.
- `QueryRouter` defaults to `router_mode="classifier"` and uses `DomainClassifier`.
- `CollectionSelector` is deterministic.
- `metadata_filters.build_collection_filters()` is deterministic.
- `MultiCollectionSearch` routing/filtering/fusion is deterministic.

LLM usage is optional and upstream of retrieval:

- `QueryRouter(mode="llm")` exists, but the production default is `classifier`.
- Tier-3 domain fallback calls the chat LLM only for low-confidence classifier output without a dominant top domain (`confidence < 0.55`, margin `< 0.25`).
- `QueryReflector` uses the configured reflection LLM when `reflection_enabled=True` to rewrite follow-ups and extract entities before collection selection.
- Agent/planner mode uses LLMs for complex queries, but it still calls retrieval tools underneath.
- HyDE uses an LLM only if the HyDE fallback path is enabled and triggered after low-recall reranking.
- Tavily web search is a post-retrieval fallback/augmentation path, not the local collection router.

### Routing Settings Caveat

`Settings.domain_confidence_threshold` exists and defaults to `0.65`, but the classic `rag_flow` module-level selector is instantiated as `_collection_selector = CollectionSelector()` and therefore uses the selector default `CONFIDENCE_THRESHOLD = 0.55`. Changing `domain_confidence_threshold` alone does not currently change production collection selection unless the selector construction is also wired to that setting.

---

## File Map

```text
retrieval/
  __init__.py                  Public exports and create_retriever() factory.
  base.py                      BaseRetriever abstract interface (search()).
  service.py                   RetrievalService singleton + _SearchResultCache (TTL/LRU).
  qdrant_store.py              QdrantStore — dual named-vector collection (BGE-M3 + E5), batched search + fusion, CRUD/metadata helpers.
  elasticsearch_store.py       ElasticsearchStore — BM25 keyword + metadata-filter search, CocCoc Vietnamese analyzer, ID resolution, freshness query.
  exam_schedule_store.py       ExamScheduleStore — specialized Elasticsearch search for exam schedules, formatting results into Markdown tables.
  hybrid_search.py             HybridSearch — per-collection vector/keyword RRF fusion (DEPRECATED in main flow; used by tests/demo).
  multi_collection_search.py   MultiCollectionSearch — parallel global multi-collection search and fusion.
  metadata_filters.py          Per-collection filter extractors, major/cohort/date helpers, comparison subqueries, recency bonus.
  collection_selector.py       Domain + signals → collection selection with confidence fallback and augmentation.
  query_expander.py            MultiQueryExpander — multi-query variants for recall-oriented searches.
  hyde.py                      HyDEExpander + should_use_hyde() — optional hypothesis-embedding fallback.
  parent_context.py            ParentContextExpander — attach parent chunk content to child results.
  validity_filter.py           ValidityFilter — drop superseded documents using data/document_lineage.json.
  reference_resolver.py        ReferenceResolver — resolve legal references such as Điều/Khoản.

  config.py                    HyDE fallback config constants (mirrored in config/settings.py; HYDE_ENABLED defaults to False here).
```

---

## RetrievalService

`RetrievalService.from_settings(settings)` is the canonical entry-point. It builds and holds:

| Component | Class | Purpose |
|-----------|-------|---------|
| `bge_embedder` | `BGEm3Embedder` | 1024-dim BGE-M3 dense embeddings |
| `e5_embedder` | `E5MultilingualEmbedder` | 1024-dim E5-multilingual dense embeddings |
| `searcher` | `MultiCollectionSearch` | Parallel hybrid search across collections (via `create_retriever`) |
| `reranker` | `create_reranker(settings)` | Optional cross-encoder reranker |
| `tavily_tool` | `TavilySearchTool` | Optional web search tool (created only with a valid API key) |
| `_search_cache` | `_SearchResultCache` | TTL/LRU cache (maxsize=128, ttl=180s) of pre-rerank results |

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `embed_query` | `(query) → (bge_vec, e5_vec)` | Embed with both models |
| `search` | `(query, *, collections=None, top_k=None, resolved_major=None, resolved_cohort=None, rerank=True, entities=None, use_multi_query=False) → List[Dict]` | Hybrid search + optional reranking + optional multi-query/parent expansion |
| `search_with_hyde` | `(query, llm, *, collections=None, top_k=None, resolved_major=None, resolved_cohort=None) → List[Dict]` | HyDE fallback: BGE vector from hypothesis, E5 from original query; returns un-reranked top-k |

Tavily calls are made through the pipeline/agent tool layer; `RetrievalService` only holds the optional `tavily_tool` for wiring.

### `search()` internals

1. `effective_top_k = top_k or settings.top_k`.
2. `multiplier = max(float(raw_candidate_multiplier), 1.0)` (default `4.0`); `min_pool = max(int(raw_candidate_min), 1)` (default `20`); `raw_candidate_k = max(round(effective_top_k * multiplier), min_pool)`.
3. `active_collections = collections or settings.collections`.
4. If `use_multi_query and entities`: build up to 3 variants with `MultiQueryExpander`; if >1 variant → `_search_multi_query` (per-variant budget = `raw_candidate_k // len(variants)`, min 10; merge+dedup by id; rerank merged pool with variant[0]).
5. Otherwise `_search_single`:
   - Check `_search_cache` keyed by (query, collections, resolved_major, resolved_cohort). On miss, embed both vectors and call `searcher.search()` with `vector_top_k`/`keyword_top_k`/`vector_pool_k`/`keyword_pool_k` from settings, then cache the **pre-rerank** results.
   - If `rerank` and reranker exists → `reranker.rerank(query, documents, top_k=effective_top_k)`. Else truncate to `effective_top_k`.
   - If `settings.parent_context_enabled` → `_expand_parent_context()` enriches child results with parent content (grouped per collection).

`RetrievalService` is created once by `RAGPipeline` (`from_settings`) and injected into agent tools via `tool_adapters.set_retrieval_service()`.

### `search_with_hyde()` internals

- `raw_candidate_k = max(round(effective_top_k * multiplier), 40)` — floor is 40, not `min_pool`, to protect recall on small top_k / list queries.
- BGE vector comes from the hypothesis embedding; E5 uses the original query directly.
- No reranking — caller is responsible for reranking the merged pool.

---

## Module Flow

```mermaid
flowchart TD
  Caller["pipeline/rag_pipeline.py or agent/tool_adapters.py"] --> Service["RetrievalService.search"]
  Service --> Cache["_SearchResultCache (TTL/LRU)"]
  Service --> Embed["embedding/BGE + E5 embed_query"]
  Service --> Searcher["MultiCollectionSearch.search"]
  Searcher --> Signals["query/signals.analyze_query_signals"]
  Searcher --> Struct["query/structured_query.parse_structured_query"]
  Searcher --> Filters["metadata_filters.build_collection_filters"]
  Filters --> ESFilter["ES metadata pre-search (fallback chain)"]
  ESFilter --> IDFilter["Qdrant HasIdCondition + ES filter clause"]
  Searcher --> Vector["QdrantStore.search (batched bge_m3 + e5, level!=parent)"]
  Searcher --> Keyword["ElasticsearchStore.keyword_search (level!=parent)"]
  Vector --> Fusion["global linear/RRF fusion + kehoach recency bonus"]
  Keyword --> Fusion
  Fusion --> Dedup["id + text dedup; keyword pin / stsv evidence"]
  Dedup --> Service
  Service --> Rerank["reranking/BGEReranker (optional)"]
  Rerank --> Parents["ParentContextExpander (if enabled)"]
  Parents --> Caller
  Caller --> Validity["ValidityFilter (pipeline-invoked)"]
  Caller --> References["ReferenceResolver (pipeline-invoked)"]
  Caller -. low recall .-> HyDE["RetrievalService.search_with_hyde"]
```

External module boundaries:

- Receives routed collections/entities/resolved major+cohort from `query`/`pipeline`; it does not decide chat mode or final answer wording.
- Owns Qdrant/Elasticsearch access and returns normalised candidate dicts for `pipeline`, `agent`, `api`, and `evaluation`.
- Consumes `embedding` and `reranking` instances built by `RetrievalService.from_settings()`.
- `ValidityFilter` and `ReferenceResolver` are constructed and called by `RAGPipeline`, not inside `RetrievalService.search()`; `ReferenceResolver` itself calls back into `RetrievalService.search()` for its semantic fallback.
- Reads metadata/lineage conventions from `data/` and must stay aligned with `scripts`/`chunking` output fields.

---

## Store Contracts

### Qdrant (`QdrantStore`)

- One collection per domain (e.g. `stsv`, `quydinh`, `kehoach`, `ctdt`); `DEFAULT_COLLECTION = "stsv"`.
- **Named vectors** (`VECTOR_CONFIGS`): `bge_m3` and `e5`, each 1024 dims, cosine distance.
- **Search params**: `hnsw_ef=128, exact=False`.
- **Per-vector over-fetch**: `per_vector_k = min(top_k × 2, 100)`.
- **Batched search**: both named-vector queries run in a single `query_batch_points` round-trip, then `_fuse_results()` combines them.
- **Dual-vector fusion** (within Qdrant): per-model **max-normalisation** of bge/e5 scores (divide by per-model max, not min-max), then `fused = bge_weight × norm_bge + e5_weight × norm_e5` (default weights `0.5/0.5`). A doc not retrieved by a model keeps contribution 0; docs with score 0 are treated as absent. The max is the largest raw score in that model's result set (1.0 if empty).
- Result dicts: `{"id", "text", "metadata", "score", "bge_score", "e5_score"}`.
- Other helpers: `index_documents`, `get_by_ids`, `get_by_metadata` (returns `collection` too), `update_metadata_by_ids`, `update_metadata_batch`, `update_metadata_by_filter`, `delete_by_metadata`, `count`, `delete_collection`.

### Elasticsearch (`ElasticsearchStore`)

- Index name matches collection name; `DEFAULT_INDEX = "stsv"`. Connection is verified with `ping()` (raises `ConnectionError` on failure).
- **Analyzer** (`vietnamese_analyzer`): CocCoc `vi_tokenizer` when the plugin is present, else `standard` tokenizer fallback. Filter chain: `lowercase`, `vietnamese_synonym` (Vietnamese academic synonym list), `vietnamese_stop` (Vietnamese stopwords), `vietnamese_ascii_folding` (asciifolding, `preserve_original`). `_index_uses_vi_tokenizer()` detects plugin mode on existing indices; `uses_vietnamese_plugin` flag drives Python-side segmentation fallback in `keyword_search`. `INDEX_SETTINGS` is exported for legacy callers/tests (built with `use_vietnamese_plugin=True`).
- **Note**: `_make_settings(use_icu=True)` is a backward-compatible wrapper — `use_icu=True` maps to `vi_tokenizer` path, `use_icu=False` maps to `standard` fallback.
- **Similarity**: custom BM25 `custom_bm25` (`k1=1.5, b=0.5`); shards=1, replicas=0.
- **Text fields** (custom analyzer; `+keyword` subfield where noted): `search_text`, `text`, `title`(+kw), `doc_title`(+kw), `hierarchy_path`(+kw), `section_context`(+kw), `section_h1..h4`(+kw), `course_name`(+kw), `semester`(+kw), `major_name`(+kw).
- **Keyword fields**: `type_doc`, `time_create`, `item_label`, `major_code`, `applicable_cohort`, `applicable_major`, `date_str`, `document_type`, `course_code`, `level`, `chunk_id`, `readable_id`, `parent_id`, `collection`, `source_file`.
- **Integer/boolean fields**: `doc_id`, `chunk_index`, `total_chunks`, `chunk_size` (int); `has_links`, `has_table` (bool).
- **`search_text`** is auto-built at index time (`_build_search_text`) from text + selected metadata, with Markdown/table cleanup and accent-folded dedup, unless already provided.
- **`keyword_search`** (the main keyword path used by `MultiCollectionSearch`):
  - `must`: `multi_match` (best_fields, OR) over `_KEYWORD_SEARCH_FIELDS` (boosted: `search_text^3`, `title^2`, `doc_title^1.8`, `text^1.6`, `hierarchy_path^1.5`, `section_h1^1.4`, `section_h2^1.4`, `section_h3^1.3`, `section_h4^1.1`, `course_name^1.8`, `major_name^1.2`, `semester^1.2`, `section_context^1`, `item_label^1`).
  - `should`: optional segmented-query boost (×1.5, fallback mode only), per-key-phrase `match_phrase` boosts across text/heading fields (generic policy phrases get lower boost of 1.5; non-generic top-3 get boost 10, rest 5), `has_table` term boost (2.5) when `table_lookup` signal set, and a `terms` on `course_code` (boost 8.0) when structured query contains course codes.
  - `must_not`: structured-query exclusion clauses (`build_es_must_not_clauses`) **plus `{"term": {"level": "parent"}}`** so parent chunks are never keyword hits.
  - `filter`: optional caller-supplied filter dict.
  - Scores bumped ×1.2 for table hits when `table_lookup` is set; results carry `_keyword_search_mode` and `_keyword_table_lookup_hit` in metadata.
  - **Fuzzy fallback**: if exact pass returns nothing (or fewer than `top_k` and not in exact-policy/table mode), a second `multi_match` with `fuzziness=AUTO` runs and results are merged (`_merge_keyword_results`).
  - Returns `{"id", "text", "metadata", "score"}`.
- **Metadata-only search** (`metadata_filter_search`): wraps the supplied query in `{bool:{filter:[...]}}` (no scoring, `source=False`) and returns matching `_id` strings (default cap 1000).
- **Chunk ID resolution** (`resolve_chunk_ids_for_qdrant`): fast path = direct `ids` query; fallback = `terms` over `chunk_id`, `chunk_id.keyword`, `doc_id.keyword`, and integer `doc_id`. Returns deduped ES `_id` list.
- **Freshness query** (`get_latest_chunk_ids_by_date`): fetches up to 1000 docs that have `date_str`, parses `D/M/YYYY` in Python, sorts descending, returns top `max_n` (default 200) `_id` values.
- Other helpers: `index_documents` (bulk, refreshes index), `update_metadata_batch`, `delete_by_metadata`, `count`, `delete_index`, `recreate_index`.

---

## HybridSearch (Per-Collection, deprecated in main flow)

`HybridSearch.search()` fuses single-collection vector + keyword results via RRF. **It is not used by the production flow** — `MultiCollectionSearch._fetch_one()` calls `hybrid.qdrant.search()` and `hybrid.es.keyword_search()` directly. `HybridSearch` is retained for unit tests.

- `rrf_score(rank, k=60) = 1/(k + rank)`; `fused = vector_weight × rrf(v_rank) + keyword_weight × rrf(k_rank)`; missing component = 0.
- Optional `hybrid_score_threshold` filter; exclusion terms applied to both lists.
- Output dicts: `id`, `text`, `metadata`, `score`, `vector_score`, `keyword_score`, `vector_rank`, `keyword_rank`, plus pass-through `bge_score`/`e5_score`.

---

## MultiCollectionSearch (Global)

`MultiCollectionSearch` is the top-level engine: parallel per-collection search then global fusion.

### Full Search Pipeline

```text
search(query, bge_m3_query, e5_query, ...active_collections, fusion_mode="linear", trace_out=None)
  │
  ├── Resolve target searchers from active_collections (skip unregistered; fall back to all if none match).
  ├── Parse structured query (exclusion terms) + analyze_query_signals.
  ├── exact_policy_mode = exact_policy_lookup OR table_lookup
  │     → effective_keyword_top_k = max(keyword_top_k, 120)
  │     → effective_keyword_pool_k = max(keyword_pool_k, 80)
  ├── Resolve adaptive fusion weights (course-query / exact-policy bias).
  │
  ├── Step 0: build_collection_filters() → per-collection CollectionFilter specs
  │           (disable_metadata_filter_collections forces empty filters per call)
  │           For each collection → _resolve_filter_with_fallback():
  │             → freshness path: get_latest_chunk_ids_by_date → HasIdCondition + ES ids filter
  │             → else try each ES metadata query in order; first non-empty wins
  │             → ES-empty path: translate simple exact term/terms into a Qdrant payload filter
  │             → else no filter
  │
  ├── Step 1: Parallel per-collection fetch (ThreadPoolExecutor, max_workers=4)
  │           Each Qdrant filter is merged with a must_not level=parent condition.
  │           Qdrant vector search (level!=parent) + ES keyword_search (level!=parent).
  │           Prefix every ID as "{collection}/{id}"; attach "collection".
  │           Failed collections are logged and skipped (counts recorded with "error").
  │
  ├── Step 2: Apply exclusion-term filter to both pools (text/title/course_code/course_name).
  ├── Step 3: Sort vector pool by raw score, dedup by ID, keep vector_pool_k.
  ├── Step 4: Sort keyword pool by score, dedup by ID, keep effective_keyword_pool_k.
  │           exact_policy_mode → _pin_keyword_hits() forces table/phrase hits into the pool.
  ├── Step 5: Fusion — fusion_mode "linear" (default) or "rrf"; both add kehoach recency bonus.
  ├── Step 6: procedural_support signal → _ensure_collection_evidence(collection="stsv")
  │           keeps at least one stsv support doc in the final list.
  └── Return top-K (after text-level dedup inside fusion).
```

### Score Fusion

#### Mode `"linear"` (default)

**Max-normalise** each pool independently (divide each score by the pool maximum, not min-max). This preserves relative magnitude and avoids setting the lowest-scoring doc to zero:

```
v_max = vector_pool[0]["score"]   # pool is pre-sorted descending
k_max = keyword_pool[0]["score"]
norm_vec = score / v_max
norm_kw  = score / k_max
final = vector_weight * norm_vec + keyword_weight * norm_kw + kehoach_recency_bonus(doc)
```

After fusion, results are text-deduplicated (identical stripped text dropped).

#### Mode `"rrf"`

```
final = vector_weight × 1/(rrf_k + v_rank) + keyword_weight × 1/(rrf_k + k_rank)
      + kehoach_recency_bonus(doc) × (1 / (rrf_k + 1))
```

`rrf_k` defaults to `60`. The recency bonus is **rescaled** by `1/(rrf_k+1)` (≈0.016 for k=60) so it stays a ~5% nudge relative to RRF magnitude rather than dominating. Same text-level dedup applies.

### Adaptive Fusion Weights

`_resolve_fusion_weights(query)`:

- **Course-like queries** (course-code regex `\b(IT|MI|EE|ET|ME|CH|PH|MA|TL|FL|PE|ED)\d{4}[A-Z]?\b`, or hints `môn`, `môn học`, `học phần`, `tín chỉ`, `tiên quyết`, `song hành`, `khối lượng`, …, accented/unaccented) → `vector = min(default, 0.4)`, `keyword = max(default, 0.6)`, reason `course_query_keyword_bias`.
- Otherwise configured defaults (reason `default`).
- **Exact-policy mode** then applies on top of whichever reason was chosen: `vector = min(vector, 0.1)`, `keyword = max(keyword, 0.75)`, reason updated to `exact_policy_keyword_bias` (or `{prior}+exact_policy` if a course bias was already active).

### Default Parameters

| Parameter | Settings default | Constructor default | Description |
|-----------|-----------------|--------------------|--------------|
| `vector_weight` | **0.8** | 0.7 | Vector weight in global fusion |
| `keyword_weight` | **0.2** | 0.3 | Keyword weight in global fusion |
| `rrf_k` | — | **60** | RRF constant (global + per-collection) |
| `max_workers` | — | **4** | Thread pool size |
| `vector_top_k` | **50** | 20 | Qdrant candidates per collection |
| `keyword_top_k` | **50** | 20 | ES candidates per collection (raised to ≥120 in exact-policy mode) |
| `vector_pool_k` | **40** | 15 | Global vector pool after dedup |
| `keyword_pool_k` | **40** | 15 | Global keyword pool after dedup (≥80 in exact-policy mode) |
| `top_k` | **7** | 10 | Final results before reranking |
| `raw_candidate_multiplier` | **4.0** | — | Candidate over-fetch multiplier before rerank (`effective_top_k * multiplier`) |
| `raw_candidate_min` | **20** | — | Minimum candidate pool before rerank |
| `collections` | `["stsv", "quydinh", "kehoach", "ctdt"]` | — | Active collections |

> The Settings values are what run in production; `create_retriever()` passes `vector_weight`/`keyword_weight` from settings. Per-call `vector_top_k`/pool_k/etc. come from `RetrievalService`.

### Rerank Runtime Defaults

`rag_flow` passes reranker controls through `_reranker_kwargs(cfg, top_k_value)`:

| Setting | Default | Meaning |
|---------|---------|---------|
| `reranker_score_threshold` | **0.0** | Minimum regular chunk score kept by the BGE reranker |
| `reranker_table_score_threshold` | **-1.0** | Relaxed score threshold for chunks with `metadata.has_table` |
| `reranker_min_top_k` | **3** | Keep at least this many best scored docs, capped by `top_k`, even if below threshold |

`low_retrieval_confidence` in the web-fallback gate is not a separate configured threshold. It is set when `rag_flow` has to use `rerank_raw_fallback`: first rerank produced no docs or only negative-score docs, retrying with the original question still failed the same quality check, and the flow fell back to raw top-K by fusion score.

### Convenience accessors

`collection_names`, `qdrant_stores` (name → `QdrantStore`), `collection_counts()` (per-collection qdrant/es doc counts), and `get_by_metadata(collection, filters, limit)` for sibling lookups.

**Caution**: `get_by_metadata` calls `hybrid.qdrant.get_by_metadata()` (the attribute is `hybrid.qdrant`, not `hybrid.qdrant_store`).

### Tracing

When `trace_out` is supplied, it is populated with: `filters` (per-collection applied/matched_ids/filter_desc), `collection_counts`, `fusion_weights` (vector/keyword/reason/mode), `structured_query`, `query_signals`, `candidate_pool_sizes` (vector/keyword pool + effective keyword top_k/pool_k), `pinned_keyword_hits`, and `excluded_counts`.

---

## Metadata Filters

`metadata_filters.py` builds the pre-search filter chains and the major/cohort/date helpers.

### `CollectionFilter`

Dataclass with `metadata_es_queries` (ordered ES filter-only fallback chain) and `sort_by_date_desc` (freshness mode). `is_empty` ⇔ no queries. Explicit date/term queries take priority over `sort_by_date_desc`.

### Pre-Search Flow

```text
1. build_collection_filters(query, collections, resolved_major, resolved_cohort)
   → per-collection CollectionFilter via registered extractor (or empty).
   → freshness intent + collection in {"kehoach", "quydinh"} + empty filter
     + not already sort_by_date_desc ⇒ sort_by_date_desc=True.
2. MultiCollectionSearch._resolve_filter_with_fallback() tries each ES query in order;
   first returning ≥1 doc ID (after resolve_chunk_ids_for_qdrant) wins.
3. Winning IDs → Qdrant HasIdCondition + ES filter clause.
4. All zero → no filter, UNLESS ES index is empty → translate a simple exact term/terms
   clause into a Qdrant payload filter (fields: major_code, applicable_cohort,
   applicable_major, date_str, course_code).
```

**Note**: `_DATE_STR_FRESHNESS_COLLECTIONS = {"kehoach", "quydinh"}` — both collections receive `sort_by_date_desc=True` on freshness intent when their filter is otherwise empty.

### Per-Collection Filter Logic

- **`ctdt` — `CtdtFilterExtractor`** (key `major_code`): chain = exact `major_code` (`_term_any_mapping`) → fuzzy `major_name` match (`_match_only`, no null fallback) → `major_code` exact OR missing (generic chunks, `_null_or_term`). Empty filter when no major signal.
- **`quydinh` — `QuyDinhFilterExtractor`** (key `applicable_cohort`): chain = `applicable_cohort` term(s) OR missing (`_null_or_terms`). Cohort priority: query text → `resolved_cohort` → `resolved_major`. Empty when no cohort signal.
- **`kehoach` — `KeHoachFilterExtractor`** (key `date_str`): explicit month/year → `date_str` wildcard (`*/M/YYYY` or `*/YYYY`); academic terms (`2025.2`, `20252`, `2025-2`) and school years (`2025-2026`, `năm học 2025-2026`) stripped before parsing. Else freshness intent → `sort_by_date_desc=True`. Else empty (recency bonus still applies).
- **`stsv`** — no extractor registered.

### Freshness Intent

`has_freshness_intent()` matches accent-folded `moi nhat`, `gan day`, `hien tai`, `ky/ki nay`, `hoc ky/ki moi`, `hoc ky/ki toi`, `thong bao moi`, `latest`, `recent`, `newest`, `current semester`.

### `kehoach` Recency Bonus

```python
KEHOACH_RECENCY_BONUS_MAX = 0.05
KEHOACH_RECENCY_DECAY_DAYS = 365
ratio = max(0, 1 - age_days / 365); bonus = ratio × 0.05
```

Only `kehoach` docs with a parseable `date_str` get it; added in both `linear` and `rrf` fusion (in `rrf` mode the bonus is rescaled by `1/(rrf_k+1)` before adding).

### Major Code Handling

- `MAJOR_CODE_TO_NAME`: ~70 HUST programme codes → canonical names.
- `MAJOR_PATTERNS`: ordered `(regex, code)` tuples.
- `MAJOR_NAME_ALIAS_MAPPING`: canonical name → accepted aliases/codes.
- `_normalise_major_text()` handles Unicode dashes and compact forms (`IT E10`, `IT–E10`, `ITE10` → `IT-E10`).
- `_resolve_major_code()` priority: `resolved_major` (code → canonical-name alias → name→code → pattern) then query regex.
- Public helpers: `extract_major_codes`, `extract_cohort_codes`, `canonicalize_major_name`, `enrich_major_references_for_query` (adds code/name pairs while leaving already bracketed references like `[IT-E6]` unchanged), `expand_major_in_query_for_reranking` (replaces codes with full names to help the cross-encoder).

### Comparison & Query-Shaping Helpers

- `build_cohort_comparison_subqueries_for_retrieval()` and `build_major_comparison_subqueries_for_retrieval()` split compare queries into per-cohort / per-(query,code) subqueries (require ≥2 entities + compare hint).
- `strip_cohort_comparison_scaffold_for_retrieval()` / `strip_major_comparison_scaffold_for_retrieval()` remove compare scaffolding.
- `strip_major_from_query_for_retrieval()` removes major mentions once metadata filtering covers them; returns original if stripped query < 2 words or only generic words remain.
- `expand_major_in_query_for_reranking()` replaces codes with full names for the cross-encoder.

### Adding a New Collection Filter

1. Subclass `BaseFilterExtractor` and implement `extract(query, resolved_major, resolved_cohort) → CollectionFilter`.
2. Register the instance in `_COLLECTION_FILTER_REGISTRY`. No other files need to change.

---

## Collection Selection

`CollectionSelector.select()` maps routed domains (single `domain`, list `domain`, or `domains`) + confidence + optional query/signals to collection names.

### Mapping & Constants

```python
DOMAIN_TO_COLLECTIONS = {
    "ctdt":    ["ctdt"],
    "quydinh": ["quydinh", "stsv"],
    "kehoach": ["kehoach"],
    "stsv":    ["stsv", "quydinh"],
}
ALL_COLLECTIONS       = ["stsv", "quydinh", "kehoach", "ctdt"]
MULTI_DOMAIN_FALLBACK = ["quydinh", "stsv", "ctdt"]
CONFIDENCE_THRESHOLD  = 0.55
KEHOACH_CLOSE_PROBABILITY_MARGIN = 0.10
```

### Selection Logic

- No active domains → all collections.
- Active domains, confidence ≥ 0.55 → union of mapped collections (order preserved, deduped).
- Active domains, confidence < 0.55 → mapped collections first, then broadened with `MULTI_DOMAIN_FALLBACK`.
- Low-confidence `kehoach` widening is special-cased: if `kehoach` is not already active, it is inserted when either its probability is within `0.10` of the top domain, or the query has freshness/schedule/deadline/announcement intent and no strong non-`kehoach` top domain (`top_score >= 0.55` and margin over `kehoach` > `0.10`).
- Unknown domain labels are skipped with a warning; all-unknown → all collections.

### Query-Signal Augmentation

Every return path passes through `augment_collections_for_query(query, collections, query_signals)`:

- Foreign-language/cohort policy lookups (`_is_foreign_language_policy_lookup`: FL-code or `K65–K70` cohort + FL hints) → prepend `quydinh`.
- `eligibility_check` / `table_lookup` / `exact_policy_lookup` signals → prepend `quydinh`. (The former `_is_ctdt_course_lookup` guard that suppressed this for course/credit lookups was removed in Phase 3, 2026-06-21 — the v2 classifier disambiguates ctdt vs quydinh, and ablation showed the guard was net-harmful.)
- `procedural_support` → append `stsv`.
- `multi_domain` + `eligibility_check` → append `ctdt`.
- `curriculum_semester_intent` without schedule/deadline/announcement/freshness signals → prepend `ctdt` (course semester placement lives in the standard study plan, not `kehoach`).
- Freshness/schedule/deadline/announcement intent → append `kehoach`, unless suppressed by the curriculum-semester rule above.

### Pipeline-Side Route Guards

After `CollectionSelector.select()`, `pipeline/flows.py` applies additional deterministic route guards:

- `_should_lock_kehoach_route(...)` can force `target_collections = ["kehoach"]` for clear freshness/schedule/deadline/announcement queries. It returns true when selected domains are only `kehoach`, or when the highest probability domain is `kehoach` and either `kehoach_score - runner_up >= 0.20` or `kehoach_score >= 0.65`.
- The `kehoach` lock is suppressed for some non-`kehoach` policy-lock terms (`chuong trinh thu hai`, `de tai luan van`, `hoc ky chinh`, `quy che`, `quy dinh`, `dieu kien`, `ctdt`) unless the query has explicit freshness/deadline/announcement intent.
- `_should_strip_major_for_retrieval(...)` strips a resolved major from the retrieval query when metadata filters can cover it. It does **not** strip the major if `quydinh` is in `target_collections`, because `quydinh` relies on lexical/semantic major cues rather than `major_code` filtering.

### Hardcoded Routing And Fallback Rules

The current hardcoded routing surface is:

- Domain labels are fixed to `ctdt`, `quydinh`, `kehoach`, `stsv`.
- Domain-to-collection overlap is hardcoded: `quydinh` also searches `stsv`; `stsv` also searches `quydinh`.
- Low-confidence fallback is hardcoded to `["quydinh", "stsv", "ctdt"]`; `kehoach` is intentionally excluded unless timing/freshness signals or close probabilities justify it.
- Collection selector confidence is hardcoded at `0.55` in production because `flows.py` constructs `CollectionSelector()` without passing `Settings.domain_confidence_threshold`.
- Tier-3 LLM domain fallback thresholds are hardcoded in `pipeline/rag_pipeline.py`: confidence `< 0.55` and dominant-domain margin `< 0.25`.
- Query signals are regex-driven in `query/signals.py`; they are deterministic and shared by complexity routing, collection selection, and search-time fusion.
- Metadata routing is hardcoded per collection: `ctdt` uses major code/name, `quydinh` uses applicable cohort, `kehoach` uses `date_str`/freshness, `stsv` has no extractor.
- `MultiCollectionSearch` hardcodes exact-policy/table lookup widening (`keyword_top_k >= 120`, `keyword_pool_k >= 80`) and keyword-heavy weights (`vector <= 0.1`, `keyword >= 0.75`).
- Course-like queries hardcode a milder keyword bias (`vector <= 0.4`, `keyword >= 0.6`).
- Procedural-support queries hardcode at least one `stsv` evidence doc in the final fused list when possible.
- Parent chunks are always excluded from vector and keyword retrieval via `level != parent`.
- Local retrieval fallback in `rag_flow` retries with the `quydinh` metadata filter disabled, then all collections, when routed collections return no candidates.
- Tavily is not a collection router. It is triggered after retrieval/rerank by pre/post-generation gates such as no sources, freshness/dynamic risk, raw rerank fallback (`low_retrieval_confidence`), no-info answer patterns, or self-eval web requests, and only when `tavily_fallback_enabled=True`.

### Tavily Web Fallback Boundary

Tavily is wired through `RetrievalService.tavily_tool` but called from `pipeline/flows.py`, not from `RetrievalService.search()` or `CollectionSelector`.

- `_build_pre_generation_web_decision(...)` can request web context for `no_sources`, freshness/dynamic risk without acceptable local evidence, or `low_retrieval_confidence` (set when rerank falls back to raw candidates).
- `_build_answer_quality_gate(...)` can request web context after answer generation for no-info answers, no sources, or a structured self-eval request with `answer_status` in `insufficient`/`stale_risk`.
- `_build_web_search_query(question, search_query)` is deterministic: it starts from the reflected search query when available, adds `HUST` context if missing, and appends academic-year / registration / notice terms for freshness and planning queries.
- `_tavily_search_context(...)` restricts normal search to `HUST_OFFICIAL_DOMAINS`: `hust.edu.vn`, `sis.hust.edu.vn`, `ctt.hust.edu.vn`, `ctsv.hust.edu.vn`, `sv-ctt.hust.edu.vn`, `soict.hust.edu.vn`.
- Runtime defaults: `tavily_fallback_enabled=False`, `tavily_max_results=5`, `tavily_web_result_count=3`, `tavily_web_content_char_limit=1500`, `tavily_search_depth="basic"`, `web_fallback_dynamic_collections=["kehoach"]`.
- `TavilySearchTool.search()` filters results, ranks them for the query, keeps only `result_count`, truncates each result's `content` to `content_char_limit`, formats a compact context string, and caches by query/domain/depth/result limits.

---

## Validity Filter

`ValidityFilter` loads `data/document_lineage.json` (path: `Path(__file__).resolve().parent.parent / "data" / "document_lineage.json"`) and builds `_superseded_ids` (status `superseded`) and `_superseded_patterns` (lowercased filename stems). `filter(results, min_results=2)` drops chunks whose `source`/`title` matches a superseded pattern (substring), but returns the original list if filtering would leave fewer than `min_results`. `reload()` hot-reloads. Invoked by `RAGPipeline`, not by `RetrievalService.search()`.

---

## Reference Resolver

`ReferenceResolver(retrieval_service, ...)` detects Vietnamese legal cross-references in retrieved chunks and inserts matching same-document chunks after the referencing chunk.

- **Detection**: two regexes — clause-first (`khoản 1 [và khoản 2] Điều 5`) and article-first (`Điều 5 [khoản 1 [và khoản 2]]`), both with optional prefixes (`theo`, `xem`, `tại`, `căn cứ`, `quy định tại`, `nêu tại`). References to the same article are merged.
- **Resolution per reference**:
  1. Metadata lookup — scroll Qdrant by `document_id` (page_size 128, max_points 500), keep chunks whose `section_h3`/text matches the `Điều {article}` heading; sort prefers non-parent, clause-containing, lower `chunk_index`.
  2. Semantic fallback — `RetrievalService.search()` with `rerank=True` on the source collection, filtered to the same document and article heading.
- **Limits**: `max_refs_per_chunk=2`, `max_total_refs=3`, `scroll_page_size=128`, `scroll_max_points=500`.
- **Dedup**: by `{collection}/{id}` keys, raw `id`, and first-200-char text. Resolved chunks marked `_cross_reference=True`, `_referenced_from`, `_reference`.
- **Note**: `_qdrant_store(collection)` resolves via `service.searcher.qdrant_stores` (property dict, not a method call).

---

## Query Expansion & HyDE

- `MultiQueryExpander(max_variants=3, clamped 2–4).expand(query, entities)` → up to 3 variants: original, entity-focused (entity values + topic words), topic-only (entities stripped). Entity keys: `major_code`, `cohort`, `course_code`, `academic_year`, `semester`.
- `HyDEExpander(llm, embedder, prompt_template=None, max_hypothesis_len=800)`: `generate_hypothesis()` (Vietnamese HUST prompt, falls back to raw query on empty/error) and `generate_embedding()`. `should_use_hyde(results, reranker_stats, min_results=3, confidence_threshold=0.3)` triggers when too few results or low reranker mean score (`reranker_stats["rerank_score_mean"]`).
- **config.py constants** (`HYDE_ENABLED=False`, `HYDE_MIN_RESULTS=3`, `HYDE_CONFIDENCE_THRESHOLD=0.3`) are legacy constants for older direct imports; production settings live in `config/settings.py` (`hyde_enabled=True` in settings, overriding `config.py`'s `False`).

---

## Parent Context

`ParentContextExpander(qdrant_host, qdrant_port, max_parent_chars=3000)` (the service passes `settings.parent_max_chars`, default 1500). `expand_with_parents(results, collection, include_parent_content=True)` collects `parent_id` for results with `level=="child"`, fetches parents from Qdrant, and attaches `parent_context` (truncated at a sentence/paragraph boundary when over limit, with `[… nội dung còn tiếp …]` marker), `parent_title` (parent `hierarchy_path`), and `parent_section_h2` to each child's metadata. Qdrant client is lazily created.

---

## Structured Query Processing

`MultiCollectionSearch` uses `parse_structured_query()` (from `query.structured_query`) to extract exclusion terms (e.g. `"quy định -tín chỉ"`):

- Qdrant/ES results are post-filtered (`text_contains_excluded_term` over text + title + course_code + course_name).
- ES applies `build_es_must_not_clauses()` in `keyword_search`.

---

## ID Conventions

- **Within a collection**: raw Qdrant point ID = ES `_id`.
- **Across collections** (runtime): `"{collection}/{point_id}"`.
- `resolve_chunk_ids_for_qdrant()` guards against ID mismatches between metadata filtering and vector search.

---

## Maintenance Notes

- Preserve `{collection}/{id}` runtime IDs when merging across collections.
- Parent chunks (`level=="parent"`) are excluded from both vector and keyword search; keep the `must_not level=parent` clauses when editing `keyword_search` / `_fetch_one`.
- Keep ES field names aligned with `data/MODULE.md`, `chunking`, and indexing scripts; `search_text` is generated unless supplied.
- The CocCoc `vi_tokenizer` path is the production analyzer; the standard-tokenizer fallback (and Python `segment_query`) only run when the plugin is missing.
- If a Qdrant collection is populated but its ES index is empty, `_resolve_filter_with_fallback()` still applies exact Qdrant payload filters; do not remove this without fixing the indexing sync.
- `_search_cache` caches **pre-rerank** results for 180s; clear/disable it when debugging fusion or filter changes.
- `date_str` is a keyword `"D/M/YYYY"` (not a native date field) — sorting requires Python-side parsing.
- Fusion uses **max-normalisation** (divide by pool max), not min-max. The lowest-scoring doc in a pool retains a non-zero contribution. Do not confuse with true min-max in comments or docs.
- The `kehoach` recency bonus in RRF mode is multiplied by `1/(rrf_k+1)` before addition; in linear mode it is added raw. Keep these consistent when changing fusion modes.
- When changing fusion/scoring, re-run the search/eval benchmarks.

---

## Useful Checks

```bash
python -m py_compile retrieval/*.py
python -m pytest tests/retrieval -q -m "not integration"

```
