# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 07:54:52
- **Total queries**: `30`
- **Avg latency**: `48357.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `96.67%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `32.22%` |
| recall@3 | `86.67%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `85.17%` |
| hit@5 | `90.00%` |
| precision@5 | `20.00%` |
| recall@5 | `88.33%` |
| mrr@5 | `85.83%` |
| ndcg@5 | `86.05%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `88.33%` |
| mrr@7 | `85.83%` |
| ndcg@7 | `86.05%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `77.3%` | `100.0%` | `87.5%` | `143446.8 ms` |
| simple | 22 | `90.9%` | `90.9%` | `89.2%` | `95.5%` | `90.9%` | `13780.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `85.4%` | `95.7%` | `91.3%` | `16630.5 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `84719.0 ms` |
| medium | 6 | `100.0%` | `91.7%` | `86.4%` | `100.0%` | `83.3%` | `163918.9 ms` |
