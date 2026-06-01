# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 20:38:41
- **Total Queries Evaluated**: `30`

## Run Config

| Key | Value |
| :--- | :--- |
| `top_k` | `7` |
| `reranker_min_top_k` | `7` |
| `reranker_score_threshold` | `-1.0` |
| `reranker_table_score_threshold` | `-1.0` |
| `raw_candidate_multiplier` | `4.0` |
| `raw_candidate_min` | `20` |
| `vector_top_k` | `20` |
| `keyword_top_k` | `20` |
| `vector_pool_k` | `15` |
| `keyword_pool_k` | `15` |
| `low_conf_pool_expand_enabled` | `False` |
| `hyde_enabled` | `False` |
| `decomposer_enabled` | `True` |
| `reflection_enabled` | `True` |
| `complexity_router_enabled` | `True` |
| `parent_context_enabled` | `True` |
| `agent_enabled` | `False` |
| `web_fallback_enabled` | `False` |
| `validity_filter_enabled` | `False` |

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `83.33%` | `29` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `90.00%` | Context facts coverage rate |
| **Hallucination Rate** | `3.33%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `96.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `3.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `0.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `100.00%` |
| **precision@3** | `36.66%` |
| **recall@3** | `92.22%` |
| **mrr@3** | `96.11%` |
| **ndcg@3** | `91.81%` |
| **hit@5** | `100.00%` |
| **precision@5** | `24.00%` |
| **recall@5** | `96.67%` |
| **mrr@5** | `96.11%` |
| **ndcg@5** | `94.08%` |
| **hit@7** | `100.00%` |
| **precision@7** | `17.15%` |
| **recall@7** | `96.67%` |
| **mrr@7** | `96.11%` |
| **ndcg@7** | `94.08%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `7417.7 ms` |
| Routing Latency | `360.4 ms` |
| Search Latency | `62.5 ms` |
| Rerank Latency | `2988.0 ms` |
| Generation Latency | `1378.4 ms` |
| Self-Evaluation Latency | `1466.7 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `87.5%` | `82.4%` | `37.5%` | `87.5%` | `8606.9 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `98.3%` | `100.0%` | `100.0%` | `6985.2 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 19 | `100.0%` | `100.0%` | `98.1%` | `100.0%` | `100.0%` | `6894.6 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `94.7%` | `0.0%` | `100.0%` | `6157.0 ms` |
| **medium** | 10 | `100.0%` | `90.0%` | `86.5%` | `60.0%` | `90.0%` | `8537.6 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 29 | `100.0%` | `96.5%` | `94.4%` | `86.2%` | `96.5%` | `7326.3 ms` |
| **rag_v2_decomposed** | 1 | `100.0%` | `100.0%` | `85.0%` | `0.0%` | `100.0%` | `10067.7 ms` |
