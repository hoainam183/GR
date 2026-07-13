# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `30`
- **Avg latency**: `4240.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `28.89%` |
| recall@3 | `81.67%` |
| mrr@3 | `76.11%` |
| ndcg@3 | `74.98%` |
| hit@5 | `86.67%` |
| precision@5 | `18.00%` |
| recall@5 | `83.33%` |
| mrr@5 | `76.11%` |
| ndcg@5 | `75.86%` |
| hit@7 | `86.67%` |
| precision@7 | `12.86%` |
| recall@7 | `83.33%` |
| mrr@7 | `76.11%` |
| ndcg@7 | `75.86%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `76.3%` | `87.5%` | `62.5%` | `3918.8 ms` |
| simple | 22 | `86.4%` | `86.4%` | `75.7%` | `90.9%` | `86.4%` | `4357.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `76.8%` | `91.3%` | `87.0%` | `4349.9 ms` |
| medium | 7 | `85.7%` | `71.4%` | `72.9%` | `85.7%` | `57.1%` | `3881.6 ms` |
