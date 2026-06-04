# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-03 20:42:06
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
| **Faithfulness (Grounded)** | `93.33%` | `28` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `96.67%` | Context facts coverage rate |
| **Hallucination Rate** | `6.67%` | `2` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `90.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `6.67%` | Partially matches reference answer |
| **Ref Match Incorrect** | `3.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `90.00%` |
| **precision@3** | `30.00%` |
| **recall@3** | `86.67%` |
| **mrr@3** | `84.44%` |
| **ndcg@3** | `83.77%` |
| **hit@5** | `90.00%` |
| **precision@5** | `18.67%` |
| **recall@5** | `88.33%` |
| **mrr@5** | `84.44%` |
| **ndcg@5** | `84.65%` |
| **hit@7** | `90.00%` |
| **precision@7** | `13.34%` |
| **recall@7** | `88.33%` |
| **mrr@7** | `84.44%` |
| **ndcg@7** | `84.65%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10574.7 ms` |
| Routing Latency | `564.9 ms` |
| Search Latency | `84.8 ms` |
| Rerank Latency | `4233.0 ms` |
| Generation Latency | `1344.1 ms` |
| Self-Evaluation Latency | `1010.1 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `68.8%` | `65.8%` | `100.0%` | `75.0%` | `10922.0 ms` |
| **simple** | 22 | `95.5%` | `95.5%` | `91.5%` | `90.9%` | `95.5%` | `10448.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 17 | `100.0%` | `100.0%` | `94.9%` | `94.1%` | `100.0%` | `10588.6 ms` |
| **hard** | 2 | `50.0%` | `25.0%` | `19.4%` | `100.0%` | `0.0%` | `8543.5 ms` |
| **medium** | 11 | `81.8%` | `81.8%` | `80.7%` | `90.9%` | `90.9%` | `10922.4 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 2 | `0.0%` | `0.0%` | `0.0%` | `100.0%` | `50.0%` | `11970.8 ms` |
| **rag_v2** | 28 | `96.4%` | `94.6%` | `90.7%` | `92.9%` | `92.9%` | `10474.9 ms` |
