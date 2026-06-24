# RAG Evaluation Report (production config)

- **Date**: 2026-06-22 22:02:20
- **Total queries**: `30`
- **Avg latency**: `11817.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `93.33%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `73.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `16.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `31.11%` |
| recall@3 | `85.00%` |
| mrr@3 | `75.00%` |
| ndcg@3 | `76.71%` |
| hit@5 | `90.00%` |
| precision@5 | `20.00%` |
| recall@5 | `88.33%` |
| mrr@5 | `75.83%` |
| ndcg@5 | `78.38%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `88.33%` |
| mrr@7 | `75.83%` |
| ndcg@7 | `78.38%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `71.6%` | `100.0%` | `62.5%` | `15052.3 ms` |
| simple | 22 | `90.9%` | `90.9%` | `80.8%` | `90.9%` | `77.3%` | `10641.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `77.3%` | `91.3%` | `73.9%` | `11219.4 ms` |
| hard | 1 | `100.0%` | `100.0%` | `50.1%` | `100.0%` | `100.0%` | `10176.9 ms` |
| medium | 6 | `100.0%` | `91.7%` | `87.1%` | `100.0%` | `66.7%` | `14384.1 ms` |
