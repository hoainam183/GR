# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-03 19:53:26
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
| **Faithfulness (Grounded)** | `76.67%` | `25` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `86.67%` | Context facts coverage rate |
| **Hallucination Rate** | `16.67%` | `5` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `63.33%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `30.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `6.67%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `66.67%` |
| **precision@3** | `23.33%` |
| **recall@3** | `63.33%` |
| **mrr@3** | `59.44%` |
| **ndcg@3** | `58.73%` |
| **hit@5** | `66.67%` |
| **precision@5** | `14.67%` |
| **recall@5** | `65.00%` |
| **mrr@5** | `59.44%` |
| **ndcg@5** | `59.52%` |
| **hit@7** | `73.33%` |
| **precision@7** | `11.91%` |
| **recall@7** | `73.33%` |
| **mrr@7** | `60.56%` |
| **ndcg@7** | `62.62%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `12616.8 ms` |
| Routing Latency | `610.4 ms` |
| Search Latency | `110.7 ms` |
| Rerank Latency | `4801.8 ms` |
| Generation Latency | `1220.0 ms` |
| Self-Evaluation Latency | `960.7 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `37.5%` | `31.2%` | `30.8%` | `87.5%` | `50.0%` | `13728.6 ms` |
| **simple** | 22 | `77.3%` | `77.3%` | `70.0%` | `72.7%` | `68.2%` | `12212.6 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `77.8%` | `77.8%` | `70.9%` | `72.2%` | `66.7%` | `11806.5 ms` |
| **hard** | 1 | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `10025.2 ms` |
| **medium** | 11 | `54.5%` | `50.0%` | `46.3%` | `90.9%` | `63.6%` | `14178.5 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 3 | `33.3%` | `33.3%` | `33.3%` | `66.7%` | `66.7%` | `11647.7 ms` |
| **rag_v2** | 27 | `70.4%` | `68.5%` | `62.4%` | `77.8%` | `63.0%` | `12724.5 ms` |
