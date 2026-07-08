# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 23:53:08
- **Total queries**: `30`
- **Avg latency**: `18522.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `76.67%` |
| precision@3 | `25.55%` |
| recall@3 | `73.33%` |
| mrr@3 | `75.00%` |
| ndcg@3 | `72.86%` |
| hit@5 | `93.33%` |
| precision@5 | `19.33%` |
| recall@5 | `90.00%` |
| mrr@5 | `79.17%` |
| ndcg@5 | `81.71%` |
| hit@7 | `96.67%` |
| precision@7 | `14.77%` |
| recall@7 | `95.00%` |
| mrr@7 | `79.72%` |
| ndcg@7 | `84.30%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `62.5%` | `59.1%` | `75.0%` | `62.5%` | `17462.1 ms` |
| simple | 22 | `100.0%` | `100.0%` | `89.9%` | `100.0%` | `100.0%` | `18907.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `95.8%` | `95.8%` | `86.6%` | `95.8%` | `100.0%` | `19008.2 ms` |
| medium | 6 | `83.3%` | `66.7%` | `62.1%` | `83.3%` | `50.0%` | `16578.0 ms` |
