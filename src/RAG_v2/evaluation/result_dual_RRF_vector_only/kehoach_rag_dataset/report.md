# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `50`
- **Avg latency**: `14718.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `92.00%` |
| Hallucination rate | `6.00%` (3) |
| Answer relevance | `96.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `66.00%` |
| Correctness vs gold (partial) | `12.00%` |
| Correctness vs gold (incorrect) | `22.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `58.00%` |
| precision@3 | `20.67%` |
| recall@3 | `58.00%` |
| mrr@3 | `49.67%` |
| ndcg@3 | `51.83%` |
| hit@5 | `60.00%` |
| precision@5 | `12.80%` |
| recall@5 | `60.00%` |
| mrr@5 | `50.17%` |
| ndcg@5 | `52.69%` |
| hit@7 | `60.00%` |
| precision@7 | `9.15%` |
| recall@7 | `60.00%` |
| mrr@7 | `50.17%` |
| ndcg@7 | `52.69%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `41.7%` | `41.7%` | `41.7%` | `91.7%` | `58.3%` | `22567.1 ms` |
| simple | 38 | `65.8%` | `65.8%` | `56.2%` | `92.1%` | `68.4%` | `12239.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `65.8%` | `65.8%` | `56.2%` | `92.1%` | `68.4%` | `12239.9 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `6286.6 ms` |
| medium | 11 | `36.4%` | `36.4%` | `36.4%` | `90.9%` | `54.5%` | `24047.1 ms` |
