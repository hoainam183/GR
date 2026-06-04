# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-03 22:41:33
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
| **Faithfulness (Grounded)** | `80.00%` | `27` grounded responses |
| **Answer Relevance** | `96.67%` | Relevance of answer to question |
| **Completeness** | `90.00%` | Context facts coverage rate |
| **Hallucination Rate** | `10.00%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `83.33%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `10.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `6.67%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `80.00%` |
| **precision@3** | `26.66%` |
| **recall@3** | `76.67%` |
| **mrr@3** | `69.44%` |
| **ndcg@3** | `69.52%` |
| **hit@5** | `86.67%` |
| **precision@5** | `18.00%` |
| **recall@5** | `83.33%` |
| **mrr@5** | `71.11%` |
| **ndcg@5** | `72.63%` |
| **hit@7** | `86.67%` |
| **precision@7** | `12.86%` |
| **recall@7** | `83.33%` |
| **mrr@7** | `71.11%` |
| **ndcg@7** | `72.63%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `19736.8 ms` |
| Routing Latency | `2478.3 ms` |
| Search Latency | `206.8 ms` |
| Rerank Latency | `10001.7 ms` |
| Generation Latency | `1262.1 ms` |
| Self-Evaluation Latency | `981.4 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `75.0%` | `65.3%` | `62.5%` | `50.0%` | `11651.1 ms` |
| **simple** | 22 | `86.4%` | `86.4%` | `75.3%` | `86.4%` | `95.5%` | `22677.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `90.0%` | `90.0%` | `77.8%` | `85.0%` | `100.0%` | `23514.4 ms` |
| **medium** | 10 | `80.0%` | `70.0%` | `62.3%` | `70.0%` | `50.0%` | `12181.5 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 2 | `0.0%` | `0.0%` | `0.0%` | `50.0%` | `50.0%` | `14219.3 ms` |
| **rag_v2** | 28 | `92.9%` | `89.3%` | `77.8%` | `82.1%` | `85.7%` | `20130.9 ms` |
