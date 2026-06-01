# Module: `evaluation`

Source-verified: 2026-06-01 from `evaluation/*.py`, `eval/`, `api/routes/metrics.py`, and GitNexus query results.

## Purpose

`evaluation` is the offline quality and regression layer for RAG v2. It separates production-current policy checks from historical conversation/advisory checks.

The important design rule is:

```text
Historical email eval measures conversation/advisory behavior.
Current policy eval measures production factual retrieval against currently indexed documents.
```

Historical results must not be used as a production factual pass/fail gate when policy may have changed.

## File Map

```text
evaluation/
  eval_schemas.py                    Shared dataclasses, loaders, judge parsing, freshness helpers.
  eval_store.py                      Mongo/artifact persistence and dashboard payloads.
  two_layer_eval.py                  Main CLI runner for current and historical suites.
  evaluate_current_pipeline.py       Retrieval eval on real production stack.
  evaluate_e2e_pipeline.py           Full query_v3 RAG eval with generation, judge, and tuning knobs.
  build_current_policy_ground_truth.py Draft inventory/cases/labels/audit exports.
  post_index.py                      Fail-soft post-index eval trigger.
  search_strategy_benchmark.py       BM25/BGE/E5/hybrid/rerank benchmark.
  evaluate_retrieval.py              Older isolated retrieval eval.
  evaluate_llm_quality.py            Older answer-quality eval.
  evaluate_phase3.py                 Older phase eval.
  evaluate_hf_dataset.py             HuggingFace dataset eval utility.
  evaluate_sft_backend.py            Live /chat/v3 SFT runner with resumable JSONL artifacts.
  rerun_incorrect_sft_backend.py     Rerun SFT backend records previously judged incorrect.
  results/                           JSON/CSV run artifacts.
  ground_truth_drafts/               Draft current-policy cases and seed labels.
```

Related but outside this module:

```text
eval/golden_dataset.json             Default current-policy golden dataset.
eval/RAG/ragass_evaluator.py         RAGAS-style dataset/full-RAG evaluator.
api/routes/metrics.py                /metrics/eval dashboard API.
frontend/chat-companion/src/pages/EvalPage.tsx
```

## Main CLI

Run from `src/RAG_v2`:

```bash
python -m evaluation.two_layer_eval current --persist
python -m evaluation.two_layer_eval current --labels evaluation/search_strategy_labels.jsonl --persist
python -m evaluation.two_layer_eval current --max-cases 120 --persist --trigger post_index
python -m evaluation.two_layer_eval historical --max-cases 50 --judge --persist
```

Default inputs:

- Current policy: `eval/golden_dataset.json`
- Historical email: `../clean_data/test_dataset.json`
- Relevance labels: `evaluation/search_strategy_labels.jsonl`
- Lineage/freshness: `data/document_lineage.json`
- Artifacts: `evaluation/results/`

## Current Policy Eval

Goal: ensure current production retrieval returns the right collection, sources, ranking, and fresh/non-superseded documents.

Production stack evaluated:

```text
Settings
  -> RetrievalService.from_settings()
  -> QueryRouter
  -> CollectionSelector
  -> MultiCollectionSearch
  -> configured reranker
```

Metrics:

- `collection_accuracy`
- `keyword_hit_rate`
- `recall_at_50`
- `ndcg_at_10`
- `mrr_at_10`
- `context_precision`
- `context_recall`
- `citation_accuracy`
- `freshness_pass_rate`
- latency percentiles

Current eval reads baseline from `evaluation/search_strategy_results.json` and can downgrade run status to `warning` when current metrics fall below baseline.

## E2E Pipeline Eval

`evaluate_e2e_pipeline.py` evaluates `RAGPipeline.query_v3()` and writes
`query_results.csv`, `summary.json`, and `report.md`. The report includes a
`Run Config` section so tuning runs are attributable.

Useful tuning flags:

```bash
python -m evaluation.evaluate_e2e_pipeline --dataset evaluation/data/ITE6_rag_evaluation_dataset_no_parent_evidence.json --top-k 7 --reranker-min-top-k 7
python -m evaluation.evaluate_e2e_pipeline --dataset ... --vector-pool-k 28 --keyword-pool-k 28 --vector-top-k 28 --keyword-top-k 28
python -m evaluation.evaluate_e2e_pipeline --dataset ... --hyde-enabled --low-conf-pool-expand
python -m evaluation.evaluate_e2e_pipeline --dataset ... --enable-agent
python -m evaluation.evaluate_e2e_pipeline --dataset ... --disable-decomposer --disable-reflection --disable-complexity-router
```

