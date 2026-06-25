# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 15:43:49
- **Total queries**: `30`
- **Avg latency**: `12042.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `33.33%` |
| recall@3 | `81.67%` |
| mrr@3 | `86.11%` |
| ndcg@3 | `80.33%` |
| hit@5 | `90.00%` |
| precision@5 | `21.33%` |
| recall@5 | `85.00%` |
| mrr@5 | `86.11%` |
| ndcg@5 | `82.97%` |
| hit@7 | `90.00%` |
| precision@7 | `15.24%` |
| recall@7 | `85.00%` |
| mrr@7 | `86.11%` |
| ndcg@7 | `84.38%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `81.2%` | `79.9%` | `100.0%` | `87.5%` | `12283.1 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.1%` | `100.0%` | `86.4%` | `11955.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.1%` | `100.0%` | `86.4%` | `11955.1 ms` |
| hard | 2 | `100.0%` | `75.0%` | `89.8%` | `100.0%` | `100.0%` | `10927.3 ms` |
| medium | 6 | `100.0%` | `83.3%` | `76.6%` | `100.0%` | `83.3%` | `12735.0 ms` |
