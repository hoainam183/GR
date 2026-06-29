# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 16:14:59
- **Total queries**: `30`
- **Avg latency**: `19287.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `96.67%` |
| precision@3 | `33.33%` |
| recall@3 | `93.33%` |
| mrr@3 | `96.67%` |
| ndcg@3 | `93.82%` |
| hit@5 | `100.00%` |
| precision@5 | `21.33%` |
| recall@5 | `98.33%` |
| mrr@5 | `97.50%` |
| ndcg@5 | `96.14%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `98.33%` |
| mrr@7 | `97.50%` |
| ndcg@7 | `96.14%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `92.6%` | `100.0%` | `75.0%` | `20345.0 ms` |
| simple | 22 | `100.0%` | `100.0%` | `97.4%` | `100.0%` | `95.5%` | `18903.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `100.0%` | `100.0%` | `97.6%` | `100.0%` | `95.8%` | `19223.6 ms` |
| medium | 6 | `100.0%` | `91.7%` | `90.2%` | `100.0%` | `66.7%` | `19544.5 ms` |
