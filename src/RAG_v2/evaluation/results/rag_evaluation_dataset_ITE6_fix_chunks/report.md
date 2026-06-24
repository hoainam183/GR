# RAG Evaluation Report (production config)

- **Date**: 2026-06-22 21:21:51
- **Total queries**: `30`
- **Avg latency**: `11205.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `86.67%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `90.00%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `16.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `30.00%` |
| recall@3 | `76.67%` |
| mrr@3 | `80.00%` |
| ndcg@3 | `75.92%` |
| hit@5 | `83.33%` |
| precision@5 | `18.00%` |
| recall@5 | `76.67%` |
| mrr@5 | `80.00%` |
| ndcg@5 | `75.92%` |
| hit@7 | `83.33%` |
| precision@7 | `12.86%` |
| recall@7 | `76.67%` |
| mrr@7 | `80.00%` |
| ndcg@7 | `76.60%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `50.0%` | `51.8%` | `87.5%` | `50.0%` | `10674.6 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.7%` | `86.4%` | `86.4%` | `11397.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.7%` | `86.4%` | `86.4%` | `11397.8 ms` |
| hard | 2 | `0.0%` | `0.0%` | `0.0%` | `50.0%` | `0.0%` | `7246.1 ms` |
| medium | 6 | `100.0%` | `66.7%` | `69.1%` | `100.0%` | `66.7%` | `11817.5 ms` |
