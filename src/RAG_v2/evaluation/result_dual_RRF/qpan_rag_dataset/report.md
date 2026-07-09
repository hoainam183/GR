# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 15:26:34
- **Total queries**: `30`
- **Avg latency**: `24288.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `30.00%` |
| recall@3 | `83.33%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `83.07%` |
| hit@5 | `96.67%` |
| precision@5 | `20.67%` |
| recall@5 | `95.00%` |
| mrr@5 | `87.50%` |
| ndcg@5 | `88.25%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `98.33%` |
| mrr@7 | `88.06%` |
| ndcg@7 | `89.44%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `77.3%` | `87.5%` | `62.5%` | `25394.3 ms` |
| simple | 22 | `100.0%` | `100.0%` | `92.2%` | `100.0%` | `95.5%` | `23885.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `100.0%` | `100.0%` | `92.9%` | `100.0%` | `95.8%` | `24028.8 ms` |
| medium | 6 | `83.3%` | `75.0%` | `69.7%` | `83.3%` | `50.0%` | `25325.3 ms` |
