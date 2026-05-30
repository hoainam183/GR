# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-30 12:57:16
- **Total Queries Evaluated**: `2`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `100.00%` | `2` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `0.00%` | `0` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `50.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `50.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `50.00%` |
| **precision@3** | `16.66%` |
| **recall@3** | `50.00%` |
| **mrr@3** | `50.00%` |
| **ndcg@3** | `50.00%` |
| **hit@5** | `50.00%` |
| **precision@5** | `10.00%` |
| **recall@5** | `50.00%` |
| **mrr@5** | `50.00%` |
| **ndcg@5** | `50.00%` |
| **hit@7** | `50.00%` |
| **precision@7** | `7.14%` |
| **recall@7** | `50.00%` |
| **mrr@7** | `50.00%` |
| **ndcg@7** | `50.00%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `75705.0 ms` |
| Routing Latency | `6357.4 ms` |
| Search Latency | `1749.4 ms` |
| Rerank Latency | `53403.9 ms` |
| Generation Latency | `1997.1 ms` |
| Self-Evaluation Latency | `1351.4 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **simple** | 2 | `50.0%` | `50.0%` | `50.0%` | `100.0%` | `50.0%` | `75705.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 2 | `50.0%` | `50.0%` | `50.0%` | `100.0%` | `50.0%` | `75705.0 ms` |
