# Module: `retrieval`

Source-verified: 2026-05-20 from `retrieval/*.py`, `pipeline/flows.py`, `agent/tool_adapters.py`, and GitNexus context for `RetrievalService`.

## Purpose

`retrieval` owns the document search stack: Qdrant vector search, Elasticsearch keyword search, metadata prefilters, multi-collection fusion, reranking integration, validity filtering, reference resolution, and the shared `RetrievalService` used by pipeline and agent tools.

## File Map

```text
retrieval/
  __init__.py                  Public exports and create_retriever().
  base.py                      BaseRetriever interface.
  service.py                   RetrievalService shared runtime wrapper.
  qdrant_store.py              QdrantStore with named BGE/E5 vectors.
  elasticsearch_store.py       ElasticsearchStore keyword and metadata search.
  hybrid_search.py             Per-collection vector/keyword RRF fusion.
  multi_collection_search.py   Parallel global multi-collection search and fusion.
  metadata_filters.py          Major/cohort/date filter extraction and helpers.
  collection_selector.py       Domain -> collection selection.
  validity_filter.py           Drop superseded documents using data/document_lineage.json.
  reference_resolver.py        Resolve legal references such as Dieu/Khoan.
  search_stsv.py               STSV search utility.
  index_stsv_to_es.py          ES indexing utility.
```

## RetrievalService

`RetrievalService.from_settings(settings)` builds:

- `BGEm3Embedder`
- `E5MultilingualEmbedder`
- `MultiCollectionSearch`
- optional reranker
- optional Tavily tool
- `search_kwargs` from retrieval settings

Methods:

- `embed_query(query) -> (bge_vec, e5_vec)`
- `search(query, collections, top_k, resolved_major, resolved_cohort, rerank=True)`
- `web_search(query, max_results=3)`

This service is created once by `RAGPipeline` and injected into agent tools.

## Store Contracts

Qdrant:

- One collection per domain.
- Named vectors:
  - `bge_m3`, 1024 dimensions, cosine
  - `e5`, 1024 dimensions, cosine
- Payload includes metadata plus `text`.

Elasticsearch:

- Index name matches collection name.
- Keyword search over text/title-style fields.
- Metadata-only search used for prefilter ID resolution.
- `resolve_chunk_ids_for_qdrant()` maps ES ids to Qdrant ids for `HasIdCondition`.

## MultiCollectionSearch

High-level flow:

```text
query + BGE/E5 vectors + active_collections
  -> build_collection_filters()
  -> metadata ES fallback chain
  -> parallel per-collection Qdrant + ES search
  -> global vector pool
  -> global keyword pool
  -> min-max normalize
  -> weighted score fusion
  -> kehoach recency bonus when applicable
  -> text/id dedup
  -> top-k candidates
```

Trace fields populated when `trace_out` is supplied:

- filters
- collection counts/results
- fusion weights

Fusion defaults from settings:

- `vector_weight=0.8`
- `keyword_weight=0.2`

Course-like queries can shift toward keyword weight, because course codes/names need exact matching.

## Metadata Filters

`metadata_filters.py` contains:

- major code/name normalization
- cohort extraction/normalization
- academic term/date handling
- comparison scaffold stripping
- per-collection filter extractors

Collection filter behavior:

| Collection | Filter behavior |
| --- | --- |
| `ctdt` | major code exact, major name fallback, generic/null fallback. |
| `quydinh` | cohort/major applicability with null fallback. |
| `kehoach` | posting-date wildcard when real dates exist; freshness sort when no real date. |
| `stsv` | no metadata prefilter by default. |

Important current behavior:

- Academic terms like `2025.2`, `20252`, `2025-2` are not posting dates for `date_str`.
- Freshness intent without a real posting date should sort `kehoach` by latest `date_str`.
- Major-code normalization accepts dash, Unicode dash, spaced, and compact variants.

## Collection Selection

`CollectionSelector` maps routed domains to collection names and handles low-confidence fallback. If the route is locked to `kehoach` for freshness/dynamic plan queries, broad fallback should not pull unrelated regulation/curriculum results ahead of current notices.

## Validity And References

`ValidityFilter` reads `data/document_lineage.json` and removes superseded docs where safe. If too few results remain, it keeps original results to avoid empty contexts.

`ReferenceResolver` detects legal references such as `Dieu 5`, `Khoan 1 Dieu 5`, and inserts matching same-document chunks near the source chunk. It prefers Qdrant payload lookup by document id and falls back to semantic/reference search with same-document constraints.

## Maintenance Notes

- Preserve `{collection}/{id}` style runtime ids when merging across collections.
- Keep metadata field names aligned with `data/MODULE.md` and indexing scripts.
- When adding a collection, update settings, collection selector, metadata filters, agent aliases, scripts, eval data, and docs.
- When changing fusion/scoring, run current policy eval and search strategy benchmark.

## Useful Checks

```bash
python -m py_compile retrieval/*.py
python -m pytest tests/test_multi_collection_fusion.py tests/test_reference_resolver.py retrieval/test_metadata_filters.py retrieval/test_hybrid_search.py -q -m "not integration"
```
