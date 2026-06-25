# RAG Evaluation Report (production config)

- **Date**: 2026-06-24 21:20:07
- **Total queries**: `30`
- **Avg latency**: `28332.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `34.44%` |
| recall@3 | `83.33%` |
| mrr@3 | `84.44%` |
| ndcg@3 | `82.15%` |
| hit@5 | `86.67%` |
| precision@5 | `20.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `84.44%` |
| ndcg@5 | `82.15%` |
| hit@7 | `86.67%` |
| precision@7 | `14.77%` |
| recall@7 | `83.33%` |
| mrr@7 | `84.44%` |
| ndcg@7 | `82.15%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `94.2%` | `87.5%` | `100.0%` | `14185.9 ms` |
| simple | 22 | `81.8%` | `79.5%` | `77.8%` | `100.0%` | `81.8%` | `33477.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `82.6%` | `80.4%` | `78.8%` | `100.0%` | `82.6%` | `32573.4 ms` |
| medium | 7 | `100.0%` | `92.9%` | `93.3%` | `85.7%` | `100.0%` | `14399.2 ms` |