For chunk-id datasets, the runner disables ValidityFilter, agent, and
Tavily/web fallback by default so retrieved sources remain comparable to
`evidence_chunk_ids`. Use `--enable-agent` only for intentional Planner-Executor
evaluation; the chunk-id eval defaults are not production routing defaults. The
run config and active ablations in reports reflect the actual toggles. The ITE6
no-parent-evidence comparison indicates
`top_k=7` with `reranker_min_top_k=7` is the best historical report among the
tracked variants; HyDE did not trigger in those runs. A 2026-06-01 retest after
the Qdrant payload-filter fallback for empty `ctdt` ES index produced
`hit@5=53.85%`, `ref_correct=73.08%`, and avg latency about 61.6s. This is
better than the pre-fix current run but still below the older `min_top_k_7`
artifact, so investigate index sync and reranker latency before promoting wider
candidate pools.

## Historical Email Eval

Goal: measure conversation understanding, follow-up resolution, personalization, clarification quality, advisory logic, and tone.

Pipeline:

1. Load historical email cases.
2. Convert email context to chat history.
3. Call `RAGPipeline.query_v3()`.
4. Optionally judge with Gemini.
5. Persist artifacts/Mongo run.

Do not treat factual mismatch with old email ground truth as production failure if current policy changed.

## SFT Backend Eval

No-cache eval contract:

- SFT backend eval defaults to `require_no_cache=True`.
- Each record captures `cache_hit_markers`; if `cache_hit`, `query_cache_hit`, or `llm_cache_hit` appears while no-cache is required, the record is marked `setup_invalid`.
- Run summaries include `setup_valid`, `setup_invalid_count`, and `setup_invalid_reasons`; accuracy should not be interpreted from a setup-invalid run.
- `rerun_incorrect_sft_backend.py` resets `resume_from_index` to 0 so small incorrect subsets are not filtered out by the full SFT resume default.

`evaluate_sft_backend.py` and `rerun_incorrect_sft_backend.py` default to
`identity_mode: "anonymous"` so live backend runs mirror a new anonymous
frontend session: no auth header, no client-supplied `session_id`, no
`user_context`, no `user_id`, empty history, `mode: "auto"`, and `top_k: 5`.
Use `identity_mode: "frontend_env"` only when a run intentionally needs the
older env-driven identity behavior from `EVAL_SESSION_ID`,
`EVAL_USER_CONTEXT_JSON`, `EVAL_USER_ID`, or `EVAL_AUTH_TOKEN`. The rerun CLI
also exposes this as `--identity-mode`.

Each SFT backend record stores request identity diagnostics including
`identity_mode`, whether an auth header was sent, optional request fields sent,
the backend URL, `response_session_id`, and a stable request payload hash. The
saved `response_trace` includes rerank, answer-quality, context, fusion, and
tool fields to help distinguish evaluator identity issues from pipeline
retrieval/rerank/fallback issues.

## Ground Truth Builder

`build_current_policy_ground_truth.py` supports:

```bash
python -m evaluation.build_current_policy_ground_truth inventory
python -m evaluation.build_current_policy_ground_truth generate-cases --target-cases 200
python -m evaluation.build_current_policy_ground_truth seed-labels --cases evaluation/ground_truth_drafts/current_policy_cases_draft.json
python -m evaluation.build_current_policy_ground_truth validate --cases ... --labels ...
python -m evaluation.build_current_policy_ground_truth audit-export --cases eval/golden_dataset.json --labels evaluation/search_strategy_labels.jsonl
```

It writes drafts under `evaluation/ground_truth_drafts/` and should not overwrite `eval/golden_dataset.json` without review.

## Dashboard Contract

`GET /metrics/eval?suite=current_policy&limit=10` and `GET /metrics/eval?suite=historical_email&limit=10` return Mongo-backed eval runs when `mongo_logger` is available. If Mongo is unavailable, the route can fall back to JSON artifacts.

Frontend route: `/eval`.

## Maintenance Notes

- After indexing/crawling/chunking/retrieval changes, run current policy eval.
- After prompt/model/agent/history/personalization changes, run historical eval and current eval with judge if answer quality is affected.
- Prefer `expected_source_ids` over keyword-only assertions for production gates.
- Keep run artifacts reproducible: dataset path, labels path, max cases, trigger, settings summary, run id.
- `post_index.py` is fail-soft: eval errors should not fail indexing in the current design.

## Useful Checks

```bash
python -m py_compile evaluation/*.py
python -m pytest tests/test_two_layer_eval.py tests/test_week4_evaluate.py -q -m "not integration"
```
