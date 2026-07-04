# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:09:45
- **Total queries**: `30`
- **Avg latency**: `24833.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `96.67%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `32.22%` |
| recall@3 | `86.67%` |
| mrr@3 | `81.11%` |
| ndcg@3 | `82.00%` |
| hit@5 | `90.00%` |
| precision@5 | `20.00%` |
| recall@5 | `88.33%` |
| mrr@5 | `81.94%` |
| ndcg@5 | `82.88%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `88.33%` |
| mrr@7 | `81.94%` |
| ndcg@7 | `82.88%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `70.0%` | `100.0%` | `100.0%` | `33211.4 ms` |
| simple | 22 | `90.9%` | `90.9%` | `87.5%` | `95.5%` | `90.9%` | `21786.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `83.8%` | `95.7%` | `91.3%` | `24929.7 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `30297.1 ms` |
| medium | 6 | `100.0%` | `91.7%` | `76.7%` | `100.0%` | `100.0%` | `23551.4 ms` |
