# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 13:09:53
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `83.33%` | `26` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `13.33%` | `4` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `96.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `3.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `0.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `100.00%` |
| **precision@3** | `37.78%` |
| **recall@3** | `91.11%` |
| **mrr@3** | `93.89%` |
| **ndcg@3** | `89.60%` |
| **hit@5** | `100.00%` |
| **precision@5** | `25.33%` |
| **recall@5** | `96.67%` |
| **mrr@5** | `93.89%` |
| **ndcg@5** | `92.64%` |
| **hit@7** | `100.00%` |
| **precision@7** | `18.10%` |
| **recall@7** | `96.67%` |
| **mrr@7** | `93.89%` |
| **ndcg@7** | `92.64%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `12704.4 ms` |
| Routing Latency | `892.8 ms` |
| Search Latency | `103.3 ms` |
| Rerank Latency | `4014.6 ms` |
| Generation Latency | `1365.0 ms` |
| Self-Evaluation Latency | `1077.0 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `87.5%` | `78.6%` | `75.0%` | `87.5%` | `14190.6 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `97.7%` | `86.4%` | `100.0%` | `12163.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `100.0%` | `100.0%` | `97.2%` | `88.9%` | `100.0%` | `12382.5 ms` |
| **medium** | 12 | `100.0%` | `91.7%` | `85.8%` | `75.0%` | `91.7%` | `13187.3 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `100.0%` | `96.7%` | `92.6%` | `83.3%` | `96.7%` | `12704.4 ms` |
