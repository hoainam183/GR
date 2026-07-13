# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `9089.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `28.89%` |
| recall@3 | `73.33%` |
| mrr@3 | `76.67%` |
| ndcg@3 | `71.36%` |
| hit@5 | `83.33%` |
| precision@5 | `17.33%` |
| recall@5 | `73.33%` |
| mrr@5 | `76.67%` |
| ndcg@5 | `71.36%` |
| hit@7 | `83.33%` |
| precision@7 | `12.38%` |
| recall@7 | `73.33%` |
| mrr@7 | `76.67%` |
| ndcg@7 | `71.36%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `50.0%` | `51.8%` | `100.0%` | `87.5%` | `10237.7 ms` |
| simple | 22 | `81.8%` | `81.8%` | `78.5%` | `100.0%` | `90.9%` | `8671.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `80.0%` | `80.0%` | `78.1%` | `100.0%` | `90.0%` | `8754.1 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `100.0%` | `100.0%` | `7469.4 ms` |
| medium | 9 | `88.9%` | `55.6%` | `56.5%` | `100.0%` | `88.9%` | `10013.8 ms` |
