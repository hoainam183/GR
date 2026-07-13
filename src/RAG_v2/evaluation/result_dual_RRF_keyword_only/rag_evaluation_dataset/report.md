# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
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
| hit@3 | `50.00%` |
| precision@3 | `17.67%` |
| recall@3 | `48.50%` |
| mrr@3 | `43.00%` |
| ndcg@3 | `43.79%` |
| hit@5 | `51.00%` |
| precision@5 | `11.40%` |
| recall@5 | `51.00%` |
| mrr@5 | `43.25%` |
| ndcg@5 | `45.01%` |
| hit@7 | `51.00%` |
| precision@7 | `8.14%` |
| recall@7 | `51.00%` |
| mrr@7 | `43.25%` |
| ndcg@7 | `45.01%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `44.0%` | `44.0%` | `39.6%` | `96.0%` | `52.0%` | `30003.2 ms` |
| simple | 75 | `53.3%` | `53.3%` | `46.8%` | `85.3%` | `69.3%` | `25486.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `53.3%` | `53.3%` | `46.8%` | `85.3%` | `69.3%` | `25486.6 ms` |
| medium | 25 | `44.0%` | `44.0%` | `39.6%` | `96.0%` | `52.0%` | `30003.2 ms` |
