# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 11:36:14
- **Total queries**: `30`
- **Avg latency**: `12797.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `33.33%` |
| recall@3 | `83.33%` |
| mrr@3 | `88.33%` |
| ndcg@3 | `83.34%` |
| hit@5 | `93.33%` |
| precision@5 | `20.67%` |
| recall@5 | `86.67%` |
| mrr@5 | `89.17%` |
| ndcg@5 | `84.78%` |
| hit@7 | `93.33%` |
| precision@7 | `14.77%` |
| recall@7 | `86.67%` |
| mrr@7 | `89.17%` |
| ndcg@7 | `85.51%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `62.5%` | `67.2%` | `75.0%` | `87.5%` | `14975.1 ms` |
| simple | 22 | `95.5%` | `95.5%` | `91.2%` | `100.0%` | `90.9%` | `12005.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `95.5%` | `95.5%` | `91.2%` | `100.0%` | `90.9%` | `12005.6 ms` |
| hard | 2 | `100.0%` | `75.0%` | `80.7%` | `100.0%` | `50.0%` | `15292.5 ms` |
| medium | 6 | `83.3%` | `58.3%` | `62.6%` | `66.7%` | `100.0%` | `14869.3 ms` |
