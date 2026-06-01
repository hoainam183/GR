# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 15:40:40
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `76.92%` | `20` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `84.62%` | Context facts coverage rate |
| **Hallucination Rate** | `23.08%` | `6` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `80.77%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `11.54%` | Partially matches reference answer |
| **Ref Match Incorrect** | `7.69%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `88.46%` |
| **precision@3** | `32.05%` |
| **recall@3** | `78.85%` |
| **mrr@3** | `80.77%` |
| **ndcg@3** | `75.14%` |
| **hit@5** | `88.46%` |
| **precision@5** | `19.23%` |
| **recall@5** | `78.85%` |
| **mrr@5** | `80.77%` |
| **ndcg@5** | `75.14%` |
| **hit@7** | `88.46%` |
| **precision@7** | `14.29%` |
| **recall@7** | `80.77%` |
| **mrr@7** | `80.77%` |
| **ndcg@7** | `75.92%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `11140.9 ms` |
| Routing Latency | `570.5 ms` |
| Search Latency | `173.7 ms` |
| Rerank Latency | `6003.8 ms` |
| Generation Latency | `1466.4 ms` |
| Self-Evaluation Latency | `1041.1 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `43.8%` | `50.2%` | `50.0%` | `50.0%` | `13212.1 ms` |
| **simple** | 18 | `94.4%` | `94.4%` | `86.2%` | `88.9%` | `94.4%` | `10220.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `94.4%` | `94.4%` | `86.2%` | `88.9%` | `94.4%` | `10220.4 ms` |
| **hard** | 2 | `100.0%` | `41.7%` | `54.1%` | `0.0%` | `50.0%` | `10570.6 ms` |
| **medium** | 6 | `66.7%` | `44.5%` | `48.8%` | `66.7%` | `50.0%` | `14092.7 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `88.5%` | `78.8%` | `75.1%` | `76.9%` | `80.8%` | `11140.9 ms` |
