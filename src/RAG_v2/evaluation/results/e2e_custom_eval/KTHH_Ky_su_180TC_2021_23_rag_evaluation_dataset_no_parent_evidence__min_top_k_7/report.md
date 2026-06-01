# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 17:48:22
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `80.77%` | `21` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `84.62%` | Context facts coverage rate |
| **Hallucination Rate** | `19.23%` | `5` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `76.92%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `11.54%` | Partially matches reference answer |
| **Ref Match Incorrect** | `11.54%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `88.46%` |
| **precision@3** | `34.61%` |
| **recall@3** | `80.13%` |
| **mrr@3** | `78.85%` |
| **ndcg@3** | `75.34%` |
| **hit@5** | `88.46%` |
| **precision@5** | `23.08%` |
| **recall@5** | `84.62%` |
| **mrr@5** | `78.85%` |
| **ndcg@5** | `77.83%` |
| **hit@7** | `88.46%` |
| **precision@7** | `17.04%` |
| **recall@7** | `86.54%` |
| **mrr@7** | `78.85%` |
| **ndcg@7** | `78.61%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `9813.6 ms` |
| Routing Latency | `714.5 ms` |
| Search Latency | `119.8 ms` |
| Rerank Latency | `5461.1 ms` |
| Generation Latency | `1203.6 ms` |
| Self-Evaluation Latency | `1062.4 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `75.0%` | `71.4%` | `50.0%` | `75.0%` | `11624.3 ms` |
| **simple** | 18 | `88.9%` | `88.9%` | `80.7%` | `94.4%` | `77.8%` | `9008.8 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 19 | `89.5%` | `89.5%` | `81.1%` | `94.7%` | `79.0%` | `9017.8 ms` |
| **hard** | 2 | `50.0%` | `50.0%` | `47.3%` | `0.0%` | `50.0%` | `11973.3 ms` |
| **medium** | 5 | `100.0%` | `80.0%` | `77.5%` | `60.0%` | `80.0%` | `11973.5 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `88.5%` | `84.6%` | `77.8%` | `80.8%` | `76.9%` | `9813.6 ms` |
