# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 15:07:40
- **Total queries**: `30`
- **Avg latency**: `3738.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `10.00%` (3) |
| Answer relevance | `100.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `83.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `60.00%` |
| precision@3 | `20.00%` |
| recall@3 | `60.00%` |
| mrr@3 | `46.11%` |
| ndcg@3 | `49.72%` |
| hit@5 | `70.00%` |
| precision@5 | `14.00%` |
| recall@5 | `70.00%` |
| mrr@5 | `48.44%` |
| ndcg@5 | `53.88%` |
| hit@7 | `73.33%` |
| precision@7 | `10.48%` |
| recall@7 | `73.33%` |
| mrr@7 | `48.92%` |
| ndcg@7 | `54.99%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `62.5%` | `62.5%` | `43.6%` | `87.5%` | `100.0%` | `4084.4 ms` |
| simple | 22 | `72.7%` | `72.7%` | `57.6%` | `90.9%` | `77.3%` | `3612.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `71.4%` | `71.4%` | `55.6%` | `90.5%` | `76.2%` | `3583.3 ms` |
| medium | 9 | `66.7%` | `66.7%` | `49.9%` | `88.9%` | `100.0%` | `4100.8 ms` |
