# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-02 22:35:17
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
| **hit@3** | `93.33%` |
| **precision@3** | `37.78%` |
| **recall@3** | `91.67%` |
| **mrr@3** | `91.67%` |
| **ndcg@3** | `90.28%` |
| **hit@5** | `93.33%` |
| **precision@5** | `22.67%` |
| **recall@5** | `91.67%` |
| **mrr@5** | `91.67%` |
| **ndcg@5** | `90.28%` |
| **hit@7** | `93.33%` |
| **precision@7** | `16.19%` |
| **recall@7** | `91.67%` |
| **mrr@7** | `91.67%` |
| **ndcg@7** | `90.28%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `8455.8 ms` |
| Routing Latency | `414.5 ms` |
| Search Latency | `81.6 ms` |
| Rerank Latency | `4024.0 ms` |
| Generation Latency | `1106.4 ms` |
| Self-Evaluation Latency | `899.5 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `81.2%` | `80.7%` | `75.0%` | `75.0%` | `11043.8 ms` |
| **simple** | 22 | `95.5%` | `95.5%` | `93.8%` | `100.0%` | `95.5%` | `7514.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 23 | `95.7%` | `93.5%` | `92.0%` | `100.0%` | `95.7%` | `7677.1 ms` |
| **medium** | 7 | `85.7%` | `85.7%` | `84.6%` | `71.4%` | `71.4%` | `11014.6 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 3 | `66.7%` | `66.7%` | `66.7%` | `66.7%` | `66.7%` | `8510.7 ms` |
| **rag_v2** | 27 | `96.3%` | `94.4%` | `92.9%` | `96.3%` | `92.6%` | `8449.7 ms` |
