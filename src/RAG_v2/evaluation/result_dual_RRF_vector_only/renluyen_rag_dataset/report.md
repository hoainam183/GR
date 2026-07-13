# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `30`
- **Avg latency**: `20708.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `31.11%` |
| recall@3 | `86.67%` |
| mrr@3 | `76.67%` |
| ndcg@3 | `77.79%` |
| hit@5 | `93.33%` |
| precision@5 | `19.33%` |
| recall@5 | `88.33%` |
| mrr@5 | `77.50%` |
| ndcg@5 | `78.67%` |
| hit@7 | `93.33%` |
| precision@7 | `14.29%` |
| recall@7 | `90.00%` |
| mrr@7 | `77.50%` |
| ndcg@7 | `79.35%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `68.8%` | `64.8%` | `100.0%` | `62.5%` | `27103.8 ms` |
| simple | 22 | `95.5%` | `95.5%` | `83.7%` | `100.0%` | `95.5%` | `18382.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `80.1%` | `100.0%` | `91.3%` | `19822.9 ms` |
| hard | 1 | `100.0%` | `50.0%` | `26.4%` | `100.0%` | `0.0%` | `31382.1 ms` |
| medium | 6 | `100.0%` | `83.3%` | `82.0%` | `100.0%` | `83.3%` | `22324.0 ms` |
