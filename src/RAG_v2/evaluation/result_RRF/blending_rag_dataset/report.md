# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 11:14:25
- **Total queries**: `30`
- **Avg latency**: `22263.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `36.66%` |
| recall@3 | `90.00%` |
| mrr@3 | `88.89%` |
| ndcg@3 | `87.15%` |
| hit@5 | `93.33%` |
| precision@5 | `22.00%` |
| recall@5 | `90.00%` |
| mrr@5 | `88.89%` |
| ndcg@5 | `87.15%` |
| hit@7 | `93.33%` |
| precision@7 | `15.72%` |
| recall@7 | `90.00%` |
| mrr@7 | `88.89%` |
| ndcg@7 | `87.15%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `94.2%` | `87.5%` | `100.0%` | `14185.9 ms` |
| simple | 22 | `90.9%` | `88.6%` | `84.6%` | `100.0%` | `90.9%` | `25200.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `89.1%` | `85.3%` | `100.0%` | `91.3%` | `24657.0 ms` |
| medium | 7 | `100.0%` | `92.9%` | `93.3%` | `85.7%` | `100.0%` | `14399.2 ms` |
