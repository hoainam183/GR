# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-03 00:19:11
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
| **Faithfulness (Grounded)** | `96.67%` | `29` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `3.33%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `96.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `3.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `0.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `93.33%` |
| **precision@3** | `33.33%` |
| **recall@3** | `90.00%` |
| **mrr@3** | `83.89%` |
| **ndcg@3** | `84.37%` |
| **hit@5** | `96.67%` |
| **precision@5** | `21.33%` |
| **recall@5** | `95.00%` |
| **mrr@5** | `84.72%` |
| **ndcg@5** | `86.69%` |
| **hit@7** | `96.67%` |
| **precision@7** | `15.24%` |
| **recall@7** | `95.00%` |
| **mrr@7** | `84.72%` |
| **ndcg@7** | `86.69%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `12778.4 ms` |
| Routing Latency | `582.3 ms` |
| Search Latency | `127.1 ms` |
| Rerank Latency | `5700.4 ms` |
| Generation Latency | `1838.8 ms` |
| Self-Evaluation Latency | `1020.7 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `81.2%` | `71.0%` | `100.0%` | `87.5%` | `22441.5 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `92.4%` | `95.5%` | `100.0%` | `9264.6 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `100.0%` | `100.0%` | `93.5%` | `95.0%` | `100.0%` | `9343.5 ms` |
| **hard** | 1 | `100.0%` | `50.0%` | `61.3%` | `100.0%` | `100.0%` | `39823.5 ms` |
| **medium** | 9 | `88.9%` | `88.9%` | `74.5%` | `100.0%` | `88.9%` | `17406.6 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `13329.5 ms` |
| **rag_v2** | 29 | `96.5%` | `94.8%` | `86.2%` | `96.5%` | `96.5%` | `12759.4 ms` |
