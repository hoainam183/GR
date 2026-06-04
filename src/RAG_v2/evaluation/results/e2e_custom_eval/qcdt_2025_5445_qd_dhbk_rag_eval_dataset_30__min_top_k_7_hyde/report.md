# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-02 22:57:16
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
| **Faithfulness (Grounded)** | `86.67%` | `27` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `93.33%` | Context facts coverage rate |
| **Hallucination Rate** | `10.00%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `83.33%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `13.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `3.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `90.00%` |
| **precision@3** | `32.22%` |
| **recall@3** | `90.00%` |
| **mrr@3** | `85.00%` |
| **ndcg@3** | `86.04%` |
| **hit@5** | `90.00%` |
| **precision@5** | `19.33%` |
| **recall@5** | `90.00%` |
| **mrr@5** | `85.00%` |
| **ndcg@5** | `86.04%` |
| **hit@7** | `90.00%` |
| **precision@7** | `13.81%` |
| **recall@7** | `90.00%` |
| **mrr@7** | `85.00%` |
| **ndcg@7** | `86.04%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `16002.1 ms` |
| Routing Latency | `443.9 ms` |
| Search Latency | `104.6 ms` |
| Rerank Latency | `5057.0 ms` |
| Generation Latency | `1128.2 ms` |
| Self-Evaluation Latency | `969.0 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `81.9%` | `62.5%` | `87.5%` | `18649.5 ms` |
| **simple** | 22 | `90.9%` | `90.9%` | `87.5%` | `95.5%` | `81.8%` | `15039.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 22 | `90.9%` | `90.9%` | `87.5%` | `95.5%` | `81.8%` | `15039.4 ms` |
| **medium** | 8 | `87.5%` | `87.5%` | `81.9%` | `62.5%` | `87.5%` | `18649.5 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **agent** | 3 | `66.7%` | `66.7%` | `42.1%` | `66.7%` | `66.7%` | `16244.0 ms` |
| **rag_v2** | 27 | `92.6%` | `92.6%` | `90.9%` | `88.9%` | `85.2%` | `15975.2 ms` |
