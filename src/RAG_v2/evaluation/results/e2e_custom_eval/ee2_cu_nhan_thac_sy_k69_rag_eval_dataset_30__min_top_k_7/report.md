# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 14:46:48
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `90.00%` | `27` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `90.00%` | Context facts coverage rate |
| **Hallucination Rate** | `10.00%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `83.33%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `16.67%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `83.33%` |
| **precision@3** | `30.00%` |
| **recall@3** | `81.11%` |
| **mrr@3** | `77.78%` |
| **ndcg@3** | `77.44%` |
| **hit@5** | `86.67%` |
| **precision@5** | `18.67%` |
| **recall@5** | `84.44%` |
| **mrr@5** | `78.44%` |
| **ndcg@5** | `78.73%` |
| **hit@7** | `90.00%` |
| **precision@7** | `14.29%` |
| **recall@7** | `87.22%` |
| **mrr@7** | `79.00%` |
| **ndcg@7** | `80.01%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `8115.1 ms` |
| Routing Latency | `508.0 ms` |
| Search Latency | `120.0 ms` |
| Rerank Latency | `3699.7 ms` |
| Generation Latency | `1312.4 ms` |
| Self-Evaluation Latency | `1005.4 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `66.7%` | `68.4%` | `87.5%` | `87.5%` | `9767.5 ms` |
| **simple** | 22 | `90.9%` | `90.9%` | `82.5%` | `90.9%` | `81.8%` | `7514.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `94.4%` | `94.4%` | `90.3%` | `94.4%` | `88.9%` | `7642.8 ms` |
| **hard** | 2 | `100.0%` | `66.7%` | `73.5%` | `100.0%` | `100.0%` | `10745.3 ms` |
| **medium** | 10 | `70.0%` | `70.0%` | `58.9%` | `80.0%` | `70.0%` | `8439.3 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `86.7%` | `84.4%` | `78.7%` | `90.0%` | `83.3%` | `8115.1 ms` |
