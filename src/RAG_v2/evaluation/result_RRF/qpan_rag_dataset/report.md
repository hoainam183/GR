# RAG Evaluation Report (production config)

- **Date**: 2026-06-24 23:21:41
- **Total queries**: `30`
- **Avg latency**: `10835.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `100.00%` |
| precision@3 | `34.44%` |
| recall@3 | `96.67%` |
| mrr@3 | `100.00%` |
| ndcg@3 | `97.15%` |
| hit@5 | `100.00%` |
| precision@5 | `21.33%` |
| recall@5 | `98.33%` |
| mrr@5 | `100.00%` |
| ndcg@5 | `98.03%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `98.33%` |
| mrr@7 | `100.00%` |
| ndcg@7 | `98.03%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `92.6%` | `100.0%` | `87.5%` | `11902.8 ms` |
| simple | 22 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `10447.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `10577.9 ms` |
| medium | 6 | `100.0%` | `91.7%` | `90.2%` | `100.0%` | `83.3%` | `11864.4 ms` |
