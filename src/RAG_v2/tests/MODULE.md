# Module: `tests`

Source-verified: 2026-06-24 from `tests/*.py`, `tests/retrieval/*.py`, `tests/conversation_regression_queries.jsonl`, root `pytest.ini`, and root `conftest.py`.

## Purpose

`tests` contains regression, unit, contract, and integration-style tests for the backend RAG system: query routing/signals, retrieval and fusion, parent-child context, Redis/cache, auth/RBAC, mobile/admin API contracts, the document upload pipeline, the agent (Planner-Executor) graph, evaluation tooling, and hardening fixes (audit, P0, reflection, profile-dependency).

Test discovery is configured in `pytest.ini` (`testpaths = tests`, `asyncio_mode = auto`). The root `conftest.py` inserts the RAG_v2 project root onto `sys.path` so top-level packages (`agent`, `api`, `query`, `retrieval`, …) import without a full install. There is no `conftest.py` inside `tests/` or `tests/retrieval/` itself.

## File Map

```text
tests/
  prompt_tune_questions.py          Question set (Vietnamese query, expected tool, expected collection) for prompt tuning.
  run_prompt_tune.py                Script: runs TUNE_QUESTIONS through a live ReActAgent / LM Studio and prints tool accuracy.

  test_adapters.py                  agent.tool_adapters: execute_tool router errors, result/web formatting, parent dedup; RAG/web search are @integration.
  test_admin_llm_config.py          Persisted admin LLM config: filter/merge, upsert doc, startup DB merge, legacy key import, API-key registry, hot reload + chat-cache invalidation.
  test_agent_langgraph.py           Planner-Executor ReActAgent compat class: plan/decompose payloads, synthesis, APIConnectionError handling (ChatOpenAI mocked).
  test_all_fixes.py                 P0–P3 fixes: _should_trigger_tier3, query normalization, reflection hallucination guard, query-only cache, ke_hoach latest/freshness regressions, profile-note prepend, latest-chunk-by-date.
  test_audit_fixes.py               Audit-fix pass: agent context-window cap (_to_agent_state/_CONTEXT_WINDOW_TOOL_LIMIT), canonicalize_major_name after dedup alias removal, LocalStorage path-traversal guard, admin-only route RBAC (require_admin). No external services.
  test_auth_refresh.py              Refresh-token rotation, reuse-detection family revoke, logout revoke, expiry rejection, naive-UTC handling (httpx ASGI app, fake Mongo collection).
  test_chat_route_mode.py           /chat route modes (auto/rag/agent) selecting query_v3 vs classic RAG vs agent runner, plus turn logging (fake pipeline/agent/Mongo).
  test_chunk_indexing_policy.py     utils.chunk_indexing.is_indexable_chunk: skips parent/header, allows child/recursive/appendix/legacy.
  test_constants.py                 schemas.constants: CLARIFY_SENTINEL value, RouteMode/PipelineMode/AgentRoute enums.
  test_course_catalog.py            query.course_catalog: major-scoped course-name lookup and safe shorthand alias (ambiguous alias rejection).
  test_crawler_html_cleaning.py     Crawler HTML→text: GenericCrawler._parse_detail keeps inline tags inline (no spurious newlines around bold/strong).
  test_crawler_review.py            Auto-crawler Mongo staging without indexing, pending-review previews, edit marking, reviewed indexing success/failure retry (sync+async fake Mongo).
  test_decomposer.py                query.decomposer: _DECOMPOSE_FEW_SHOT coverage for broad graduation-condition decomposition (foreign-language + general-rules sub-queries).
  test_dependencies.py              api.dependencies.resolve_session (new/unknown/existing session) and parse_history helper.
  test_document_pipeline.py         DocumentPipeline steps (convert/clean/chunk/embed+index), chunker factory, delete cleanup, full pipeline, upload integration. Requires MongoDB; uses requires_mongo skip mark.
  test_domain_routing_evaluator.py  evaluation.evaluate_domain_routing: RoutingEvalCase/evaluate_cases stage metrics (raw_classifier, selector, final_pipeline) with fake router and CollectionSelector.
  test_e2e.py                       Full routing + answer-quality flow over RAGPipeline. @pytest.mark.e2e (needs Qdrant/ES/LM Studio).
  test_mobile_api_contracts.py      Mobile/shared API contracts: chat_v3 profile override, session ownership aliases, bookmark folders, notification subscribe/broadcast, Redis session sync.
  test_mongo.py                     MongoLogger CRUD: new_session, log_turn (rag/chitchat), get_history, turn count, list sessions. Skips when MongoDB unavailable; @integration.
  test_multi_collection_fusion.py   MultiCollectionSearch RRF score fusion and excluded-result text/metadata filtering.
  test_p0_fixes.py                  P0 hardening: /retrieval/search reuses pipeline's shared RetrievalService (no per-request reload), upload index/delete invalidates agent RAG + Redis LLM cache, rate-limit middleware (429, JWT/IP identity), /api/admin/reload-validity requires admin, query_stream per-request state isolation, SSE stream contract. No external services.
  test_parent_context_phase1.py     Phase 1: is_indexable_chunk / is_qdrant_storable policy split, parent_id remapping, ES parent skip logic.
  test_parent_context_phase2.py     Phase 2: re-implemented _format_context / parent-expand / _format_search_results logic (no heavy imports).
  test_parent_context_phase3.py     Phase 3: ParentContextExpander with mock Qdrant, service multi-query expansion, end-to-end format, settings/get_parent_for_child.
  test_phase1_improvements.py       Phase 1 retrieval: HyDE prompt (Quy Nhon) fix, BGE/E5 embedding LRU cache, search-result TTL cache, ES synonym/BM25 settings, synonym coverage. Heavy deps mocked via _mock_heavy_deps().
  test_phase1_redis.py              Redis session store + sliding-window rate limiter + RedisManager + resolve_session using fakeredis. Module skips if fakeredis missing.
  test_phase2_improvements.py       Phase 2 retrieval: Vietnamese segmenter, ES keyword segmentation, fusion-weight sweep metrics, Redis config defaults, metadata audit.
  test_phase2_redis.py              Phase 2 cache: LLM cache hit/miss/FAQ promotion/invalidation, history cache ops/ltrim/warming, rag_flow cache via fakeredis. Skips if fakeredis missing.
  test_phase3_improvements.py       Phase 3: index-script discovery, chunk prep, ParentContextExpander, service expansion, parent filtering, config, dry-run, parent dedup.
  test_phase5.py                    Smoke checks: Settings import, API schemas, flows import, FastAPI app creation, pipeline syntax.
  test_phase7.py                    Phase 7 fixes: query reflection, self-evaluation activation, Tavily fallback, payload.pop fix, config sync (mocked pipeline).
  test_phase8.py                    Phase 8 collection-aware routing: CollectionSelector, MultiCollectionSearch active_collections filter, rag_flow routing integration, Settings fields.
  test_profile_dependency.py        query.profile_dependency: topic-driven major/cohort dependency (DEPENDENCY vs SOURCE), effective_major_for_retrieval, should_inject_profile_note, resolve_sources — covers "điều kiện ngoại ngữ của tôi" bug case table.
  test_query_signals.py             query.signals.analyze_query_signals / extract_key_phrases: personal/eligibility/policy-lookup/table_lookup detection, accent insensitivity.
  test_rag_dataset_eval.py          evaluation.evaluate_rag_datasets: dataset adapter, validation/dup detection, ranking metrics, source-id extraction, retrieval/answer metrics, summary aggregation.
  test_rbac.py                      Role system & RBAC: JWT role claim, dependency guards, login role, admin/superadmin create, require-admin endpoint, backward compat. Requires MongoDB; @integration/@asyncio.
  test_reference_resolver.py        retrieval.reference_resolver: extract_references merge, metadata lookup ordering, dedup of runtime/raw IDs, cross-document fallback filtering.
  test_reflection_course_lookup.py  query.reflection.QueryReflector: course alias injection, wrong-code correction, explicit-code preservation, profile-only LLM skip (LLM client mocked).
  test_reflection_profile_split.py  query.reflection._extract_entities: user_major_code immutable from auth profile; history cannot override it; explicit query major goes to target_major_code (BUG-3·R1).
  test_reranker_factory.py          reranking.create_reranker: returns None on model memory error, reraises non-memory OSError.
  test_reranker_thresholds.py       reranking.bge_reranker.BGEReranker: threshold filtering before top_k and min-top-k append of below-threshold docs.
  test_response_mapper.py           api.response_mapper.ChatResponseMapper: v3-result normalization, filter/collection-result models, chat response build, API-key validation, set_runtime.
  test_router.py                    query.complexity_router.ComplexityRouter: chitchat/simple/complex classification, real use cases, route() dict shape.
  test_sft_backend_eval.py          evaluation.evaluate_sft_backend runner: dataset load, legacy input parse, resume/merge, batch selection, anonymous vs frontend_env identity, request hashing, metrics, incorrect-record rerun CLI.
  test_storage.py                   LocalStorage backend: save_upload/save_text/read_text round-trip, unicode, overwrite, delete_all idempotency, doc isolation. @pytest.mark.asyncio.
  test_structured_query.py          query.structured_query: parse core slots, diacritic/Vietnamese negation, accent-insensitive excluded-term check, ES must_not phrase clauses.
  test_terminology.py               utils.terminology.expand_academic_abbreviations: full<->abbrev expansion, idempotency, glossary presence in RAG/self-eval prompts.
  test_training_data.py             query.training_data.get_training_data: quydinh boundary queries are present as labeled examples.
  test_two_layer_eval.py            evaluation eval_schemas/loaders: historical email + current policy cases, judge-score parsing, freshness checker, graded retrieval, ground-truth builder, dashboard.
  test_upload_api.py                Admin document API: DocumentRecord/Chunk models, schemas, LocalStorage, upload endpoints, pagination/filtering/conflicts. Requires MongoDB; uses requires_mongo skip mark.
  test_week4_evaluate.py            SKIPPED at module level (allow_module_level) — targets deprecated eval.evaluate API; needs rewrite against eval.evaluator.
  test_week4_mongo_logger.py        MongoLogger agent-trace features: log_agent_trace resilience/fields, get_agent_stats aggregation, log_turn debug fields with capped prompt preview.

  retrieval/test_elasticsearch_store.py     ElasticsearchStore index mapping (cohort keyword, vi tokenizer + fallback), index_documents search_text/chunk_id, keyword search phrase/table boost + fuzzy fallback. Has script main().
  retrieval/test_hybrid_search.py           HybridSearch RRF: rrf_score formula, fusion, weighted fusion, empty results. Has script main().
  retrieval/test_metadata_filters.py        retrieval.metadata_filters: major-name canonicalize/resolve, code extraction, query stripping, cohort dedup, quydinh applicable_cohort filter extraction.
  retrieval/test_phase2_features.py         HyDEExpander, should_use_hyde, ChunkContextualizer, RetrievalService multi-query and HyDE paths.
  retrieval/test_qdrant_store.py            QdrantStore smoke test (script main(), requires live Qdrant on :6333). Has script main().
  retrieval/test_retrieval_improvements.py  Phase 0-2: score-fusion single-item, dual-vector normalize, applicable_cohort fix, metadata reranking, multi-query, adaptive fusion, RRF, dedup, kehoach filter, exclude-term, CollectionSelector.

  conversation_regression_queries.jsonl     Saved chat/RAG regression prompts for replay (kehoach routing, reflection guardrail, freshness, profile bleed, etc.). Status field per entry: needs_runner | covered.
```

