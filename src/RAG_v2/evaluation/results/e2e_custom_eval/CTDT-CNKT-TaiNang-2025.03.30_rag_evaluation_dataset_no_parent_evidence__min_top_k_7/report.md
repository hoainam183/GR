# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 14:29:11
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `84.62%` | `25` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `84.62%` | Context facts coverage rate |
| **Hallucination Rate** | `3.85%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `76.92%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `11.54%` | Partially matches reference answer |
| **Ref Match Incorrect** | `11.54%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `76.92%` |
| **precision@3** | `26.92%` |
| **recall@3** | `62.82%` |
| **mrr@3** | `46.79%` |
| **ndcg@3** | `47.26%` |
| **hit@5** | `84.62%` |
| **precision@5** | `19.23%` |
| **recall@5** | `71.47%` |
| **mrr@5** | `48.72%` |
| **ndcg@5** | `51.39%` |
| **hit@7** | `84.62%` |
| **precision@7** | `14.84%` |
| **recall@7** | `74.68%` |
| **mrr@7** | `48.72%` |
| **ndcg@7** | `52.87%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10295.1 ms` |
| Routing Latency | `574.0 ms` |
| Search Latency | `143.8 ms` |
| Rerank Latency | `5407.2 ms` |
| Generation Latency | `1301.7 ms` |
| Self-Evaluation Latency | `1084.5 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `63.5%` | `50.2%` | `75.0%` | `62.5%` | `12003.8 ms` |
| **simple** | 18 | `77.8%` | `75.0%` | `51.9%` | `88.9%` | `83.3%` | `9535.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `78.6%` | `78.6%` | `56.8%` | `92.9%` | `85.7%` | `9682.2 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `11905.6 ms` |
| **medium** | 11 | `90.9%` | `59.9%` | `40.1%` | `72.7%` | `63.6%` | `10928.9 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `84.6%` | `71.5%` | `51.4%` | `84.6%` | `76.9%` | `10295.1 ms` |
