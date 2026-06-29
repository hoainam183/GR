# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 13:17:01
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
| hit@3 | `46.00%` |
| precision@3 | `16.33%` |
| recall@3 | `45.50%` |
| mrr@3 | `41.33%` |
| ndcg@3 | `42.35%` |
| hit@5 | `51.00%` |
| precision@5 | `10.80%` |
| recall@5 | `49.50%` |
| mrr@5 | `42.53%` |
| ndcg@5 | `44.13%` |
| hit@7 | `54.00%` |
| precision@7 | `8.43%` |
| recall@7 | `53.50%` |
| mrr@7 | `43.01%` |
| ndcg@7 | `45.60%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `44.0%` | `38.0%` | `33.1%` | `96.0%` | `56.0%` | `22545.2 ms` |
| simple | 75 | `53.3%` | `53.3%` | `47.8%` | `84.0%` | `68.0%` | `29860.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `53.3%` | `53.3%` | `47.8%` | `84.0%` | `68.0%` | `29860.2 ms` |
| medium | 25 | `44.0%` | `38.0%` | `33.1%` | `96.0%` | `56.0%` | `22545.2 ms` |
