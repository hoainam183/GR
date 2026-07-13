# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `30`
- **Avg latency**: `10734.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `96.67%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `46.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `43.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `17.78%` |
| recall@3 | `48.33%` |
| mrr@3 | `50.00%` |
| ndcg@3 | `48.71%` |
| hit@5 | `50.00%` |
| precision@5 | `10.67%` |
| recall@5 | `48.33%` |
| mrr@5 | `50.00%` |
| ndcg@5 | `48.71%` |
| hit@7 | `50.00%` |
| precision@7 | `7.62%` |
| recall@7 | `48.33%` |
| mrr@7 | `50.00%` |
| ndcg@7 | `48.71%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `50.0%` | `43.8%` | `45.2%` | `100.0%` | `37.5%` | `12741.9 ms` |
| simple | 22 | `50.0%` | `50.0%` | `50.0%` | `100.0%` | `50.0%` | `10004.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `47.8%` | `47.8%` | `47.8%` | `100.0%` | `52.2%` | `10125.1 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `7777.5 ms` |
| medium | 6 | `50.0%` | `41.7%` | `43.5%` | `100.0%` | `16.7%` | `13563.5 ms` |
