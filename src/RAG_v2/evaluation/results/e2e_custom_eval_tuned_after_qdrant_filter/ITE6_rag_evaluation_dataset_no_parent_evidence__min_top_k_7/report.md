# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 00:01:09
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
| **Faithfulness (Grounded)** | `96.15%` | `25` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `92.31%` | Context facts coverage rate |
| **Hallucination Rate** | `3.85%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `73.08%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `7.69%` | Partially matches reference answer |
| **Ref Match Incorrect** | `19.23%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `46.15%` |
| **precision@3** | `15.38%` |
| **recall@3** | `44.23%` |
| **mrr@3** | `39.74%` |
| **ndcg@3** | `39.90%` |
| **hit@5** | `53.85%` |
| **precision@5** | `10.77%` |
| **recall@5** | `49.36%` |
| **mrr@5** | `41.47%` |
| **ndcg@5** | `42.26%` |
| **hit@7** | `57.69%` |
| **precision@7** | `8.24%` |
| **recall@7** | `53.21%` |
| **mrr@7** | `42.12%` |
| **ndcg@7** | `43.63%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `61553.3 ms` |
| Routing Latency | `1089.9 ms` |
| Search Latency | `429.4 ms` |
| Rerank Latency | `39604.8 ms` |
| Generation Latency | `2624.5 ms` |
| Self-Evaluation Latency | `2755.0 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `62.5%` | `47.9%` | `29.4%` | `87.5%` | `62.5%` | `64714.5 ms` |
| **simple** | 18 | `50.0%` | `50.0%` | `47.9%` | `100.0%` | `77.8%` | `60148.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `50.0%` | `50.0%` | `47.9%` | `100.0%` | `77.8%` | `60148.4 ms` |
| **medium** | 8 | `62.5%` | `47.9%` | `29.4%` | `87.5%` | `62.5%` | `64714.5 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `53.8%` | `49.4%` | `42.3%` | `96.2%` | `73.1%` | `61553.3 ms` |