## Fixtures, Markers, and conftest

Markers declared in `pytest.ini`:

- `integration` — needs external services (Qdrant, Elasticsearch, local models, or Tavily).
- `e2e` — full end-to-end tests across routing and retrieval flows.

Patterns observed in the suite:

- `@pytest.mark.integration` is applied per-test (e.g. retrieval calls in `test_adapters.py`); `test_mongo.py`, `test_rbac.py`, `test_upload_api.py`, `test_document_pipeline.py` are Mongo-backed (skip via `_mongo_available()` + `requires_mongo = pytest.mark.skipif(...)` and/or `@integration`).
- `@pytest.mark.e2e` is class-level in `test_e2e.py`.
- Redis tests (`test_phase1_redis.py`, `test_phase2_redis.py`) use `fakeredis` and skip at module level via `pytestmark = pytest.mark.skipif(...)` when it is not installed.
- `test_week4_evaluate.py` is skipped at module level (`pytest.skip(..., allow_module_level=True)`).
- Async tests rely on `asyncio_mode = auto` (pytest.ini); some use explicit `@pytest.mark.asyncio`.
- LLM and vector DB calls are mocked via `unittest.mock.MagicMock`/`AsyncMock` or `_mock_heavy_deps()` (stubs `torch`, `FlagEmbedding`, `qdrant_client`, `elasticsearch`, `openai`, etc.).
- No `conftest.py` inside `tests/` or `tests/retrieval/`; the only conftest is the root `conftest.py` which inserts `RAG_v2/` onto `sys.path`.

