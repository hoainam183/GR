# RAG Evaluation Report (production config)

- **Date**: 2026-06-24 22:21:37
- **Total queries**: `30`
- **Avg latency**: `19538.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `34.44%` |
| recall@3 | `83.33%` |
| mrr@3 | `81.67%` |
| ndcg@3 | `79.32%` |
| hit@5 | `90.00%` |
| precision@5 | `20.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `81.67%` |
| ndcg@5 | `79.32%` |
| hit@7 | `90.00%` |
| precision@7 | `14.77%` |
| recall@7 | `83.33%` |
| mrr@7 | `81.67%` |
| ndcg@7 | `79.32%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `75.0%` | `69.2%` | `100.0%` | `100.0%` | `10663.4 ms` |
| simple | 22 | `86.4%` | `86.4%` | `83.0%` | `100.0%` | `90.9%` | `22765.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `85.0%` | `85.0%` | `83.2%` | `100.0%` | `90.0%` | `23684.5 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `100.0%` | `100.0%` | `8722.2 ms` |
| medium | 9 | `100.0%` | `77.8%` | `71.9%` | `100.0%` | `100.0%` | `11526.2 ms` |
