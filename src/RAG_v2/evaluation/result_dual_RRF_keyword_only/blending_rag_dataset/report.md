# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `12890.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `34.44%` |
| recall@3 | `83.33%` |
| mrr@3 | `84.44%` |
| ndcg@3 | `82.15%` |
| hit@5 | `86.67%` |
| precision@5 | `20.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `84.44%` |
| ndcg@5 | `83.43%` |
| hit@7 | `86.67%` |
| precision@7 | `14.77%` |
| recall@7 | `83.33%` |
| mrr@7 | `84.44%` |
| ndcg@7 | `83.99%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `99.0%` | `100.0%` | `100.0%` | `12381.1 ms` |
| simple | 22 | `81.8%` | `79.5%` | `77.8%` | `90.9%` | `95.5%` | `13075.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `82.6%` | `80.4%` | `78.8%` | `91.3%` | `95.7%` | `12987.2 ms` |
| medium | 7 | `100.0%` | `92.9%` | `98.8%` | `100.0%` | `100.0%` | `12571.4 ms` |
