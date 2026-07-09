# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 15:23:10
- **Total queries**: `3`
- **Avg latency**: `9688.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `66.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `66.67%` |
| Correctness vs gold (partial) | `33.33%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `66.67%` |
| precision@3 | `33.33%` |
| recall@3 | `66.67%` |
| mrr@3 | `66.67%` |
| ndcg@3 | `63.99%` |
| hit@5 | `66.67%` |
| precision@5 | `20.00%` |
| recall@5 | `66.67%` |
| mrr@5 | `66.67%` |
| ndcg@5 | `63.99%` |
| hit@7 | `66.67%` |
| precision@7 | `14.29%` |
| recall@7 | `66.67%` |
| mrr@7 | `66.67%` |
| ndcg@7 | `63.99%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 2 | `50.0%` | `50.0%` | `46.0%` | `50.0%` | `50.0%` | `8439.4 ms` |
| simple | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `12187.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `12187.5 ms` |
| medium | 2 | `50.0%` | `50.0%` | `46.0%` | `50.0%` | `50.0%` | `8439.4 ms` |
