# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:23:38
- **Total queries**: `30`
- **Avg latency**: `29956.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `10.00%` (3) |
| Answer relevance | `83.33%` |
| Completeness | `76.67%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `32.22%` |
| recall@3 | `88.33%` |
| mrr@3 | `86.11%` |
| ndcg@3 | `86.19%` |
| hit@5 | `93.33%` |
| precision@5 | `20.67%` |
| recall@5 | `93.33%` |
| mrr@5 | `86.78%` |
| ndcg@5 | `88.36%` |
| hit@7 | `93.33%` |
| precision@7 | `14.77%` |
| recall@7 | `93.33%` |
| mrr@7 | `86.78%` |
| ndcg@7 | `88.36%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `100.0%` | `86.0%` | `100.0%` | `100.0%` | `45300.7 ms` |
| simple | 22 | `90.9%` | `90.9%` | `89.2%` | `86.4%` | `95.5%` | `24377.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `90.5%` | `90.5%` | `88.7%` | `85.7%` | `95.2%` | `23488.7 ms` |
| medium | 9 | `100.0%` | `100.0%` | `87.5%` | `100.0%` | `100.0%` | `45049.0 ms` |
