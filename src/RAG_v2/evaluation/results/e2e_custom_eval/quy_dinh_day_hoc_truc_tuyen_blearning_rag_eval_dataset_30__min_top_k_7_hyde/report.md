# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-03 22:13:57
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
| **Faithfulness (Grounded)** | `90.00%` | `27` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `10.00%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `73.33%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `3.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `23.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `76.67%` |
| **precision@3** | `27.78%` |
| **recall@3** | `76.67%` |
| **mrr@3** | `76.67%` |
| **ndcg@3** | `76.40%` |
| **hit@5** | `76.67%` |
| **precision@5** | `16.67%` |
| **recall@5** | `76.67%` |
| **mrr@5** | `76.67%` |
| **ndcg@5** | `76.40%` |
| **hit@7** | `76.67%` |
| **precision@7** | `11.91%` |
| **recall@7** | `76.67%` |
| **mrr@7** | `76.67%` |
| **ndcg@7** | `76.40%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `18301.0 ms` |
| Routing Latency | `1477.7 ms` |
| Search Latency | `162.0 ms` |
| Rerank Latency | `6982.3 ms` |
| Generation Latency | `1120.5 ms` |
| Self-Evaluation Latency | `961.6 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `75.0%` | `74.0%` | `75.0%` | `75.0%` | `30697.9 ms` |
| **simple** | 22 | `77.3%` | `77.3%` | `77.3%` | `95.5%` | `72.7%` | `13793.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 16 | `68.8%` | `68.8%` | `68.8%` | `93.8%` | `68.8%` | `13676.1 ms` |
| **medium** | 14 | `85.7%` | `85.7%` | `85.1%` | `85.7%` | `78.6%` | `23586.6 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 1 | `100.0%` | `100.0%` | `92.0%` | `100.0%` | `100.0%` | `21371.8 ms` |
| **rag_v2** | 29 | `75.9%` | `75.9%` | `75.9%` | `89.7%` | `72.4%` | `18195.1 ms` |
