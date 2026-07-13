# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `8839.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `6.67%` |
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
| precision@5 | `18.67%` |
| recall@5 | `85.00%` |
| mrr@5 | `73.44%` |
| ndcg@5 | `77.82%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `90.00%` |
| mrr@7 | `73.92%` |
| ndcg@7 | `80.84%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `86.2%` | `100.0%` | `87.5%` | `10419.9 ms` |
| simple | 22 | `81.8%` | `81.8%` | `74.8%` | `90.9%` | `86.4%` | `8265.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `81.0%` | `81.0%` | `73.6%` | `90.5%` | `85.7%` | `8133.4 ms` |
| medium | 9 | `100.0%` | `94.4%` | `87.7%` | `100.0%` | `88.9%` | `10488.3 ms` |
