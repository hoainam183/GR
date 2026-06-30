# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 12:35:38
- **Total queries**: `30`
- **Avg latency**: `20311.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `100.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `32.22%` |
| recall@3 | `90.00%` |
| mrr@3 | `90.00%` |
| ndcg@3 | `88.77%` |
| hit@5 | `100.00%` |
| precision@5 | `21.33%` |
| recall@5 | `96.67%` |
| mrr@5 | `91.67%` |
| ndcg@5 | `91.88%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `96.67%` |
| mrr@7 | `91.67%` |
| ndcg@7 | `91.88%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `87.5%` | `74.2%` | `100.0%` | `100.0%` | `21052.9 ms` |
| simple | 22 | `100.0%` | `100.0%` | `98.3%` | `95.5%` | `100.0%` | `20042.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `100.0%` | `100.0%` | `98.4%` | `95.7%` | `100.0%` | `19802.8 ms` |
| medium | 7 | `100.0%` | `85.7%` | `70.5%` | `100.0%` | `100.0%` | `21983.8 ms` |
