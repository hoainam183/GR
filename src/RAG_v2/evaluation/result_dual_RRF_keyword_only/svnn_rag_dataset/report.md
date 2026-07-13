# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `22457.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `20.00%` |
| Hallucination rate | `80.00%` (24) |
| Answer relevance | `100.00%` |
| Completeness | `50.00%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `30.00%` |
| recall@3 | `81.11%` |
| mrr@3 | `82.78%` |
| ndcg@3 | `80.45%` |
| hit@5 | `86.67%` |
| precision@5 | `18.00%` |
| recall@5 | `81.11%` |
| mrr@5 | `82.78%` |
| ndcg@5 | `80.45%` |
| hit@7 | `90.00%` |
| precision@7 | `13.34%` |
| recall@7 | `84.44%` |
| mrr@7 | `83.25%` |
| ndcg@7 | `81.56%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `66.7%` | `64.2%` | `0.0%` | `87.5%` | `31454.5 ms` |
| simple | 22 | `86.4%` | `86.4%` | `86.4%` | `27.3%` | `86.4%` | `19185.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `86.4%` | `27.3%` | `86.4%` | `19185.7 ms` |
| medium | 8 | `87.5%` | `66.7%` | `64.2%` | `0.0%` | `87.5%` | `31454.5 ms` |
