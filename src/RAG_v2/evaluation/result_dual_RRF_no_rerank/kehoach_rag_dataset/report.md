# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `50`
- **Avg latency**: `19847.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `8.00%` (4) |
| Answer relevance | `100.00%` |
| Completeness | `88.00%` |
| Correctness vs gold (correct) | `64.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `26.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `46.00%` |
| precision@3 | `15.33%` |
| recall@3 | `44.00%` |
| mrr@3 | `36.00%` |
| ndcg@3 | `37.02%` |
| hit@5 | `52.00%` |
| precision@5 | `11.20%` |
| recall@5 | `52.00%` |
| mrr@5 | `37.20%` |
| ndcg@5 | `40.40%` |
| hit@7 | `56.00%` |
| precision@7 | `8.57%` |
| recall@7 | `56.00%` |
| mrr@7 | `37.87%` |
| ndcg@7 | `41.83%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `50.0%` | `50.0%` | `34.7%` | `91.7%` | `50.0%` | `25866.1 ms` |
| simple | 38 | `52.6%` | `52.6%` | `42.2%` | `89.5%` | `68.4%` | `17946.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `52.6%` | `52.6%` | `42.2%` | `89.5%` | `68.4%` | `17946.4 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `12745.9 ms` |
| medium | 11 | `45.5%` | `45.5%` | `28.7%` | `90.9%` | `45.5%` | `27058.8 ms` |
