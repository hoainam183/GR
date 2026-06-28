# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 14:22:10
- **Total queries**: `30`
- **Avg latency**: `8381.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `96.67%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `16.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `70.00%` |
| precision@3 | `26.66%` |
| recall@3 | `65.00%` |
| mrr@3 | `68.33%` |
| ndcg@3 | `64.57%` |
| hit@5 | `76.67%` |
| precision@5 | `18.00%` |
| recall@5 | `71.67%` |
| mrr@5 | `70.00%` |
| ndcg@5 | `69.53%` |
| hit@7 | `76.67%` |
| precision@7 | `12.86%` |
| recall@7 | `71.67%` |
| mrr@7 | `70.00%` |
| ndcg@7 | `70.94%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `68.8%` | `67.9%` | `87.5%` | `75.0%` | `9488.9 ms` |
| simple | 22 | `72.7%` | `72.7%` | `70.1%` | `100.0%` | `77.3%` | `7978.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `72.7%` | `72.7%` | `70.1%` | `100.0%` | `77.3%` | `7978.1 ms` |
| hard | 2 | `50.0%` | `50.0%` | `59.2%` | `100.0%` | `50.0%` | `9618.8 ms` |
| medium | 6 | `100.0%` | `75.0%` | `70.8%` | `83.3%` | `83.3%` | `9445.6 ms` |
