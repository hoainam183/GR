# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-02 22:20:01
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
| **Faithfulness (Grounded)** | `93.33%` | `29` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `96.67%` | Context facts coverage rate |
| **Hallucination Rate** | `3.33%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `96.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `3.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `93.33%` |
| **precision@3** | `37.78%` |
| **recall@3** | `90.56%` |
| **mrr@3** | `85.00%` |
| **ndcg@3** | `85.05%` |
| **hit@5** | `93.33%` |
| **precision@5** | `24.00%` |
| **recall@5** | `93.33%` |
| **mrr@5** | `85.00%` |
| **ndcg@5** | `86.45%` |
| **hit@7** | `93.33%` |
| **precision@7** | `17.15%` |
| **recall@7** | `93.33%` |
| **mrr@7** | `85.00%` |
| **ndcg@7** | `86.45%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10292.2 ms` |
| Routing Latency | `523.6 ms` |
| Search Latency | `106.9 ms` |
| Rerank Latency | `4815.1 ms` |
| Generation Latency | `1225.4 ms` |
| Self-Evaluation Latency | `943.4 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `75.5%` | `87.5%` | `100.0%` | `11257.0 ms` |
| **simple** | 22 | `95.5%` | `95.5%` | `90.4%` | `95.5%` | `95.5%` | `9941.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 11 | `90.9%` | `90.9%` | `84.2%` | `100.0%` | `90.9%` | `9833.9 ms` |
| **hard** | 3 | `100.0%` | `100.0%` | `83.3%` | `100.0%` | `100.0%` | `10225.2 ms` |
| **medium** | 16 | `93.8%` | `93.8%` | `88.6%` | `87.5%` | `100.0%` | `10619.9 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 2 | `50.0%` | `50.0%` | `46.0%` | `50.0%` | `100.0%` | `11627.7 ms` |
| **rag_v2** | 28 | `96.4%` | `96.4%` | `89.3%` | `96.4%` | `96.4%` | `10196.8 ms` |
