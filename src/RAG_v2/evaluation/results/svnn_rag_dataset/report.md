# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 18:45:29
- **Total queries**: `30`
- **Avg latency**: `13088.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `32.22%` |
| recall@3 | `89.44%` |
| mrr@3 | `87.78%` |
| ndcg@3 | `86.76%` |
| hit@5 | `100.00%` |
| precision@5 | `20.67%` |
| recall@5 | `94.44%` |
| mrr@5 | `89.44%` |
| ndcg@5 | `90.37%` |
| hit@7 | `100.00%` |
| precision@7 | `14.77%` |
| recall@7 | `94.44%` |
| mrr@7 | `89.44%` |
| ndcg@7 | `90.37%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `79.2%` | `75.6%` | `100.0%` | `75.0%` | `13577.3 ms` |
| simple | 22 | `100.0%` | `100.0%` | `95.7%` | `100.0%` | `100.0%` | `12910.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `100.0%` | `100.0%` | `95.7%` | `100.0%` | `100.0%` | `12910.4 ms` |
| medium | 8 | `100.0%` | `79.2%` | `75.6%` | `100.0%` | `75.0%` | `13577.3 ms` |
