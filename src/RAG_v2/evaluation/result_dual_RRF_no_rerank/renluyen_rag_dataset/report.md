# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:54
- **Total queries**: `30`
- **Avg latency**: `18783.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `3.33%` |
| Hallucination rate | `96.67%` (29) |
| Answer relevance | `96.67%` |
| Completeness | `23.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `28.89%` |
| recall@3 | `78.33%` |
| mrr@3 | `66.11%` |
| ndcg@3 | `68.85%` |
| hit@5 | `86.67%` |
| precision@5 | `18.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `67.61%` |
| ndcg@5 | `71.02%` |
| hit@7 | `90.00%` |
| precision@7 | `13.81%` |
| recall@7 | `86.67%` |
| mrr@7 | `68.17%` |
| ndcg@7 | `72.21%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `61.2%` | `0.0%` | `75.0%` | `20156.3 ms` |
| simple | 22 | `86.4%` | `86.4%` | `74.6%` | `4.5%` | `90.9%` | `18283.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `82.6%` | `82.6%` | `71.4%` | `4.3%` | `87.0%` | `18655.1 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `0.0%` | `100.0%` | `33081.7 ms` |
| medium | 6 | `100.0%` | `83.3%` | `70.0%` | `0.0%` | `83.3%` | `16890.2 ms` |
