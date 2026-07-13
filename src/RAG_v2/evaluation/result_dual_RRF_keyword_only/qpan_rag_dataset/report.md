# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `38039.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `30.00%` |
| recall@3 | `85.00%` |
| mrr@3 | `86.67%` |
| ndcg@3 | `85.11%` |
| hit@5 | `86.67%` |
| precision@5 | `18.00%` |
| recall@5 | `85.00%` |
| mrr@5 | `86.67%` |
| ndcg@5 | `85.11%` |
| hit@7 | `86.67%` |
| precision@7 | `12.86%` |
| recall@7 | `85.00%` |
| mrr@7 | `86.67%` |
| ndcg@7 | `85.11%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `62.5%` | `56.2%` | `56.7%` | `87.5%` | `62.5%` | `95856.9 ms` |
| simple | 22 | `95.5%` | `95.5%` | `95.5%` | `100.0%` | `95.5%` | `17015.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `91.7%` | `91.7%` | `91.7%` | `100.0%` | `91.7%` | `42880.0 ms` |
| medium | 6 | `66.7%` | `58.3%` | `58.9%` | `83.3%` | `66.7%` | `18677.1 ms` |
