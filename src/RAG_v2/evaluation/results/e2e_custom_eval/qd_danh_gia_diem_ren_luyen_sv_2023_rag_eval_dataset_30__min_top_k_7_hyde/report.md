# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-02 23:16:17
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
| **Faithfulness (Grounded)** | `93.33%` | `30` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `0.00%` | `0` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `90.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `10.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `90.00%` |
| **precision@3** | `31.11%` |
| **recall@3** | `88.33%` |
| **mrr@3** | `71.67%` |
| **ndcg@3** | `74.91%` |
| **hit@5** | `90.00%` |
| **precision@5** | `18.67%` |
| **recall@5** | `88.33%` |
| **mrr@5** | `71.67%` |
| **ndcg@5** | `74.91%` |
| **hit@7** | `90.00%` |
| **precision@7** | `13.34%` |
| **recall@7** | `88.33%` |
| **mrr@7** | `71.67%` |
| **ndcg@7** | `74.91%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `13562.7 ms` |
| Routing Latency | `456.4 ms` |
| Search Latency | `118.0 ms` |
| Rerank Latency | `5194.7 ms` |
| Generation Latency | `1149.6 ms` |
| Self-Evaluation Latency | `940.4 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `81.2%` | `77.0%` | `75.0%` | `87.5%` | `11923.0 ms` |
| **simple** | 22 | `90.9%` | `90.9%` | `74.1%` | `100.0%` | `90.9%` | `14158.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 22 | `90.9%` | `90.9%` | `74.1%` | `100.0%` | `90.9%` | `14158.9 ms` |
| **medium** | 8 | `87.5%` | `81.2%` | `77.0%` | `75.0%` | `87.5%` | `11923.0 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 1 | `100.0%` | `50.0%` | `61.3%` | `0.0%` | `100.0%` | `14487.6 ms` |
| **rag_v2** | 29 | `89.7%` | `89.7%` | `75.4%` | `96.5%` | `89.7%` | `13530.8 ms` |
