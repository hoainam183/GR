# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 12:37:13
- **Total queries**: `30`
- **Avg latency**: `20245.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `32.22%` |
| recall@3 | `91.67%` |
| mrr@3 | `93.33%` |
| ndcg@3 | `91.78%` |
| hit@5 | `96.67%` |
| precision@5 | `20.67%` |
| recall@5 | `95.00%` |
| mrr@5 | `94.17%` |
| ndcg@5 | `93.54%` |
| hit@7 | `96.67%` |
| precision@7 | `14.77%` |
| recall@7 | `95.00%` |
| mrr@7 | `94.17%` |
| ndcg@7 | `93.54%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `88.3%` | `100.0%` | `75.0%` | `25419.4 ms` |
| simple | 22 | `95.5%` | `95.5%` | `95.5%` | `100.0%` | `90.9%` | `18363.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `95.8%` | `95.8%` | `95.8%` | `100.0%` | `91.7%` | `18722.1 ms` |
| medium | 6 | `100.0%` | `91.7%` | `84.4%` | `100.0%` | `66.7%` | `26336.5 ms` |
