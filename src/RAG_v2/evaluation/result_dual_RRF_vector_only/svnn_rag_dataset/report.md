# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `30`
- **Avg latency**: `19414.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `27.78%` |
| recall@3 | `78.33%` |
| mrr@3 | `76.67%` |
| ndcg@3 | `76.25%` |
| hit@5 | `83.33%` |
| precision@5 | `17.33%` |
| recall@5 | `81.67%` |
| mrr@5 | `77.33%` |
| ndcg@5 | `78.83%` |
| hit@7 | `90.00%` |
| precision@7 | `13.34%` |
| recall@7 | `88.33%` |
| mrr@7 | `78.29%` |
| ndcg@7 | `81.05%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `70.4%` | `100.0%` | `75.0%` | `22551.5 ms` |
| simple | 22 | `86.4%` | `86.4%` | `81.9%` | `95.5%` | `95.5%` | `18274.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `81.9%` | `95.5%` | `95.5%` | `18274.2 ms` |
| medium | 8 | `75.0%` | `68.8%` | `70.4%` | `100.0%` | `75.0%` | `22551.5 ms` |
