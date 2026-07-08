# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 22:11:57
- **Total queries**: `30`
- **Avg latency**: `11039.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `33.33%` |
| recall@3 | `88.33%` |
| mrr@3 | `88.33%` |
| ndcg@3 | `86.94%` |
| hit@5 | `93.33%` |
| precision@5 | `20.67%` |
| recall@5 | `91.67%` |
| mrr@5 | `89.00%` |
| ndcg@5 | `88.23%` |
| hit@7 | `93.33%` |
| precision@7 | `14.77%` |
| recall@7 | `91.67%` |
| mrr@7 | `89.00%` |
| ndcg@7 | `88.23%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `80.7%` | `100.0%` | `75.0%` | `12422.4 ms` |
| simple | 22 | `95.5%` | `95.5%` | `91.0%` | `95.5%` | `95.5%` | `10536.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `87.0%` | `95.7%` | `91.3%` | `10471.8 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `19120.8 ms` |
| medium | 6 | `100.0%` | `91.7%` | `90.9%` | `100.0%` | `83.3%` | `11868.4 ms` |
