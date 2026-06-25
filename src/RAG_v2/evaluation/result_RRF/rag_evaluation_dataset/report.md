# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 18:25:56
- **Total queries**: `100`
- **Avg latency**: `20166.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `61.00%` |
| Correctness vs gold (partial) | `5.00%` |
| Correctness vs gold (incorrect) | `34.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `53.00%` |
| precision@3 | `19.00%` |
| recall@3 | `51.50%` |
| mrr@3 | `46.67%` |
| ndcg@3 | `47.29%` |
| hit@5 | `55.00%` |
| precision@5 | `12.20%` |
| recall@5 | `54.50%` |
| mrr@5 | `47.17%` |
| ndcg@5 | `48.68%` |
| hit@7 | `55.00%` |
| precision@7 | `8.86%` |
| recall@7 | `55.00%` |
| mrr@7 | `47.17%` |
| ndcg@7 | `48.90%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 25 | `48.0%` | `46.0%` | `42.6%` | `100.0%` | `60.0%` | `14332.6 ms` |
| simple | 75 | `57.3%` | `57.3%` | `50.7%` | `100.0%` | `61.3%` | `22111.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 75 | `57.3%` | `57.3%` | `50.7%` | `100.0%` | `61.3%` | `22111.3 ms` |
| medium | 25 | `48.0%` | `46.0%` | `42.6%` | `100.0%` | `60.0%` | `14332.6 ms` |
