# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 15:31:08
- **Total queries**: `100`
- **Avg latency**: `29427.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.00%` |
| Hallucination rate | `4.00%` (4) |
| Answer relevance | `100.00%` |
| Completeness | `97.00%` |
| Correctness vs gold (correct) | `77.00%` |
| Correctness vs gold (partial) | `6.00%` |
| Correctness vs gold (incorrect) | `17.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `66.00%` |
| precision@3 | `23.00%` |
| recall@3 | `64.50%` |
| mrr@3 | `57.50%` |
| ndcg@3 | `58.68%` |
| hit@5 | `70.00%` |
| precision@5 | `15.00%` |
| recall@5 | `69.00%` |
| mrr@5 | `58.45%` |
| ndcg@5 | `60.72%` |
| hit@7 | `70.00%` |
| precision@7 | `11.00%` |
| recall@7 | `70.00%` |
| mrr@7 | `58.45%` |
| ndcg@7 | `61.16%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `52.0%` | `48.0%` | `41.3%` | `96.0%` | `68.0%` | `21819.4 ms` |
| simple | 75 | `76.0%` | `76.0%` | `67.2%` | `96.0%` | `80.0%` | `31963.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `76.0%` | `76.0%` | `67.2%` | `96.0%` | `80.0%` | `31963.5 ms` |
| medium | 25 | `52.0%` | `48.0%` | `41.3%` | `96.0%` | `68.0%` | `21819.4 ms` |
