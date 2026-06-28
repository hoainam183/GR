# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 15:32:58
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
| hit@3 | `56.67%` |
| precision@3 | `20.00%` |
| recall@3 | `53.33%` |
| mrr@3 | `45.56%` |
| ndcg@3 | `46.95%` |
| hit@5 | `70.00%` |
| precision@5 | `14.67%` |
| recall@5 | `65.00%` |
| mrr@5 | `48.89%` |
| ndcg@5 | `52.14%` |
| hit@7 | `76.67%` |
| precision@7 | `11.43%` |
| recall@7 | `71.67%` |
| mrr@7 | `50.00%` |
| ndcg@7 | `54.52%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `56.2%` | `49.5%` | `100.0%` | `62.5%` | `3740.5 ms` |
| simple | 22 | `68.2%` | `68.2%` | `53.1%` | `95.5%` | `86.4%` | `3857.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `65.2%` | `65.2%` | `50.8%` | `95.7%` | `87.0%` | `4009.3 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `3069.1 ms` |
| medium | 6 | `83.3%` | `58.3%` | `49.3%` | `100.0%` | `50.0%` | `3249.3 ms` |
