# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-03 21:45:46
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
| `hyde_enabled` | `True` |
| `decomposer_enabled` | `True` |
| `reflection_enabled` | `True` |
| `complexity_router_enabled` | `True` |
| `parent_context_enabled` | `True` |
| `agent_enabled` | `True` |
| `web_fallback_enabled` | `False` |
| `validity_filter_enabled` | `True` |

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `76.67%` | `26` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `93.33%` | Context facts coverage rate |
| **Hallucination Rate** | `13.33%` | `4` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `76.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `10.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `13.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `70.00%` |
| **precision@3** | `23.33%` |
| **recall@3** | `65.00%` |
| **mrr@3** | `62.22%` |
| **ndcg@3** | `60.81%` |
| **hit@5** | `73.33%` |
| **precision@5** | `15.33%` |
| **recall@5** | `70.00%` |
| **mrr@5** | `63.06%` |
| **ndcg@5** | `63.04%` |
| **hit@7** | `73.33%` |
| **precision@7** | `10.96%` |
| **recall@7** | `70.00%` |
| **mrr@7** | `63.06%` |
| **ndcg@7** | `63.04%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `20663.3 ms` |
| Routing Latency | `1408.4 ms` |
| Search Latency | `157.4 ms` |
| Rerank Latency | `6455.1 ms` |
| Generation Latency | `1645.7 ms` |
| Self-Evaluation Latency | `1080.4 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `75.0%` | `73.1%` | `62.5%` | `75.0%` | `34137.4 ms` |
| **simple** | 22 | `68.2%` | `68.2%` | `59.4%` | `81.8%` | `77.3%` | `15763.6 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 17 | `64.7%` | `64.7%` | `58.8%` | `82.3%` | `76.5%` | `16086.1 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `62.4%` | `100.0%` | `100.0%` | `38094.3 ms` |
| **medium** | 12 | `83.3%` | `75.0%` | `69.1%` | `66.7%` | `75.0%` | `25695.0 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `73.3%` | `70.0%` | `63.0%` | `76.7%` | `76.7%` | `20663.3 ms` |
