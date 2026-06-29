# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 18:19:07
- **Total queries**: `30`
- **Avg latency**: `18783.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `0.00%` |
| Hallucination rate | `100.00%` (30) |
| Answer relevance | `0.00%` |
| Completeness | `0.00%` |
| Correctness vs gold (correct) | `0.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `100.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `76.67%` |
| precision@3 | `27.78%` |
| recall@3 | `75.00%` |
| mrr@3 | `64.44%` |
| ndcg@3 | `66.75%` |
| hit@5 | `86.67%` |
| precision@5 | `18.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `66.61%` |
| ndcg@5 | `70.20%` |
| hit@7 | `86.67%` |
| precision@7 | `13.34%` |
| recall@7 | `83.33%` |
| mrr@7 | `66.61%` |
| ndcg@7 | `70.20%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `61.2%` | `0.0%` | `0.0%` | `20156.3 ms` |
| simple | 22 | `86.4%` | `86.4%` | `73.5%` | `0.0%` | `0.0%` | `18283.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `82.6%` | `82.6%` | `70.3%` | `0.0%` | `0.0%` | `18655.1 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `0.0%` | `0.0%` | `33081.7 ms` |
| medium | 6 | `100.0%` | `83.3%` | `70.0%` | `0.0%` | `0.0%` | `16890.2 ms` |
