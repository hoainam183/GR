# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `30`
- **Avg latency**: `17281.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `31.11%` |
| recall@3 | `88.33%` |
| mrr@3 | `75.55%` |
| ndcg@3 | `78.56%` |
| hit@5 | `93.33%` |
| precision@5 | `19.33%` |
| recall@5 | `90.00%` |
| mrr@5 | `76.22%` |
| ndcg@5 | `79.35%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `98.33%` |
| mrr@7 | `77.17%` |
| ndcg@7 | `82.30%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `56.8%` | `75.0%` | `75.0%` | `18970.5 ms` |
| simple | 22 | `95.5%` | `95.5%` | `87.5%` | `100.0%` | `100.0%` | `16666.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `91.7%` | `91.7%` | `82.3%` | `100.0%` | `95.8%` | `16942.7 ms` |
| medium | 6 | `100.0%` | `83.3%` | `67.4%` | `66.7%` | `83.3%` | `18633.9 ms` |
