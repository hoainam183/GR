# RAG Evaluation Report (production config)

- **Date**: 2026-06-27 16:51:53
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
| hit@3 | `46.00%` |
| precision@3 | `16.67%` |
| recall@3 | `46.00%` |
| mrr@3 | `40.33%` |
| ndcg@3 | `41.79%` |
| hit@5 | `56.00%` |
| precision@5 | `12.00%` |
| recall@5 | `56.00%` |
| mrr@5 | `42.63%` |
| ndcg@5 | `45.92%` |
| hit@7 | `60.00%` |
| precision@7 | `9.15%` |
| recall@7 | `60.00%` |
| mrr@7 | `43.25%` |
| ndcg@7 | `47.30%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `41.7%` | `41.7%` | `37.5%` | `91.7%` | `58.3%` | `22567.1 ms` |
| simple | 38 | `60.5%` | `60.5%` | `48.6%` | `92.1%` | `68.4%` | `12239.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `60.5%` | `60.5%` | `48.6%` | `92.1%` | `68.4%` | `12239.9 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `6286.6 ms` |
| medium | 11 | `36.4%` | `36.4%` | `31.8%` | `90.9%` | `54.5%` | `24047.1 ms` |
