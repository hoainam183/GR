# RAG Evaluation Report (production config)

- **Date**: 2026-06-22 19:12:43
- **Total queries**: `30`
- **Avg latency**: `12688.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `86.67%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `90.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `66.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `33.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `73.33%` |
| precision@3 | `27.78%` |
| recall@3 | `70.00%` |
| mrr@3 | `71.11%` |
| ndcg@3 | `68.82%` |
| hit@5 | `76.67%` |
| precision@5 | `18.00%` |
| recall@5 | `72.22%` |
| mrr@5 | `71.94%` |
| ndcg@5 | `70.10%` |
| hit@7 | `76.67%` |
| precision@7 | `13.34%` |
| recall@7 | `73.33%` |
| mrr@7 | `71.94%` |
| ndcg@7 | `70.66%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `89.6%` | `86.5%` | `87.5%` | `87.5%` | `13931.7 ms` |
| simple | 22 | `68.2%` | `65.9%` | `64.1%` | `86.4%` | `59.1%` | `12236.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `69.6%` | `67.4%` | `65.7%` | `87.0%` | `60.9%` | `12262.8 ms` |
| medium | 7 | `100.0%` | `88.1%` | `84.5%` | `85.7%` | `85.7%` | `14087.7 ms` |
