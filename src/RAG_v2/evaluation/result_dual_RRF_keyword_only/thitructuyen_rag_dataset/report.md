# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 11:28:10
- **Total queries**: `30`
- **Avg latency**: `28043.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `0.00%` |
| Hallucination rate | `100.00%` (30) |
| Answer relevance | `0.00%` |
| Completeness | `0.00%` |
| Correctness vs gold (correct) | `0.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `100.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `40.00%` |
| precision@3 | `13.33%` |
| recall@3 | `36.11%` |
| mrr@3 | `33.89%` |
| ndcg@3 | `33.26%` |
| hit@5 | `53.33%` |
| precision@5 | `11.33%` |
| recall@5 | `50.56%` |
| mrr@5 | `37.22%` |
| ndcg@5 | `39.61%` |
| hit@7 | `53.33%` |
| precision@7 | `8.10%` |
| recall@7 | `50.56%` |
| mrr@7 | `37.22%` |
| ndcg@7 | `39.61%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `62.5%` | `52.1%` | `32.4%` | `0.0%` | `0.0%` | `32031.5 ms` |
| simple | 22 | `50.0%` | `50.0%` | `42.2%` | `0.0%` | `0.0%` | `26593.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `50.0%` | `50.0%` | `42.2%` | `0.0%` | `0.0%` | `26593.8 ms` |
| medium | 8 | `62.5%` | `52.1%` | `32.4%` | `0.0%` | `0.0%` | `32031.5 ms` |
