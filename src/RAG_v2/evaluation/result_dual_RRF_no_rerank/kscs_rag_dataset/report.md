# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
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
| hit@3 | `63.33%` |
| precision@3 | `21.11%` |
| recall@3 | `63.33%` |
| mrr@3 | `49.44%` |
| ndcg@3 | `53.05%` |
| hit@5 | `70.00%` |
| precision@5 | `14.00%` |
| recall@5 | `70.00%` |
| mrr@5 | `50.94%` |
| ndcg@5 | `55.78%` |
| hit@7 | `73.33%` |
| precision@7 | `10.48%` |
| recall@7 | `73.33%` |
| mrr@7 | `51.42%` |
| ndcg@7 | `56.89%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `62.5%` | `62.5%` | `50.8%` | `87.5%` | `100.0%` | `4084.4 ms` |
| simple | 22 | `72.7%` | `72.7%` | `57.6%` | `90.9%` | `77.3%` | `3612.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `71.4%` | `71.4%` | `55.6%` | `90.5%` | `76.2%` | `3583.3 ms` |
| medium | 9 | `66.7%` | `66.7%` | `56.2%` | `88.9%` | `100.0%` | `4100.8 ms` |
