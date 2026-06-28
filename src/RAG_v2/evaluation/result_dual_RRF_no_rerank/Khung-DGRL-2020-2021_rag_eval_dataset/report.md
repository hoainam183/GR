# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 15:22:01
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
| hit@3 | `66.67%` |
| precision@3 | `22.22%` |
| recall@3 | `56.67%` |
| mrr@3 | `46.11%` |
| ndcg@3 | `46.20%` |
| hit@5 | `70.00%` |
| precision@5 | `14.67%` |
| recall@5 | `61.67%` |
| mrr@5 | `46.78%` |
| ndcg@5 | `48.37%` |
| hit@7 | `76.67%` |
| precision@7 | `12.38%` |
| recall@7 | `70.00%` |
| mrr@7 | `47.89%` |
| ndcg@7 | `51.69%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `43.8%` | `34.1%` | `75.0%` | `87.5%` | `3963.3 ms` |
| simple | 22 | `68.2%` | `68.2%` | `53.5%` | `95.5%` | `86.4%` | `3408.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `65.0%` | `65.0%` | `50.7%` | `95.0%` | `85.0%` | `3443.6 ms` |
| hard | 1 | `100.0%` | `50.0%` | `38.7%` | `100.0%` | `100.0%` | `2985.1 ms` |
| medium | 9 | `77.8%` | `55.6%` | `44.2%` | `77.8%` | `88.9%` | `3870.4 ms` |
