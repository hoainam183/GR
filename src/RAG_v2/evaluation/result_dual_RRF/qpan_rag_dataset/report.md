# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 14:48:35
- **Total queries**: `30`
- **Avg latency**: `24144.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `30.00%` |
| recall@3 | `85.00%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `83.88%` |
| hit@5 | `100.00%` |
| precision@5 | `21.33%` |
| recall@5 | `98.33%` |
| mrr@5 | `88.33%` |
| ndcg@5 | `89.95%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `98.33%` |
| mrr@7 | `88.33%` |
| ndcg@7 | `89.95%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `83.7%` | `100.0%` | `87.5%` | `24856.0 ms` |
| simple | 22 | `100.0%` | `100.0%` | `92.2%` | `100.0%` | `95.5%` | `23885.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `100.0%` | `100.0%` | `92.9%` | `100.0%` | `95.8%` | `24028.8 ms` |
| medium | 6 | `100.0%` | `91.7%` | `78.2%` | `100.0%` | `83.3%` | `24607.6 ms` |
