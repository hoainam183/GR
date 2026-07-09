# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 15:26:34
- **Total queries**: `30`
- **Avg latency**: `21854.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `32.22%` |
| recall@3 | `86.67%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `85.17%` |
| hit@5 | `96.67%` |
| precision@5 | `21.33%` |
| recall@5 | `96.67%` |
| mrr@5 | `87.50%` |
| ndcg@5 | `89.48%` |
| hit@7 | `96.67%` |
| precision@7 | `15.24%` |
| recall@7 | `96.67%` |
| mrr@7 | `87.50%` |
| ndcg@7 | `89.48%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `87.5%` | `86.5%` | `87.5%` | `87.5%` | `23815.7 ms` |
| simple | 22 | `100.0%` | `100.0%` | `90.6%` | `90.9%` | `100.0%` | `21140.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `100.0%` | `100.0%` | `91.0%` | `91.3%` | `100.0%` | `21366.2 ms` |
| medium | 7 | `85.7%` | `85.7%` | `84.6%` | `85.7%` | `85.7%` | `23456.9 ms` |
