# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 13:26:41
- **Total queries**: `100`
- **Avg latency**: `19920.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `97.00%` |
| Hallucination rate | `3.00%` (3) |
| Answer relevance | `97.00%` |
| Completeness | `97.00%` |
| Correctness vs gold (correct) | `58.00%` |
| Correctness vs gold (partial) | `5.00%` |
| Correctness vs gold (incorrect) | `37.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `17.67%` |
| recall@3 | `48.50%` |
| mrr@3 | `43.67%` |
| ndcg@3 | `44.29%` |
| hit@5 | `52.00%` |
| precision@5 | `11.40%` |
| recall@5 | `51.50%` |
| mrr@5 | `44.17%` |
| ndcg@5 | `45.68%` |
| hit@7 | `52.00%` |
| precision@7 | `8.29%` |
| recall@7 | `52.00%` |
| mrr@7 | `44.17%` |
| ndcg@7 | `45.90%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `44.0%` | `42.0%` | `38.6%` | `96.0%` | `56.0%` | `13812.2 ms` |
| simple | 75 | `54.7%` | `54.7%` | `48.0%` | `97.3%` | `58.7%` | `21956.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `54.7%` | `54.7%` | `48.0%` | `97.3%` | `58.7%` | `21956.5 ms` |
| medium | 25 | `44.0%` | `42.0%` | `38.6%` | `96.0%` | `56.0%` | `13812.2 ms` |
