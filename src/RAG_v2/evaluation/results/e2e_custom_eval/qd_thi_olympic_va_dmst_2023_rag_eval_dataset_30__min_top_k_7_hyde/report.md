# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-03 21:23:56
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
| **Faithfulness (Grounded)** | `96.67%` | `30` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `96.67%` | Context facts coverage rate |
| **Hallucination Rate** | `0.00%` | `0` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `70.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `30.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `70.00%` |
| **precision@3** | `30.00%` |
| **recall@3** | `68.89%` |
| **mrr@3** | `70.00%` |
| **ndcg@3** | `69.01%` |
| **hit@5** | `70.00%` |
| **precision@5** | `18.67%` |
| **recall@5** | `70.00%` |
| **mrr@5** | `70.00%` |
| **ndcg@5** | `69.62%` |
| **hit@7** | `70.00%` |
| **precision@7** | `13.34%` |
| **recall@7** | `70.00%` |
| **mrr@7** | `70.00%` |
| **ndcg@7** | `69.62%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `11988.8 ms` |
| Routing Latency | `672.4 ms` |
| Search Latency | `102.6 ms` |
| Rerank Latency | `4831.8 ms` |
| Generation Latency | `1347.5 ms` |
| Self-Evaluation Latency | `982.4 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `75.0%` | `73.6%` | `87.5%` | `75.0%` | `13387.4 ms` |
| **simple** | 22 | `68.2%` | `68.2%` | `68.2%` | `100.0%` | `68.2%` | `11480.2 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 13 | `69.2%` | `69.2%` | `69.2%` | `100.0%` | `69.2%` | `10952.1 ms` |
| **hard** | 3 | `66.7%` | `66.7%` | `62.8%` | `66.7%` | `66.7%` | `15790.2 ms` |
| **medium** | 14 | `71.4%` | `71.4%` | `71.4%` | `100.0%` | `71.4%` | `12136.9 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 1 | `0.0%` | `0.0%` | `0.0%` | `100.0%` | `0.0%` | `13240.0 ms` |
| **rag_v2** | 29 | `72.4%` | `72.4%` | `72.0%` | `96.5%` | `72.4%` | `11945.7 ms` |
