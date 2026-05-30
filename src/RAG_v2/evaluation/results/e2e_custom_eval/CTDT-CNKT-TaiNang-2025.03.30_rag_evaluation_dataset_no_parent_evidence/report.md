# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-30 22:08:06
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `84.62%` | `25` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `92.31%` | Context facts coverage rate |
| **Hallucination Rate** | `3.85%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `76.92%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `3.85%` | Partially matches reference answer |
| **Ref Match Incorrect** | `19.23%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `69.23%` |
| **precision@3** | `24.36%` |
| **recall@3** | `58.97%` |
| **mrr@3** | `42.95%` |
| **ndcg@3** | `44.28%` |
| **hit@5** | `76.92%` |
| **precision@5** | `16.15%` |
| **recall@5** | `64.74%` |
| **mrr@5** | `44.87%` |
| **ndcg@5** | `46.95%` |
| **hit@7** | `76.92%` |
| **precision@7** | `13.19%` |
| **recall@7** | `70.51%` |
| **mrr@7** | `44.87%` |
| **ndcg@7** | `49.42%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `20696.5 ms` |
| Routing Latency | `924.3 ms` |
| Search Latency | `227.9 ms` |
| Rerank Latency | `6551.5 ms` |
| Generation Latency | `2348.1 ms` |
| Self-Evaluation Latency | `3628.3 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `41.7%` | `35.8%` | `75.0%` | `75.0%` | `24120.8 ms` |
| **simple** | 18 | `77.8%` | `75.0%` | `51.9%` | `88.9%` | `77.8%` | `19174.6 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `78.6%` | `78.6%` | `56.8%` | `92.9%` | `78.6%` | `19864.7 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `21446.5 ms` |
| **medium** | 11 | `72.7%` | `43.9%` | `29.6%` | `72.7%` | `72.7%` | `21687.0 ms` |
