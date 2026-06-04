# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-04 18:05:54
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
| **Faithfulness (Grounded)** | `90.00%` | `29` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `96.67%` | Context facts coverage rate |
| **Hallucination Rate** | `3.33%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `96.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `3.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `0.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `93.33%` |
| **precision@3** | `32.22%` |
| **recall@3** | `90.00%` |
| **mrr@3** | `93.33%` |
| **ndcg@3** | `90.75%` |
| **hit@5** | `96.67%` |
| **precision@5** | `21.33%` |
| **recall@5** | `94.00%` |
| **mrr@5** | `94.17%` |
| **ndcg@5** | `92.82%` |
| **hit@7** | `96.67%` |
| **precision@7** | `15.24%` |
| **recall@7** | `94.00%` |
| **mrr@7** | `94.17%` |
| **ndcg@7** | `92.82%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `11475.6 ms` |
| Routing Latency | `541.0 ms` |
| Search Latency | `105.2 ms` |
| Rerank Latency | `5778.0 ms` |
| Generation Latency | `1387.7 ms` |
| Self-Evaluation Latency | `1000.2 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `90.0%` | `85.6%` | `87.5%` | `100.0%` | `13275.1 ms` |
| **simple** | 22 | `95.5%` | `95.5%` | `95.5%` | `90.9%` | `95.5%` | `10821.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `92.9%` | `92.9%` | `92.9%` | `92.9%` | `92.9%` | `10848.0 ms` |
| **hard** | 2 | `100.0%` | `60.0%` | `49.8%` | `100.0%` | `100.0%` | `16706.2 ms` |
| **medium** | 14 | `100.0%` | `100.0%` | `98.9%` | `85.7%` | `100.0%` | `11355.9 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `96.7%` | `94.0%` | `92.8%` | `90.0%` | `96.7%` | `11475.6 ms` |
