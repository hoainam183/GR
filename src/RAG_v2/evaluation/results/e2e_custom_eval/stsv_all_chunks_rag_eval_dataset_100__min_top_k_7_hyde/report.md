# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-04 19:39:43
- **Total Queries Evaluated**: `100`

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
| **Faithfulness (Grounded)** | `92.00%` | `95` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `99.00%` | Context facts coverage rate |
| **Hallucination Rate** | `5.00%` | `5` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `90.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `2.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `8.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `84.00%` |
| **precision@3** | `32.33%` |
| **recall@3** | `77.50%` |
| **mrr@3** | `70.83%` |
| **ndcg@3** | `70.14%` |
| **hit@5** | `88.00%` |
| **precision@5** | `22.20%` |
| **recall@5** | `85.50%` |
| **mrr@5** | `71.73%` |
| **ndcg@5** | `73.97%` |
| **hit@7** | `89.00%` |
| **precision@7** | `16.15%` |
| **recall@7** | `87.00%` |
| **mrr@7** | `71.90%` |
| **ndcg@7** | `74.54%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `13235.4 ms` |
| Routing Latency | `599.4 ms` |
| Search Latency | `128.1 ms` |
| Rerank Latency | `7379.0 ms` |
| Generation Latency | `1518.3 ms` |
| Self-Evaluation Latency | `1052.6 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 30 | `93.3%` | `85.0%` | `71.7%` | `86.7%` | `93.3%` | `13622.6 ms` |
| **simple** | 70 | `85.7%` | `85.7%` | `75.0%` | `94.3%` | `88.6%` | `13069.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 70 | `85.7%` | `85.7%` | `75.0%` | `94.3%` | `88.6%` | `13069.4 ms` |
| **medium** | 30 | `93.3%` | `85.0%` | `71.7%` | `86.7%` | `93.3%` | `13622.6 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 2 | `50.0%` | `50.0%` | `46.0%` | `50.0%` | `100.0%` | `25615.0 ms` |
| **rag_v2** | 98 | `88.8%` | `86.2%` | `74.6%` | `92.9%` | `89.8%` | `12982.7 ms` |
