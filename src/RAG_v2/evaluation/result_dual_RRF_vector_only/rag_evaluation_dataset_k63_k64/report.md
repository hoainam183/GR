# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 14:04:42
- **Total queries**: `30`
- **Avg latency**: `28829.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `20.00%` |
| Hallucination rate | `80.00%` (24) |
| Answer relevance | `33.33%` |
| Completeness | `23.33%` |
| Correctness vs gold (correct) | `16.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `80.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `17.78%` |
| recall@3 | `50.00%` |
| mrr@3 | `48.33%` |
| ndcg@3 | `48.77%` |
| hit@5 | `60.00%` |
| precision@5 | `12.67%` |
| recall@5 | `60.00%` |
| mrr@5 | `50.83%` |
| ndcg@5 | `53.08%` |
| hit@7 | `60.00%` |
| precision@7 | `9.05%` |
| recall@7 | `60.00%` |
| mrr@7 | `50.83%` |
| ndcg@7 | `53.08%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `12.5%` | `12.5%` | `50.0%` | `50.0%` | `26089.2 ms` |
| simple | 22 | `77.3%` | `77.3%` | `67.8%` | `9.1%` | `4.5%` | `29825.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `77.3%` | `77.3%` | `67.8%` | `9.1%` | `4.5%` | `29825.6 ms` |
| medium | 8 | `12.5%` | `12.5%` | `12.5%` | `50.0%` | `50.0%` | `26089.2 ms` |
