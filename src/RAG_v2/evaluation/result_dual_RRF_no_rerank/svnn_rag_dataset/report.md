# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:54
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
| hit@5 | `90.00%` |
| precision@5 | `18.67%` |
| recall@5 | `88.33%` |
| mrr@5 | `61.61%` |
| ndcg@5 | `67.68%` |
| hit@7 | `90.00%` |
| precision@7 | `13.34%` |
| recall@7 | `88.33%` |
| mrr@7 | `61.61%` |
| ndcg@7 | `67.68%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `58.6%` | `62.5%` | `87.5%` | `24695.8 ms` |
| simple | 22 | `95.5%` | `95.5%` | `71.0%` | `86.4%` | `100.0%` | `15057.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `95.5%` | `95.5%` | `71.0%` | `86.4%` | `100.0%` | `15057.8 ms` |
| medium | 8 | `75.0%` | `68.8%` | `58.6%` | `62.5%` | `87.5%` | `24695.8 ms` |
