# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 17:40:22
- **Total queries**: `30`
- **Avg latency**: `11386.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `31.11%` |
| recall@3 | `86.11%` |
| mrr@3 | `84.44%` |
| ndcg@3 | `83.43%` |
| hit@5 | `96.67%` |
| precision@5 | `20.00%` |
| recall@5 | `91.11%` |
| mrr@5 | `86.11%` |
| ndcg@5 | `87.04%` |
| hit@7 | `100.00%` |
| precision@7 | `14.77%` |
| recall@7 | `94.44%` |
| mrr@7 | `86.67%` |
| ndcg@7 | `88.22%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `79.2%` | `75.6%` | `100.0%` | `75.0%` | `11811.2 ms` |
| simple | 22 | `95.5%` | `95.5%` | `91.2%` | `100.0%` | `100.0%` | `11231.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `95.5%` | `95.5%` | `91.2%` | `100.0%` | `100.0%` | `11231.6 ms` |
| medium | 8 | `100.0%` | `79.2%` | `75.6%` | `100.0%` | `75.0%` | `11811.2 ms` |
