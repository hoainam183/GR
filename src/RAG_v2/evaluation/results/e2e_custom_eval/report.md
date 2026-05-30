# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-30 13:13:52
- **Total Queries Evaluated**: `2`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `100.00%` | `2` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `0.00%` | `0` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `100.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `0.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `100.00%` |
| **precision@3** | `33.33%` |
| **recall@3** | `100.00%` |
| **mrr@3** | `100.00%` |
| **ndcg@3** | `100.00%` |
| **hit@5** | `100.00%` |
| **precision@5** | `20.00%` |
| **recall@5** | `100.00%` |
| **mrr@5** | `100.00%` |
| **ndcg@5** | `100.00%` |
| **hit@7** | `100.00%` |
| **precision@7** | `14.29%` |
| **recall@7** | `100.00%` |
| **mrr@7** | `100.00%` |
| **ndcg@7** | `100.00%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `25361.5 ms` |
| Routing Latency | `1257.5 ms` |
| Search Latency | `239.6 ms` |
| Rerank Latency | `7569.9 ms` |
| Generation Latency | `1302.5 ms` |
| Self-Evaluation Latency | `3201.0 ms` |
| **HyDE Fallback Trigger Rate** | `100.00%` (`2` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **simple** | 2 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `25361.5 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 2 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `25361.5 ms` |
