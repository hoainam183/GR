# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `30`
- **Avg latency**: `10844.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `83.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `32.22%` |
| recall@3 | `80.00%` |
| mrr@3 | `86.11%` |
| ndcg@3 | `79.31%` |
| hit@5 | `90.00%` |
| precision@5 | `20.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `86.11%` |
| ndcg@5 | `82.56%` |
| hit@7 | `90.00%` |
| precision@7 | `14.77%` |
| recall@7 | `83.33%` |
| mrr@7 | `86.11%` |
| ndcg@7 | `84.65%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `75.0%` | `78.3%` | `87.5%` | `75.0%` | `10093.5 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.1%` | `100.0%` | `86.4%` | `11117.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.1%` | `100.0%` | `86.4%` | `11117.7 ms` |
| hard | 2 | `100.0%` | `75.0%` | `88.5%` | `100.0%` | `100.0%` | `11120.0 ms` |
| medium | 6 | `100.0%` | `75.0%` | `75.0%` | `83.3%` | `66.7%` | `9751.3 ms` |
