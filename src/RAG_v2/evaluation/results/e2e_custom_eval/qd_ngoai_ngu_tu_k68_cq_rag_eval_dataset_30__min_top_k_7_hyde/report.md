# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-03 09:46:16
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
| **Completeness** | `93.33%` | Context facts coverage rate |
| **Hallucination Rate** | `3.33%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `80.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `6.67%` | Partially matches reference answer |
| **Ref Match Incorrect** | `13.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `80.00%` |
| **precision@3** | `28.89%` |
| **recall@3** | `75.56%` |
| **mrr@3** | `76.11%` |
| **ndcg@3** | `73.74%` |
| **hit@5** | `83.33%` |
| **precision@5** | `18.67%` |
| **recall@5** | `80.56%` |
| **mrr@5** | `76.78%` |
| **ndcg@5** | `75.82%` |
| **hit@7** | `83.33%` |
| **precision@7** | `13.34%` |
| **recall@7** | `80.56%` |
| **mrr@7** | `76.78%` |
| **ndcg@7** | `75.82%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `11762.6 ms` |
| Routing Latency | `411.1 ms` |
| Search Latency | `147.5 ms` |
| Rerank Latency | `4377.2 ms` |
| Generation Latency | `1088.2 ms` |
| Self-Evaluation Latency | `939.3 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `62.5%` | `52.1%` | `46.6%` | `87.5%` | `62.5%` | `11351.2 ms` |
| **simple** | 22 | `90.9%` | `90.9%` | `86.4%` | `95.5%` | `86.4%` | `11912.2 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 17 | `100.0%` | `100.0%` | `94.2%` | `100.0%` | `94.1%` | `12655.2 ms` |
| **hard** | 3 | `100.0%` | `72.2%` | `79.3%` | `100.0%` | `100.0%` | `9716.1 ms` |
| **medium** | 10 | `50.0%` | `50.0%` | `43.5%` | `80.0%` | `50.0%` | `10859.2 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 4 | `50.0%` | `50.0%` | `37.5%` | `50.0%` | `50.0%` | `12654.3 ms` |
| **rag_v2** | 26 | `88.5%` | `85.3%` | `81.7%` | `100.0%` | `84.6%` | `11625.4 ms` |
