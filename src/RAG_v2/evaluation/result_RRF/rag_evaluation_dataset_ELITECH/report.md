# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 22:11:57
- **Total queries**: `30`
- **Avg latency**: `20056.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `10.00%` (3) |
| Answer relevance | `100.00%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `63.33%` |
| precision@3 | `21.11%` |
| recall@3 | `58.33%` |
| mrr@3 | `56.11%` |
| ndcg@3 | `54.11%` |
| hit@5 | `66.67%` |
| precision@5 | `13.33%` |
| recall@5 | `60.00%` |
| mrr@5 | `56.78%` |
| ndcg@5 | `54.90%` |
| hit@7 | `66.67%` |
| precision@7 | `9.53%` |
| recall@7 | `60.00%` |
| mrr@7 | `56.78%` |
| ndcg@7 | `54.90%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `50.0%` | `25.0%` | `26.0%` | `75.0%` | `75.0%` | `22668.9 ms` |
| simple | 22 | `72.7%` | `72.7%` | `65.4%` | `86.4%` | `77.3%` | `19106.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `72.7%` | `72.7%` | `65.4%` | `86.4%` | `77.3%` | `19106.8 ms` |
| medium | 8 | `50.0%` | `25.0%` | `26.0%` | `75.0%` | `75.0%` | `22668.9 ms` |
