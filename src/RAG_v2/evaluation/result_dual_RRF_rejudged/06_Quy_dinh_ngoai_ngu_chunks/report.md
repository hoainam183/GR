# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:04:37
- **Total queries**: `30`
- **Avg latency**: `37690.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `76.67%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `86.67%` |
| Completeness | `63.33%` |
| Correctness vs gold (correct) | `70.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `20.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `20.00%` |
| recall@3 | `55.00%` |
| mrr@3 | `42.78%` |
| ndcg@3 | `45.40%` |
| hit@5 | `66.67%` |
| precision@5 | `14.67%` |
| recall@5 | `65.00%` |
| mrr@5 | `45.28%` |
| ndcg@5 | `50.03%` |
| hit@7 | `70.00%` |
| precision@7 | `10.96%` |
| recall@7 | `68.33%` |
| mrr@7 | `45.75%` |
| ndcg@7 | `51.14%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `31.2%` | `21.9%` | `50.0%` | `37.5%` | `43176.2 ms` |
| simple | 22 | `77.3%` | `77.3%` | `60.2%` | `86.4%` | `81.8%` | `35695.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `77.3%` | `77.3%` | `60.2%` | `86.4%` | `81.8%` | `35695.8 ms` |
| medium | 8 | `37.5%` | `31.2%` | `21.9%` | `50.0%` | `37.5%` | `43176.2 ms` |
