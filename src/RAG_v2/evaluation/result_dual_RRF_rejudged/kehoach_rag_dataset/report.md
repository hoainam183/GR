# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:18:12
- **Total queries**: `50`
- **Avg latency**: `32263.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `84.00%` |
| Hallucination rate | `10.00%` (5) |
| Answer relevance | `84.00%` |
| Completeness | `78.00%` |
| Correctness vs gold (correct) | `62.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `28.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `42.00%` |
| precision@3 | `15.33%` |
| recall@3 | `42.00%` |
| mrr@3 | `38.00%` |
| ndcg@3 | `39.05%` |
| hit@5 | `54.00%` |
| precision@5 | `11.60%` |
| recall@5 | `54.00%` |
| mrr@5 | `40.60%` |
| ndcg@5 | `43.87%` |
| hit@7 | `58.00%` |
| precision@7 | `8.86%` |
| recall@7 | `58.00%` |
| mrr@7 | `41.22%` |
| ndcg@7 | `45.24%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `50.0%` | `50.0%` | `39.8%` | `83.3%` | `58.3%` | `42493.7 ms` |
| simple | 38 | `55.3%` | `55.3%` | `45.1%` | `84.2%` | `63.2%` | `29032.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `55.3%` | `55.3%` | `45.1%` | `84.2%` | `63.2%` | `29032.3 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `26052.5 ms` |
| medium | 11 | `45.5%` | `45.5%` | `34.3%` | `81.8%` | `54.5%` | `43988.3 ms` |
