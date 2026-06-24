# RAG Evaluation Report (production config)

- **Date**: 2026-06-22 16:17:16
- **Total queries**: `30`
- **Avg latency**: `12187.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `93.33%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `30.00%` |
| recall@3 | `86.11%` |
| mrr@3 | `84.44%` |
| ndcg@3 | `83.70%` |
| hit@5 | `96.67%` |
| precision@5 | `19.33%` |
| recall@5 | `91.11%` |
| mrr@5 | `86.11%` |
| ndcg@5 | `87.30%` |
| hit@7 | `96.67%` |
| precision@7 | `13.81%` |
| recall@7 | `91.11%` |
| mrr@7 | `86.11%` |
| ndcg@7 | `87.30%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `66.7%` | `64.1%` | `87.5%` | `62.5%` | `10147.2 ms` |
| simple | 22 | `100.0%` | `100.0%` | `95.7%` | `95.5%` | `95.5%` | `12929.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `100.0%` | `100.0%` | `95.7%` | `95.5%` | `95.5%` | `12929.4 ms` |
| medium | 8 | `87.5%` | `66.7%` | `64.1%` | `87.5%` | `62.5%` | `10147.2 ms` |
