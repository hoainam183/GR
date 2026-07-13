# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `30`
- **Avg latency**: `3556.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `70.00%` |
| precision@3 | `23.33%` |
| recall@3 | `58.33%` |
| mrr@3 | `47.22%` |
| ndcg@3 | `47.22%` |
| hit@5 | `73.33%` |
| precision@5 | `15.33%` |
| recall@5 | `63.33%` |
| mrr@5 | `47.89%` |
| ndcg@5 | `49.39%` |
| hit@7 | `76.67%` |
| precision@7 | `12.38%` |
| recall@7 | `70.00%` |
| mrr@7 | `48.44%` |
| ndcg@7 | `51.99%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `50.0%` | `38.0%` | `75.0%` | `87.5%` | `3963.3 ms` |
| simple | 22 | `68.2%` | `68.2%` | `53.5%` | `95.5%` | `86.4%` | `3408.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `65.0%` | `65.0%` | `50.7%` | `95.0%` | `85.0%` | `3443.6 ms` |
| hard | 1 | `100.0%` | `50.0%` | `38.7%` | `100.0%` | `100.0%` | `2985.1 ms` |
| medium | 9 | `88.9%` | `61.1%` | `47.6%` | `77.8%` | `88.9%` | `3870.4 ms` |
