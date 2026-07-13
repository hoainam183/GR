# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `30`
- **Avg latency**: `20322.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `66.67%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `96.67%` |
| Completeness | `76.67%` |
| Correctness vs gold (correct) | `70.00%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `26.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `46.67%` |
| precision@3 | `15.55%` |
| recall@3 | `43.33%` |
| mrr@3 | `30.00%` |
| ndcg@3 | `32.35%` |
| hit@5 | `56.67%` |
| precision@5 | `12.00%` |
| recall@5 | `53.33%` |
| mrr@5 | `32.50%` |
| ndcg@5 | `36.89%` |
| hit@7 | `56.67%` |
| precision@7 | `8.57%` |
| recall@7 | `53.33%` |
| mrr@7 | `32.50%` |
| ndcg@7 | `36.89%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `25.0%` | `17.8%` | `37.5%` | `25.0%` | `20586.5 ms` |
| simple | 22 | `63.6%` | `63.6%` | `43.9%` | `77.3%` | `86.4%` | `20226.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `43.9%` | `77.3%` | `86.4%` | `20226.4 ms` |
| medium | 8 | `37.5%` | `25.0%` | `17.8%` | `37.5%` | `25.0%` | `20586.5 ms` |
