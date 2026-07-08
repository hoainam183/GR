# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 22:11:57
- **Total queries**: `30`
- **Avg latency**: `15516.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `76.67%` |
| precision@3 | `26.66%` |
| recall@3 | `75.00%` |
| mrr@3 | `71.11%` |
| ndcg@3 | `71.89%` |
| hit@5 | `86.67%` |
| precision@5 | `19.33%` |
| recall@5 | `86.67%` |
| mrr@5 | `73.44%` |
| ndcg@5 | `78.46%` |
| hit@7 | `86.67%` |
| precision@7 | `13.81%` |
| recall@7 | `86.67%` |
| mrr@7 | `73.44%` |
| ndcg@7 | `79.65%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `100.0%` | `88.6%` | `100.0%` | `100.0%` | `17434.8 ms` |
| simple | 22 | `81.8%` | `81.8%` | `74.8%` | `100.0%` | `90.9%` | `14819.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `81.0%` | `81.0%` | `73.6%` | `100.0%` | `90.5%` | `14354.5 ms` |
| medium | 9 | `100.0%` | `100.0%` | `89.9%` | `100.0%` | `100.0%` | `18228.2 ms` |
