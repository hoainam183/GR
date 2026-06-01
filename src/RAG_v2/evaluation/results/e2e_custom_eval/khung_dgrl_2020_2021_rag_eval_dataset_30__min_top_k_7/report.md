# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 17:25:47
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `93.33%` | `30` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `86.67%` | Context facts coverage rate |
| **Hallucination Rate** | `0.00%` | `0` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `76.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `6.67%` | Partially matches reference answer |
| **Ref Match Incorrect** | `16.67%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `83.33%` |
| **precision@3** | `28.89%` |
| **recall@3** | `83.33%` |
| **mrr@3** | `81.67%` |
| **ndcg@3** | `82.10%` |
| **hit@5** | `83.33%` |
| **precision@5** | `17.33%` |
| **recall@5** | `83.33%` |
| **mrr@5** | `81.67%` |
| **ndcg@5** | `82.10%` |
| **hit@7** | `83.33%` |
| **precision@7** | `12.38%` |
| **recall@7** | `83.33%` |
| **mrr@7** | `81.67%` |
| **ndcg@7** | `82.10%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `8896.6 ms` |
| Routing Latency | `539.9 ms` |
| Search Latency | `142.2 ms` |
| Rerank Latency | `4760.4 ms` |
| Generation Latency | `1068.3 ms` |
| Self-Evaluation Latency | `995.6 ms` |
| **HyDE Fallback Trigger Rate** | `13.33%` (`4` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `87.5%` | `75.0%` | `9868.7 ms` |
| **simple** | 22 | `77.3%` | `77.3%` | `75.6%` | `95.5%` | `77.3%` | `8543.1 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 22 | `77.3%` | `77.3%` | `75.6%` | `95.5%` | `77.3%` | `8543.1 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `0.0%` | `9791.9 ms` |
| **medium** | 7 | `100.0%` | `100.0%` | `100.0%` | `85.7%` | `85.7%` | `9879.7 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `83.3%` | `83.3%` | `82.1%` | `93.3%` | `76.7%` | `8896.6 ms` |
