# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 18:30:22
- **Total queries**: `30`
- **Avg latency**: `17627.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `80.00%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `100.00%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `26.66%` |
| recall@3 | `76.67%` |
| mrr@3 | `59.44%` |
| ndcg@3 | `62.79%` |
| hit@5 | `86.67%` |
| precision@5 | `18.00%` |
| recall@5 | `85.00%` |
| mrr@5 | `60.94%` |
| ndcg@5 | `66.39%` |
| hit@7 | `86.67%` |
| precision@7 | `12.86%` |
| recall@7 | `85.00%` |
| mrr@7 | `60.94%` |
| ndcg@7 | `66.39%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `58.6%` | `62.5%` | `87.5%` | `24695.8 ms` |
| simple | 22 | `90.9%` | `90.9%` | `69.2%` | `86.4%` | `100.0%` | `15057.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `90.9%` | `90.9%` | `69.2%` | `86.4%` | `100.0%` | `15057.8 ms` |
| medium | 8 | `75.0%` | `68.8%` | `58.6%` | `62.5%` | `87.5%` | `24695.8 ms` |
