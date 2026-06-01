# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 14:11:03
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `86.67%` | `27` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `90.00%` | Context facts coverage rate |
| **Hallucination Rate** | `10.00%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `86.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `10.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `3.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `83.33%` |
| **precision@3** | `30.00%` |
| **recall@3** | `74.44%` |
| **mrr@3** | `72.22%` |
| **ndcg@3** | `69.75%` |
| **hit@5** | `86.67%` |
| **precision@5** | `20.67%` |
| **recall@5** | `82.22%` |
| **mrr@5** | `72.89%` |
| **ndcg@5** | `73.47%` |
| **hit@7** | `90.00%` |
| **precision@7** | `16.19%` |
| **recall@7** | `86.67%` |
| **mrr@7** | `73.44%` |
| **ndcg@7** | `75.40%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10303.5 ms` |
| Routing Latency | `578.6 ms` |
| Search Latency | `119.6 ms` |
| Rerank Latency | `5277.8 ms` |
| Generation Latency | `1202.1 ms` |
| Self-Evaluation Latency | `1009.3 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `70.8%` | `61.2%` | `62.5%` | `75.0%` | `11122.4 ms` |
| **simple** | 22 | `86.4%` | `86.4%` | `78.0%` | `95.5%` | `90.9%` | `10005.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 21 | `90.5%` | `88.1%` | `79.8%` | `100.0%` | `85.7%` | `10129.3 ms` |
| **hard** | 3 | `66.7%` | `50.0%` | `43.5%` | `66.7%` | `66.7%` | `10496.3 ms` |
| **medium** | 6 | `83.3%` | `77.8%` | `66.2%` | `50.0%` | `100.0%` | `10816.8 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `86.7%` | `82.2%` | `73.5%` | `86.7%` | `86.7%` | `10303.5 ms` |
