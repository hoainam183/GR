# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 12:27:48
- **Total queries**: `30`
- **Avg latency**: `15288.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `36.66%` |
| recall@3 | `90.00%` |
| mrr@3 | `91.11%` |
| ndcg@3 | `88.82%` |
| hit@5 | `93.33%` |
| precision@5 | `22.00%` |
| recall@5 | `90.00%` |
| mrr@5 | `91.11%` |
| ndcg@5 | `88.82%` |
| hit@7 | `93.33%` |
| precision@7 | `15.72%` |
| recall@7 | `90.00%` |
| mrr@7 | `91.11%` |
| ndcg@7 | `88.82%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `94.2%` | `87.5%` | `100.0%` | `14650.7 ms` |
| simple | 22 | `90.9%` | `88.6%` | `86.9%` | `100.0%` | `95.5%` | `15519.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `89.1%` | `87.5%` | `100.0%` | `95.7%` | `15403.4 ms` |
| medium | 7 | `100.0%` | `92.9%` | `93.3%` | `85.7%` | `100.0%` | `14909.5 ms` |
