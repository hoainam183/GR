# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 13:48:20
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `73.33%` | `23` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `86.67%` | Context facts coverage rate |
| **Hallucination Rate** | `23.33%` | `7` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `86.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `10.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `3.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `93.33%` |
| **precision@3** | `33.33%` |
| **recall@3** | `83.33%` |
| **mrr@3** | `85.00%` |
| **ndcg@3** | `80.13%` |
| **hit@5** | `100.00%` |
| **precision@5** | `22.00%` |
| **recall@5** | `90.00%` |
| **mrr@5** | `86.50%` |
| **ndcg@5** | `83.18%` |
| **hit@7** | `100.00%` |
| **precision@7** | `17.62%` |
| **recall@7** | `96.67%` |
| **mrr@7** | `86.50%` |
| **ndcg@7** | `86.04%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10466.9 ms` |
| Routing Latency | `528.1 ms` |
| Search Latency | `134.3 ms` |
| Rerank Latency | `5955.1 ms` |
| Generation Latency | `1514.6 ms` |
| Self-Evaluation Latency | `1038.6 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `62.5%` | `62.3%` | `37.5%` | `62.5%` | `11840.3 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `90.8%` | `86.4%` | `95.5%` | `9967.5 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 13 | `100.0%` | `100.0%` | `86.8%` | `84.6%` | `92.3%` | `10120.9 ms` |
| **hard** | 4 | `100.0%` | `75.0%` | `63.2%` | `25.0%` | `75.0%` | `11889.9 ms` |
| **medium** | 13 | `100.0%` | `84.6%` | `85.7%` | `76.9%` | `84.6%` | `10375.0 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `100.0%` | `90.0%` | `83.2%` | `73.3%` | `86.7%` | `10466.9 ms` |
