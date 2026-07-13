# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 20:38:49
- **Total queries**: `100`
- **Avg latency**: `18689.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `89.00%` |
| Hallucination rate | `11.00%` (11) |
| Answer relevance | `96.00%` |
| Completeness | `93.00%` |
| Correctness vs gold (correct) | `60.00%` |
| Correctness vs gold (partial) | `6.00%` |
| Correctness vs gold (incorrect) | `34.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `45.00%` |
| precision@3 | `16.00%` |
| recall@3 | `44.50%` |
| mrr@3 | `41.00%` |
| ndcg@3 | `41.78%` |
| hit@5 | `51.00%` |
| precision@5 | `11.20%` |
| recall@5 | `50.50%` |
| mrr@5 | `42.30%` |
| ndcg@5 | `44.33%` |
| hit@7 | `53.00%` |
| precision@7 | `8.43%` |
| recall@7 | `53.00%` |
| mrr@7 | `42.61%` |
| ndcg@7 | `45.24%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `48.0%` | `46.0%` | `39.6%` | `76.0%` | `52.0%` | `23075.0 ms` |
| simple | 75 | `52.0%` | `52.0%` | `45.9%` | `93.3%` | `62.7%` | `17227.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `52.0%` | `52.0%` | `45.9%` | `93.3%` | `62.7%` | `17227.7 ms` |
| medium | 25 | `48.0%` | `46.0%` | `39.6%` | `76.0%` | `52.0%` | `23075.0 ms` |
