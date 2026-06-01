# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 21:32:08
- **Total Queries Evaluated**: `26`

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
| `agent_enabled` | `False` |
| `web_fallback_enabled` | `False` |
| `validity_filter_enabled` | `True` |

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `92.31%` | `24` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `7.69%` | `2` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `38.46%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `23.08%` | Partially matches reference answer |
| **Ref Match Incorrect** | `38.46%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `15.38%` |
| **precision@3** | `5.13%` |
| **recall@3** | `15.38%` |
| **mrr@3** | `11.54%` |
| **ndcg@3** | `12.55%` |
| **hit@5** | `15.38%` |
| **precision@5** | `3.08%` |
| **recall@5** | `15.38%` |
| **mrr@5** | `11.54%` |
| **ndcg@5** | `12.55%` |
| **hit@7** | `15.38%` |
| **precision@7** | `2.20%` |
| **recall@7** | `15.38%` |
| **mrr@7** | `11.54%` |
| **ndcg@7** | `12.55%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10960.1 ms` |
| Routing Latency | `520.7 ms` |
| Search Latency | `125.9 ms` |
| Rerank Latency | `4911.5 ms` |
| Generation Latency | `1322.8 ms` |
| Self-Evaluation Latency | `1131.5 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `0.0%` | `0.0%` | `0.0%` | `75.0%` | `50.0%` | `12420.6 ms` |
| **simple** | 18 | `22.2%` | `22.2%` | `18.1%` | `100.0%` | `33.3%` | `10311.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `22.2%` | `22.2%` | `18.1%` | `100.0%` | `33.3%` | `10311.0 ms` |
| **medium** | 8 | `0.0%` | `0.0%` | `0.0%` | `75.0%` | `50.0%` | `12420.6 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `15.4%` | `15.4%` | `12.6%` | `92.3%` | `38.5%` | `10960.1 ms` |
