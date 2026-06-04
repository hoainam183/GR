# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-04 18:36:36
- **Total Queries Evaluated**: `50`

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
| **Faithfulness (Grounded)** | `96.00%` | `48` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `98.00%` | Context facts coverage rate |
| **Hallucination Rate** | `4.00%` | `2` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `84.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `10.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `6.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `88.00%` |
| **precision@3** | `35.33%` |
| **recall@3** | `87.33%` |
| **mrr@3** | `84.00%` |
| **ndcg@3** | `84.22%` |
| **hit@5** | `88.00%` |
| **precision@5** | `21.20%` |
| **recall@5** | `87.33%` |
| **mrr@5** | `84.00%` |
| **ndcg@5** | `84.22%` |
| **hit@7** | `90.00%` |
| **precision@7** | `15.72%` |
| **recall@7** | `90.00%` |
| **mrr@7** | `84.29%` |
| **ndcg@7** | `85.22%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `11571.8 ms` |
| Routing Latency | `457.6 ms` |
| Search Latency | `140.1 ms` |
| Rerank Latency | `5201.3 ms` |
| Generation Latency | `1286.4 ms` |
| Self-Evaluation Latency | `979.9 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 15 | `100.0%` | `97.8%` | `95.3%` | `93.3%` | `93.3%` | `12551.2 ms` |
| **simple** | 35 | `82.9%` | `82.9%` | `79.5%` | `97.1%` | `80.0%` | `11152.1 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 28 | `78.6%` | `78.6%` | `74.3%` | `96.4%` | `78.6%` | `11001.7 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `92.0%` | `0.0%` | `100.0%` | `18751.1 ms` |
| **medium** | 21 | `100.0%` | `98.4%` | `97.0%` | `100.0%` | `90.5%` | `11990.1 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 1 | `0.0%` | `0.0%` | `0.0%` | `100.0%` | `0.0%` | `11950.0 ms` |
| **rag_v2** | 49 | `89.8%` | `89.1%` | `85.9%` | `95.9%` | `85.7%` | `11564.1 ms` |
