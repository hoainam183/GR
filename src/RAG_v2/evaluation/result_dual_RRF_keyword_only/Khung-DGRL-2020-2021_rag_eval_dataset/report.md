# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 11:30:39
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
| hit@3 | `76.67%` |
| precision@3 | `26.66%` |
| recall@3 | `68.33%` |
| mrr@3 | `71.67%` |
| ndcg@3 | `66.74%` |
| hit@5 | `83.33%` |
| precision@5 | `17.33%` |
| recall@5 | `73.33%` |
| mrr@5 | `73.17%` |
| ndcg@5 | `68.96%` |
| hit@7 | `83.33%` |
| precision@7 | `12.38%` |
| recall@7 | `73.33%` |
| mrr@7 | `73.17%` |
| ndcg@7 | `68.96%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `50.0%` | `50.0%` | `100.0%` | `87.5%` | `10237.7 ms` |
| simple | 22 | `81.8%` | `81.8%` | `75.9%` | `100.0%` | `90.9%` | `8671.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `80.0%` | `80.0%` | `75.3%` | `100.0%` | `90.0%` | `8754.1 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `100.0%` | `100.0%` | `7469.4 ms` |
| medium | 9 | `88.9%` | `55.6%` | `54.8%` | `100.0%` | `88.9%` | `10013.8 ms` |
