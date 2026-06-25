# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 18:36:30
- **Total queries**: `30`
- **Avg latency**: `12019.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `76.67%` |
| precision@3 | `28.89%` |
| recall@3 | `71.67%` |
| mrr@3 | `76.67%` |
| ndcg@3 | `72.53%` |
| hit@5 | `76.67%` |
| precision@5 | `18.00%` |
| recall@5 | `73.33%` |
| mrr@5 | `76.67%` |
| ndcg@5 | `73.32%` |
| hit@7 | `76.67%` |
| precision@7 | `12.86%` |
| recall@7 | `73.33%` |
| mrr@7 | `76.67%` |
| ndcg@7 | `74.05%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `62.5%` | `62.5%` | `75.0%` | `75.0%` | `13361.3 ms` |
| simple | 22 | `77.3%` | `77.3%` | `77.3%` | `100.0%` | `81.8%` | `11531.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `77.3%` | `77.3%` | `77.3%` | `100.0%` | `81.8%` | `11531.8 ms` |
| hard | 2 | `50.0%` | `50.0%` | `50.0%` | `100.0%` | `50.0%` | `10854.0 ms` |
| medium | 6 | `83.3%` | `66.7%` | `66.6%` | `66.7%` | `83.3%` | `14197.1 ms` |
