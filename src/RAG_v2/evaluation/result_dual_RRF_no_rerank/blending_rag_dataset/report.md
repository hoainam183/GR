# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `30`
- **Avg latency**: `22188.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `10.00%` (3) |
| Answer relevance | `83.33%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `31.11%` |
| recall@3 | `77.22%` |
| mrr@3 | `78.33%` |
| ndcg@3 | `76.70%` |
| hit@5 | `83.33%` |
| precision@5 | `19.33%` |
| recall@5 | `80.56%` |
| mrr@5 | `79.17%` |
| ndcg@5 | `78.13%` |
| hit@7 | `83.33%` |
| precision@7 | `13.81%` |
| recall@7 | `80.56%` |
| mrr@7 | `79.17%` |
| ndcg@7 | `78.13%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `89.6%` | `80.5%` | `75.0%` | `75.0%` | `28118.4 ms` |
| simple | 22 | `77.3%` | `77.3%` | `77.3%` | `95.5%` | `81.8%` | `20032.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `78.3%` | `78.3%` | `78.3%` | `95.7%` | `82.6%` | `20114.7 ms` |
| medium | 7 | `100.0%` | `88.1%` | `77.7%` | `71.4%` | `71.4%` | `29003.8 ms` |
