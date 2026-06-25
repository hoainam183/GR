# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 18:39:03
- **Total queries**: `30`
- **Avg latency**: `11782.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `83.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `31.11%` |
| recall@3 | `85.00%` |
| mrr@3 | `76.67%` |
| ndcg@3 | `77.94%` |
| hit@5 | `90.00%` |
| precision@5 | `20.00%` |
| recall@5 | `88.33%` |
| mrr@5 | `77.50%` |
| ndcg@5 | `79.61%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `88.33%` |
| mrr@7 | `77.50%` |
| ndcg@7 | `79.61%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `71.6%` | `100.0%` | `75.0%` | `15230.7 ms` |
| simple | 22 | `90.9%` | `90.9%` | `82.5%` | `100.0%` | `86.4%` | `10528.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `78.9%` | `100.0%` | `82.6%` | `11111.4 ms` |
| hard | 1 | `100.0%` | `100.0%` | `50.1%` | `100.0%` | `100.0%` | `10176.9 ms` |
| medium | 6 | `100.0%` | `91.7%` | `87.1%` | `100.0%` | `83.3%` | `14621.8 ms` |
