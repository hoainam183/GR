# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `30`
- **Avg latency**: `11275.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `96.67%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `70.00%` |
| precision@3 | `24.44%` |
| recall@3 | `70.00%` |
| mrr@3 | `65.00%` |
| ndcg@3 | `66.31%` |
| hit@5 | `76.67%` |
| precision@5 | `16.67%` |
| recall@5 | `76.67%` |
| mrr@5 | `66.67%` |
| ndcg@5 | `70.85%` |
| hit@7 | `76.67%` |
| precision@7 | `11.91%` |
| recall@7 | `76.67%` |
| mrr@7 | `66.67%` |
| ndcg@7 | `72.04%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `87.5%` | `77.4%` | `100.0%` | `87.5%` | `12562.5 ms` |
| simple | 22 | `72.7%` | `72.7%` | `68.5%` | `90.9%` | `86.4%` | `10807.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `71.4%` | `71.4%` | `67.0%` | `90.5%` | `85.7%` | `10701.4 ms` |
| medium | 9 | `88.9%` | `88.9%` | `79.9%` | `100.0%` | `88.9%` | `12616.1 ms` |
