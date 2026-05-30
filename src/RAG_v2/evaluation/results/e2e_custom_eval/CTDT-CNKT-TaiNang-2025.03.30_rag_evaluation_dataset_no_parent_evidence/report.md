# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-30 23:02:03
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `80.77%` | `23` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `88.46%` | Context facts coverage rate |
| **Hallucination Rate** | `11.54%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `76.92%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `7.69%` | Partially matches reference answer |
| **Ref Match Incorrect** | `15.38%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `73.08%` |
| **precision@3** | `25.64%` |
| **recall@3** | `60.90%` |
| **mrr@3** | `44.87%` |
| **ndcg@3** | `45.77%` |
| **hit@5** | `80.77%` |
| **precision@5** | `17.69%` |
| **recall@5** | `68.59%` |
| **mrr@5** | `46.79%` |
| **ndcg@5** | `49.35%` |
| **hit@7** | `80.77%` |
| **precision@7** | `14.29%` |
| **recall@7** | `74.36%` |
| **mrr@7** | `46.79%` |
| **ndcg@7** | `51.82%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `17633.6 ms` |
| Routing Latency | `1094.9 ms` |
| Search Latency | `225.0 ms` |
| Rerank Latency | `6932.7 ms` |
| Generation Latency | `2932.7 ms` |
| Self-Evaluation Latency | `1848.7 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `54.2%` | `43.6%` | `50.0%` | `87.5%` | `22057.0 ms` |
| **simple** | 18 | `77.8%` | `75.0%` | `51.9%` | `94.4%` | `72.2%` | `15667.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `78.6%` | `78.6%` | `56.8%` | `92.9%` | `78.6%` | `16316.1 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `25941.8 ms` |
| **medium** | 11 | `81.8%` | `53.0%` | `35.2%` | `63.6%` | `72.7%` | `18555.2 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `80.8%` | `68.6%` | `49.4%` | `80.8%` | `76.9%` | `17633.6 ms` |
