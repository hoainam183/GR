# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-31 16:32:02
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
| **Completeness** | `96.15%` | Context facts coverage rate |
| **Hallucination Rate** | `3.85%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `57.69%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `7.69%` | Partially matches reference answer |
| **Ref Match Incorrect** | `34.62%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `34.62%` |
| **precision@3** | `11.54%` |
| **recall@3** | `32.69%` |
| **mrr@3** | `26.28%` |
| **ndcg@3** | `27.49%` |
| **hit@5** | `46.15%` |
| **precision@5** | `9.23%` |
| **recall@5** | `41.67%` |
| **mrr@5** | `28.78%` |
| **ndcg@5** | `31.34%` |
| **hit@7** | `53.85%` |
| **precision@7** | `7.69%` |
| **recall@7** | `49.36%` |
| **mrr@7** | `30.06%` |
| **ndcg@7** | `34.08%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `55006.7 ms` |
| Routing Latency | `845.2 ms` |
| Search Latency | `443.4 ms` |
| Rerank Latency | `39484.8 ms` |
| Generation Latency | `1996.1 ms` |
| Self-Evaluation Latency | `3552.1 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `50.0%` | `35.4%` | `17.3%` | `87.5%` | `50.0%` | `51343.3 ms` |
| **simple** | 18 | `44.4%` | `44.4%` | `37.6%` | `100.0%` | `61.1%` | `56635.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `44.4%` | `44.4%` | `37.6%` | `100.0%` | `61.1%` | `56635.0 ms` |
| **medium** | 8 | `50.0%` | `35.4%` | `17.3%` | `87.5%` | `50.0%` | `51343.3 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `46.2%` | `41.7%` | `31.3%` | `96.2%` | `57.7%` | `55006.7 ms` |
