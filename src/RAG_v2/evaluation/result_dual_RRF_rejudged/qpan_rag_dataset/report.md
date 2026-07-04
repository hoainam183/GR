# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:28:44
- **Total queries**: `30`
- **Avg latency**: `24745.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `93.33%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `32.22%` |
| recall@3 | `90.00%` |
| mrr@3 | `93.33%` |
| ndcg@3 | `90.49%` |
| hit@5 | `100.00%` |
| precision@5 | `21.33%` |
| recall@5 | `98.33%` |
| mrr@5 | `95.00%` |
| ndcg@5 | `94.24%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `98.33%` |
| mrr@7 | `95.00%` |
| ndcg@7 | `94.24%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `85.5%` | `75.0%` | `75.0%` | `34952.1 ms` |
| simple | 22 | `100.0%` | `100.0%` | `97.4%` | `95.5%` | `95.5%` | `21034.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `100.0%` | `100.0%` | `97.6%` | `91.7%` | `91.7%` | `23061.2 ms` |
| medium | 6 | `100.0%` | `91.7%` | `80.7%` | `83.3%` | `83.3%` | `31482.6 ms` |
