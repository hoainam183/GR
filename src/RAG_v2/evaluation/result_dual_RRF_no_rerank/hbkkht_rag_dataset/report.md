# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `30`
- **Avg latency**: `3825.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `96.67%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `60.00%` |
| precision@3 | `21.11%` |
| recall@3 | `56.67%` |
| mrr@3 | `46.67%` |
| ndcg@3 | `48.62%` |
| hit@5 | `73.33%` |
| precision@5 | `15.33%` |
| recall@5 | `68.33%` |
| mrr@5 | `50.00%` |
| ndcg@5 | `53.81%` |
| hit@7 | `76.67%` |
| precision@7 | `11.43%` |
| recall@7 | `71.67%` |
| mrr@7 | `50.56%` |
| ndcg@7 | `55.00%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `56.2%` | `49.5%` | `100.0%` | `62.5%` | `3740.5 ms` |
| simple | 22 | `72.7%` | `72.7%` | `55.4%` | `95.5%` | `86.4%` | `3857.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `69.6%` | `69.6%` | `53.0%` | `95.7%` | `87.0%` | `4009.3 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `3069.1 ms` |
| medium | 6 | `83.3%` | `58.3%` | `49.3%` | `100.0%` | `50.0%` | `3249.3 ms` |
