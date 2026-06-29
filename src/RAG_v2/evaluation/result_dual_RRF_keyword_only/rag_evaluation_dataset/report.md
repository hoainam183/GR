# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 09:44:47
- **Total queries**: `100`
- **Avg latency**: `26615.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `88.00%` |
| Hallucination rate | `12.00%` (12) |
| Answer relevance | `99.00%` |
| Completeness | `88.00%` |
| Correctness vs gold (correct) | `65.00%` |
| Correctness vs gold (partial) | `7.00%` |
| Correctness vs gold (incorrect) | `28.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `46.00%` |
| precision@3 | `16.33%` |
| recall@3 | `45.00%` |
| mrr@3 | `40.83%` |
| ndcg@3 | `41.60%` |
| hit@5 | `48.00%` |
| precision@5 | `10.40%` |
| recall@5 | `47.00%` |
| mrr@5 | `41.28%` |
| ndcg@5 | `42.53%` |
| hit@7 | `51.00%` |
| precision@7 | `8.14%` |
| recall@7 | `51.00%` |
| mrr@7 | `41.78%` |
| ndcg@7 | `44.02%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `40.0%` | `36.0%` | `33.7%` | `96.0%` | `52.0%` | `30003.2 ms` |
| simple | 75 | `50.7%` | `50.7%` | `45.5%` | `85.3%` | `69.3%` | `25486.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `50.7%` | `50.7%` | `45.5%` | `85.3%` | `69.3%` | `25486.6 ms` |
| medium | 25 | `40.0%` | `36.0%` | `33.7%` | `96.0%` | `52.0%` | `30003.2 ms` |
