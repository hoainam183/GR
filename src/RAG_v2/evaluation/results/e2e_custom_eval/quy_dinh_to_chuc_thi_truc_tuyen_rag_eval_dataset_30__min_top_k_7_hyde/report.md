# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-04 17:49:38
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
| **Faithfulness (Grounded)** | `96.67%` | `29` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `3.33%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `83.33%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `3.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `13.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `86.67%` |
| **precision@3** | `34.44%` |
| **recall@3** | `85.00%` |
| **mrr@3** | `86.67%` |
| **ndcg@3** | `85.38%` |
| **hit@5** | `86.67%` |
| **precision@5** | `21.33%` |
| **recall@5** | `86.67%` |
| **mrr@5** | `86.67%` |
| **ndcg@5** | `86.26%` |
| **hit@7** | `86.67%` |
| **precision@7** | `15.24%` |
| **recall@7** | `86.67%` |
| **mrr@7** | `86.67%` |
| **ndcg@7** | `86.26%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10842.0 ms` |
| Routing Latency | `707.0 ms` |
| Search Latency | `102.8 ms` |
| Rerank Latency | `4656.0 ms` |
| Generation Latency | `1212.2 ms` |
| Self-Evaluation Latency | `977.7 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `86.0%` | `100.0%` | `87.5%` | `10513.8 ms` |
| **simple** | 22 | `86.4%` | `86.4%` | `86.4%` | `95.5%` | `81.8%` | `10961.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 22 | `86.4%` | `86.4%` | `86.4%` | `95.5%` | `81.8%` | `10961.3 ms` |
| **medium** | 8 | `87.5%` | `87.5%` | `86.0%` | `100.0%` | `87.5%` | `10513.8 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `86.7%` | `86.7%` | `86.3%` | `96.7%` | `83.3%` | `10842.0 ms` |
