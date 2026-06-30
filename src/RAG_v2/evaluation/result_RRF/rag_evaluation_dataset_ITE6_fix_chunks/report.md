# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 11:34:53
- **Total queries**: `30`
- **Avg latency**: `12399.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `34.44%` |
| recall@3 | `85.00%` |
| mrr@3 | `89.44%` |
| ndcg@3 | `83.66%` |
| hit@5 | `93.33%` |
| precision@5 | `22.00%` |
| recall@5 | `88.33%` |
| mrr@5 | `89.44%` |
| ndcg@5 | `86.30%` |
| hit@7 | `93.33%` |
| precision@7 | `15.72%` |
| recall@7 | `88.33%` |
| mrr@7 | `89.44%` |
| ndcg@7 | `87.71%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `81.2%` | `79.9%` | `100.0%` | `87.5%` | `12283.1 ms` |
| simple | 22 | `90.9%` | `90.9%` | `88.6%` | `100.0%` | `90.9%` | `12441.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `90.9%` | `90.9%` | `88.6%` | `100.0%` | `90.9%` | `12441.8 ms` |
| hard | 2 | `100.0%` | `75.0%` | `89.8%` | `100.0%` | `100.0%` | `10927.3 ms` |
| medium | 6 | `100.0%` | `83.3%` | `76.6%` | `100.0%` | `83.3%` | `12735.0 ms` |
