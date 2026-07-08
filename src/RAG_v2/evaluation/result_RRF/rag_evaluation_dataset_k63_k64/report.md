# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 22:11:57
- **Total queries**: `30`
- **Avg latency**: `18413.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `76.67%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `100.00%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `20.00%` |
| recall@3 | `56.67%` |
| mrr@3 | `53.33%` |
| ndcg@3 | `54.21%` |
| hit@5 | `60.00%` |
| precision@5 | `12.67%` |
| recall@5 | `60.00%` |
| mrr@5 | `54.17%` |
| ndcg@5 | `55.64%` |
| hit@7 | `60.00%` |
| precision@7 | `9.05%` |
| recall@7 | `60.00%` |
| mrr@7 | `54.17%` |
| ndcg@7 | `55.64%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `12.5%` | `12.5%` | `75.0%` | `75.0%` | `22648.7 ms` |
| simple | 22 | `77.3%` | `77.3%` | `71.3%` | `77.3%` | `77.3%` | `16872.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `77.3%` | `77.3%` | `71.3%` | `77.3%` | `77.3%` | `16872.7 ms` |
| medium | 8 | `12.5%` | `12.5%` | `12.5%` | `75.0%` | `75.0%` | `22648.7 ms` |
