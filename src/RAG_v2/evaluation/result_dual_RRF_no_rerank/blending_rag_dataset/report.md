# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 16:39:46
- **Total queries**: `30`
- **Avg latency**: `22188.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `10.00%` (3) |
| Answer relevance | `83.33%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `53.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `46.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `76.67%` |
| precision@3 | `30.00%` |
| recall@3 | `73.89%` |
| mrr@3 | `75.00%` |
| ndcg@3 | `73.36%` |
| hit@5 | `80.00%` |
| precision@5 | `18.67%` |
| recall@5 | `77.22%` |
| mrr@5 | `75.83%` |
| ndcg@5 | `74.80%` |
| hit@7 | `83.33%` |
| precision@7 | `13.81%` |
| recall@7 | `80.56%` |
| mrr@7 | `76.31%` |
| ndcg@7 | `75.91%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `77.1%` | `75.1%` | `75.0%` | `37.5%` | `28118.5 ms` |
| simple | 22 | `77.3%` | `77.3%` | `74.7%` | `95.5%` | `59.1%` | `20032.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `78.3%` | `78.3%` | `75.8%` | `95.7%` | `60.9%` | `20114.7 ms` |
| medium | 7 | `85.7%` | `73.8%` | `71.6%` | `71.4%` | `28.6%` | `29003.8 ms` |
