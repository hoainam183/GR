# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 16:39:21
- **Total queries**: `30`
- **Avg latency**: `16522.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `31.11%` |
| recall@3 | `76.67%` |
| mrr@3 | `74.44%` |
| ndcg@3 | `72.65%` |
| hit@5 | `83.33%` |
| precision@5 | `18.67%` |
| recall@5 | `76.67%` |
| mrr@5 | `74.44%` |
| ndcg@5 | `72.65%` |
| hit@7 | `83.33%` |
| precision@7 | `13.81%` |
| recall@7 | `78.33%` |
| mrr@7 | `74.44%` |
| ndcg@7 | `73.33%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `62.5%` | `56.7%` | `100.0%` | `87.5%` | `16324.3 ms` |
| simple | 22 | `81.8%` | `81.8%` | `78.5%` | `100.0%` | `86.4%` | `16595.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `80.0%` | `80.0%` | `78.1%` | `100.0%` | `85.0%` | `16561.8 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `100.0%` | `100.0%` | `18978.5 ms` |
| medium | 9 | `88.9%` | `66.7%` | `60.8%` | `100.0%` | `88.9%` | `16163.4 ms` |
