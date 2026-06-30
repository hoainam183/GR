# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 16:11:52
- **Total queries**: `30`
- **Avg latency**: `15414.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `30.00%` |
| recall@3 | `83.89%` |
| mrr@3 | `81.11%` |
| ndcg@3 | `80.26%` |
| hit@5 | `93.33%` |
| precision@5 | `19.33%` |
| recall@5 | `90.56%` |
| mrr@5 | `82.78%` |
| ndcg@5 | `83.13%` |
| hit@7 | `93.33%` |
| precision@7 | `14.29%` |
| recall@7 | `91.67%` |
| mrr@7 | `82.78%` |
| ndcg@7 | `84.80%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `89.6%` | `79.7%` | `87.5%` | `100.0%` | `13834.2 ms` |
| simple | 22 | `90.9%` | `90.9%` | `84.4%` | `90.9%` | `86.4%` | `15988.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `90.9%` | `90.9%` | `84.4%` | `90.9%` | `86.4%` | `15988.9 ms` |
| medium | 8 | `100.0%` | `89.6%` | `79.7%` | `87.5%` | `100.0%` | `13834.2 ms` |
