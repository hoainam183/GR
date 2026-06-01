# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 20:07:45
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
| `hyde_enabled` | `False` |
| `decomposer_enabled` | `True` |
| `reflection_enabled` | `True` |
| `complexity_router_enabled` | `True` |
| `parent_context_enabled` | `True` |
| `agent_enabled` | `False` |
| `web_fallback_enabled` | `False` |
| `validity_filter_enabled` | `False` |

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `88.46%` | `24` grounded responses |
| **Answer Relevance** | `96.15%` | Relevance of answer to question |
| **Completeness** | `96.15%` | Context facts coverage rate |
| **Hallucination Rate** | `7.69%` | `2` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `96.15%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `3.85%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `88.46%` |
| **precision@3** | `35.90%` |
| **recall@3** | `84.62%` |
| **mrr@3** | `82.69%` |
| **ndcg@3** | `81.71%` |
| **hit@5** | `92.31%` |
| **precision@5** | `22.31%` |
| **recall@5** | `88.46%` |
| **mrr@5** | `83.65%` |
| **ndcg@5** | `83.36%` |
| **hit@7** | `92.31%` |
| **precision@7** | `15.94%` |
| **recall@7** | `88.46%` |
| **mrr@7** | `83.65%` |
| **ndcg@7** | `83.36%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10469.4 ms` |
| Routing Latency | `428.5 ms` |
| Search Latency | `108.8 ms` |
| Rerank Latency | `5269.5 ms` |
| Generation Latency | `2121.3 ms` |
| Self-Evaluation Latency | `1219.5 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `75.0%` | `74.0%` | `87.5%` | `100.0%` | `13513.8 ms` |
| **simple** | 18 | `94.4%` | `94.4%` | `87.5%` | `88.9%` | `94.4%` | `9116.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `94.4%` | `94.4%` | `87.5%` | `88.9%` | `94.4%` | `9116.3 ms` |
| **medium** | 8 | `87.5%` | `75.0%` | `74.0%` | `87.5%` | `100.0%` | `13513.8 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `92.3%` | `88.5%` | `83.4%` | `88.5%` | `96.2%` | `10469.4 ms` |
