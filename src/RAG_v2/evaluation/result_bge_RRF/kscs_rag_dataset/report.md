# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 21:11:14
- **Total queries**: `30`
- **Avg latency**: `23468.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `86.67%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `46.67%` |
| precision@3 | `16.67%` |
| recall@3 | `46.67%` |
| mrr@3 | `40.00%` |
| ndcg@3 | `41.75%` |
| hit@5 | `76.67%` |
| precision@5 | `16.00%` |
| recall@5 | `75.00%` |
| mrr@5 | `47.33%` |
| ndcg@5 | `56.54%` |
| hit@7 | `80.00%` |
| precision@7 | `12.38%` |
| recall@7 | `80.00%` |
| mrr@7 | `47.89%` |
| ndcg@7 | `59.60%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `62.5%` | `56.2%` | `58.4%` | `62.5%` | `100.0%` | `14569.5 ms` |
| simple | 22 | `81.8%` | `81.8%` | `55.9%` | `95.5%` | `95.5%` | `26704.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `81.0%` | `81.0%` | `56.5%` | `95.2%` | `95.2%` | `25951.4 ms` |
| medium | 9 | `66.7%` | `61.1%` | `56.7%` | `66.7%` | `100.0%` | `17675.3 ms` |