## Maintenance Notes

- **New files since last doc revision (2026-06-07):** `test_audit_fixes.py`, `test_p0_fixes.py`, `test_reflection_profile_split.py`, `test_domain_routing_evaluator.py`, `e2e_test_url_exposure.py`, `test_api_key.py`, `test_clean_markdown.py`, `test_complexity_router_exam.py`, `test_complexity_tiers.py`, `test_components.py`, `test_crawler_admin_staging.py`, `test_crawler_date_update.py`, `test_crawler_robustness.py`, `test_embedding.py`, `test_es.py`, `test_evaluation_metrics.py`, `test_exam_es_store.py`, `test_exam_ingestion.py`, `test_exam_schedule_model.py`, `test_exam_schedule_parser.py`, `test_exam_schedule_service.py`, `test_exam_schedule_summary_route.py`, `test_exam_tool.py`, `test_expand.py`, `test_fix_url_exposure.py`, `test_fixes.py`, `test_flows_major_fallback.py`, `test_kehoach_table_chunking.py`, `test_normalise.py`, `test_planner_routing_exam.py`, `test_rag_pipeline.py`, `test_reflection.py`, `test_reflection_followup.py`, `test_reflection_pii_strip.py`, `test_regex.py`, `test_remote_embedder.py`, `test_remote_reranker.py`, `test_retrieval.py`, `test_retrieval_docs.py`, `test_routing_edge_cases.py`, `test_routing_fixes.py`, `test_signals_check.py`, `test_url_sanitization.py`, `test_vn_datetime.py` — ensure these are added to targeted runs as appropriate.
- Several files exercise logic re-implemented locally (`test_parent_context_phase2.py`) to avoid importing heavy dependencies (openai, torch). Treat them as logic-equivalence checks, not direct imports of `flows.py`/`tool_adapters.py`.
- `test_phase1_improvements.py` mocks a large dependency tree via `_mock_heavy_deps()` at import time; duplicate test class names in that file mean the later definitions shadow earlier ones at collection time.
- `run_prompt_tune.py` and `retrieval/test_{elasticsearch,qdrant}_store.py`, `retrieval/test_hybrid_search.py` carry `__main__` script entrypoints in addition to pytest functions.
- When fixing chat/RAG behavior, replay saved prompts in `conversation_regression_queries.jsonl`.
- For retrieval/model/service tests, be explicit about whether Qdrant/ES/Mongo/Redis/local models are required so no-service local runs stay possible.
- Keep mobile/admin contract tests (`test_mobile_api_contracts.py`, `test_admin_llm_config.py`, `test_auth_refresh.py`, `test_rbac.py`) aligned with the current route/schema and hot-reload contracts.
- `test_course_catalog.py` covers safe alias rejection (ambiguous shorthand deduplication), complementing the audit fix in `test_audit_fixes.py`.

## Useful Checks

```bash
# Fast local run — skip anything requiring external services
python -m pytest tests -q -m "not integration"

# Retrieval sub-suite only
python -m pytest tests/retrieval -q -m "not integration"

# Query-layer unit tests
python -m pytest tests/test_router.py tests/test_query_signals.py tests/test_structured_query.py -q

# API/route unit tests
python -m pytest tests/test_chat_route_mode.py tests/test_response_mapper.py tests/test_dependencies.py -q

# Auth/RBAC (skip Mongo-backed tests locally)
python -m pytest tests/test_auth_refresh.py tests/test_rbac.py tests/test_mobile_api_contracts.py -q -m "not integration"

# Hardening / recent fixes
python -m pytest tests/test_audit_fixes.py tests/test_p0_fixes.py tests/test_all_fixes.py -q

# Reflection & profile logic
python -m pytest tests/test_reflection_course_lookup.py tests/test_reflection_profile_split.py tests/test_profile_dependency.py -q

# Full E2E (requires Qdrant/ES/LM Studio)
python -m pytest tests/test_e2e.py -q -m e2e
```
