# RAG Evaluation Report (production config)

- **Date**: 2026-07-04 18:32:54
- **Total queries**: `100`
- **Avg latency**: `28367.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `99.00%` |
| Hallucination rate | `1.00%` (1) |
| Answer relevance | `99.00%` |
| Completeness | `98.00%` |
| Correctness vs gold (correct) | `79.00%` |
| Correctness vs gold (partial) | `7.00%` |
| Correctness vs gold (incorrect) | `14.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `64.00%` |
| precision@3 | `22.33%` |
| recall@3 | `64.00%` |
| mrr@3 | `56.83%` |
| ndcg@3 | `58.70%` |
| hit@5 | `75.00%` |
| precision@5 | `15.80%` |
| recall@5 | `73.50%` |
| mrr@5 | `59.28%` |
| ndcg@5 | `62.76%` |
| hit@7 | `78.00%` |
| precision@7 | `12.00%` |
| recall@7 | `77.00%` |
| mrr@7 | `59.78%` |
| ndcg@7 | `64.10%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `56.0%` | `50.0%` | `41.1%` | `100.0%` | `68.0%` | `36845.3 ms` |
| simple | 75 | `81.3%` | `81.3%` | `70.0%` | `98.7%` | `82.7%` | `25541.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `81.3%` | `81.3%` | `70.0%` | `98.7%` | `82.7%` | `25541.3 ms` |
| medium | 25 | `56.0%` | `50.0%` | `41.1%` | `100.0%` | `68.0%` | `36845.3 ms` |
