# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 22:11:57
- **Total queries**: `30`
- **Avg latency**: `12616.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `96.67%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `32.22%` |
| recall@3 | `81.67%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `81.30%` |
| hit@5 | `90.00%` |
| precision@5 | `20.00%` |
| recall@5 | `85.00%` |
| mrr@5 | `85.83%` |
| ndcg@5 | `82.74%` |
| hit@7 | `93.33%` |
| precision@7 | `14.77%` |
| recall@7 | `86.67%` |
| mrr@7 | `86.39%` |
| ndcg@7 | `84.19%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `56.2%` | `59.5%` | `87.5%` | `75.0%` | `14295.2 ms` |
| simple | 22 | `95.5%` | `95.5%` | `91.2%` | `100.0%` | `90.9%` | `12005.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `95.5%` | `95.5%` | `91.2%` | `100.0%` | `90.9%` | `12005.6 ms` |
| hard | 2 | `100.0%` | `75.0%` | `80.7%` | `100.0%` | `50.0%` | `15292.5 ms` |
| medium | 6 | `66.7%` | `50.0%` | `52.4%` | `83.3%` | `83.3%` | `13962.8 ms` |
