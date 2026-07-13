# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
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
| hit@3 | `50.00%` |
| precision@3 | `18.33%` |
| recall@3 | `49.50%` |
| mrr@3 | `44.33%` |
| ndcg@3 | `45.46%` |
| hit@5 | `53.00%` |
| precision@5 | `11.80%` |
| recall@5 | `53.00%` |
| mrr@5 | `45.03%` |
| ndcg@5 | `46.95%` |
| hit@7 | `53.00%` |
| precision@7 | `8.43%` |
| recall@7 | `53.00%` |
| mrr@7 | `45.03%` |
| ndcg@7 | `46.95%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `48.0%` | `48.0%` | `44.2%` | `76.0%` | `52.0%` | `23075.0 ms` |
| simple | 75 | `54.7%` | `54.7%` | `47.9%` | `93.3%` | `62.7%` | `17227.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `54.7%` | `54.7%` | `47.9%` | `93.3%` | `62.7%` | `17227.7 ms` |
| medium | 25 | `48.0%` | `48.0%` | `44.2%` | `76.0%` | `52.0%` | `23075.0 ms` |
