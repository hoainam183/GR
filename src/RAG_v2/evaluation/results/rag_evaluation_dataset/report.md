# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 21:57:25
- **Total queries**: `100`
- **Avg latency**: `31210.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `99.00%` |
| Hallucination rate | `1.00%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `99.00%` |
| Correctness vs gold (correct) | `50.00%` |
| Correctness vs gold (partial) | `5.00%` |
| Correctness vs gold (incorrect) | `45.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `40.00%` |
| precision@3 | `14.33%` |
| recall@3 | `38.50%` |
| mrr@3 | `35.00%` |
| ndcg@3 | `35.27%` |
| hit@5 | `43.00%` |
| precision@5 | `9.60%` |
| recall@5 | `42.00%` |
| mrr@5 | `35.75%` |
| ndcg@5 | `36.92%` |
| hit@7 | `43.00%` |
| precision@7 | `7.14%` |
| recall@7 | `43.00%` |
| mrr@7 | `35.75%` |
| ndcg@7 | `37.36%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `48.0%` | `44.0%` | `37.3%` | `100.0%` | `64.0%` | `23075.7 ms` |
| simple | 75 | `41.3%` | `41.3%` | `36.8%` | `98.7%` | `45.3%` | `33921.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `41.3%` | `41.3%` | `36.8%` | `98.7%` | `45.3%` | `33921.6 ms` |
| medium | 25 | `48.0%` | `44.0%` | `37.3%` | `100.0%` | `64.0%` | `23075.7 ms` |
