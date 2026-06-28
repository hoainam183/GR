# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 14:08:49
- **Total queries**: `30`
- **Avg latency**: `7578.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `28.89%` |
| recall@3 | `80.00%` |
| mrr@3 | `79.44%` |
| ndcg@3 | `78.33%` |
| hit@5 | `90.00%` |
| precision@5 | `18.67%` |
| recall@5 | `86.67%` |
| mrr@5 | `81.11%` |
| ndcg@5 | `81.20%` |
| hit@7 | `90.00%` |
| precision@7 | `13.34%` |
| recall@7 | `86.67%` |
| mrr@7 | `81.11%` |
| ndcg@7 | `81.20%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `75.0%` | `100.0%` | `87.5%` | `8121.3 ms` |
| simple | 22 | `90.9%` | `90.9%` | `83.5%` | `95.5%` | `95.5%` | `7381.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `84.2%` | `95.7%` | `95.7%` | `7423.8 ms` |
| medium | 7 | `85.7%` | `71.4%` | `71.4%` | `100.0%` | `85.7%` | `8087.2 ms` |
