# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `100`
- **Avg latency**: `28031.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `87.00%` |
| Hallucination rate | `13.00%` (13) |
| Answer relevance | `99.00%` |
| Completeness | `89.00%` |
| Correctness vs gold (correct) | `65.00%` |
| Correctness vs gold (partial) | `9.00%` |
| Correctness vs gold (incorrect) | `26.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `51.00%` |
| precision@3 | `18.00%` |
| recall@3 | `49.50%` |
| mrr@3 | `44.67%` |
| ndcg@3 | `45.29%` |
| hit@5 | `54.00%` |
| precision@5 | `11.80%` |
| recall@5 | `53.50%` |
| mrr@5 | `45.42%` |
| ndcg@5 | `47.11%` |
| hit@7 | `54.00%` |
| precision@7 | `8.57%` |
| recall@7 | `54.00%` |
| mrr@7 | `45.42%` |
| ndcg@7 | `47.33%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `48.0%` | `46.0%` | `40.3%` | `96.0%` | `56.0%` | `22545.2 ms` |
| simple | 75 | `56.0%` | `56.0%` | `49.4%` | `84.0%` | `68.0%` | `29860.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `56.0%` | `56.0%` | `49.4%` | `84.0%` | `68.0%` | `29860.2 ms` |
| medium | 25 | `48.0%` | `46.0%` | `40.3%` | `96.0%` | `56.0%` | `22545.2 ms` |
