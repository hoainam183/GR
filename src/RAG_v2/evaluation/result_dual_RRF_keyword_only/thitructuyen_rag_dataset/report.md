# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `28043.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `30.00%` |
| Hallucination rate | `70.00%` (21) |
| Answer relevance | `100.00%` |
| Completeness | `76.67%` |
| Correctness vs gold (correct) | `56.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `36.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `53.33%` |
| precision@3 | `18.89%` |
| recall@3 | `50.56%` |
| mrr@3 | `51.67%` |
| ndcg@3 | `49.83%` |
| hit@5 | `53.33%` |
| precision@5 | `11.33%` |
| recall@5 | `50.56%` |
| mrr@5 | `51.67%` |
| ndcg@5 | `49.83%` |
| hit@7 | `53.33%` |
| precision@7 | `8.57%` |
| recall@7 | `51.67%` |
| mrr@7 | `51.67%` |
| ndcg@7 | `50.38%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `62.5%` | `52.1%` | `49.4%` | `25.0%` | `62.5%` | `32031.5 ms` |
| simple | 22 | `50.0%` | `50.0%` | `50.0%` | `31.8%` | `54.5%` | `26593.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `50.0%` | `50.0%` | `50.0%` | `31.8%` | `54.5%` | `26593.8 ms` |
| medium | 8 | `62.5%` | `52.1%` | `49.4%` | `25.0%` | `62.5%` | `32031.5 ms` |
