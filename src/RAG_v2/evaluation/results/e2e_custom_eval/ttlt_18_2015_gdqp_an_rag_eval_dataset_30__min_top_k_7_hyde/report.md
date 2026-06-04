# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-04 20:09:55
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
| **Faithfulness (Grounded)** | `83.33%` | `27` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `93.33%` | Context facts coverage rate |
| **Hallucination Rate** | `10.00%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `86.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `13.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `0.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `90.00%` |
| **precision@3** | `34.44%` |
| **recall@3** | `90.00%` |
| **mrr@3** | `87.78%` |
| **ndcg@3** | `88.33%` |
| **hit@5** | `90.00%` |
| **precision@5** | `20.67%` |
| **recall@5** | `90.00%` |
| **mrr@5** | `87.78%` |
| **ndcg@5** | `88.33%` |
| **hit@7** | `90.00%` |
| **precision@7** | `14.77%` |
| **recall@7** | `90.00%` |
| **mrr@7** | `87.78%` |
| **ndcg@7** | `88.33%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `11746.5 ms` |
| Routing Latency | `369.3 ms` |
| Search Latency | `84.9 ms` |
| Rerank Latency | `4817.3 ms` |
| Generation Latency | `1359.0 ms` |
| Self-Evaluation Latency | `1008.0 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `75.0%` | `87.5%` | `13164.4 ms` |
| **simple** | 22 | `90.9%` | `90.9%` | `88.6%` | `86.4%` | `86.4%` | `11230.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `95.0%` | `95.0%` | `92.5%` | `85.0%` | `95.0%` | `11306.4 ms` |
| **medium** | 10 | `80.0%` | `80.0%` | `80.0%` | `80.0%` | `70.0%` | `12626.7 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `90.0%` | `90.0%` | `88.3%` | `83.3%` | `86.7%` | `11746.5 ms` |
