# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 22:11:57
- **Total queries**: `100`
- **Avg latency**: `20413.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `78.00%` |
| Correctness vs gold (partial) | `7.00%` |
| Correctness vs gold (incorrect) | `15.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `68.00%` |
| precision@3 | `24.00%` |
| recall@3 | `66.50%` |
| mrr@3 | `59.67%` |
| ndcg@3 | `60.81%` |
| hit@5 | `71.00%` |
| precision@5 | `15.40%` |
| recall@5 | `70.50%` |
| mrr@5 | `60.37%` |
| ndcg@5 | `62.59%` |
| hit@7 | `71.00%` |
| precision@7 | `11.15%` |
| recall@7 | `71.00%` |
| mrr@7 | `60.37%` |
| ndcg@7 | `62.81%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `52.0%` | `50.0%` | `46.6%` | `100.0%` | `64.0%` | `14339.9 ms` |
| simple | 75 | `77.3%` | `77.3%` | `67.9%` | `100.0%` | `82.7%` | `22437.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `77.3%` | `77.3%` | `67.9%` | `100.0%` | `82.7%` | `22437.6 ms` |
| medium | 25 | `52.0%` | `50.0%` | `46.6%` | `100.0%` | `64.0%` | `14339.9 ms` |
