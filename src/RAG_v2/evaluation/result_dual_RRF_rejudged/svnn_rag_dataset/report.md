# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:38:33
- **Total queries**: `30`
- **Avg latency**: `26651.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `86.67%` |
| Completeness | `80.00%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `31.11%` |
| recall@3 | `86.11%` |
| mrr@3 | `86.11%` |
| ndcg@3 | `84.66%` |
| hit@5 | `96.67%` |
| precision@5 | `20.00%` |
| recall@5 | `91.11%` |
| mrr@5 | `87.78%` |
| ndcg@5 | `86.98%` |
| hit@7 | `100.00%` |
| precision@7 | `14.77%` |
| recall@7 | `94.44%` |
| mrr@7 | `88.25%` |
| ndcg@7 | `88.09%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `66.7%` | `62.9%` | `37.5%` | `87.5%` | `31450.2 ms` |
| simple | 22 | `100.0%` | `100.0%` | `95.7%` | `100.0%` | `100.0%` | `24906.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `100.0%` | `100.0%` | `95.7%` | `100.0%` | `100.0%` | `24906.6 ms` |
| medium | 8 | `87.5%` | `66.7%` | `62.9%` | `37.5%` | `87.5%` | `31450.2 ms` |
