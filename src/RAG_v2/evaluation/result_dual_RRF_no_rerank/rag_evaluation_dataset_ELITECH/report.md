# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 17:37:12
- **Total queries**: `30`
- **Avg latency**: `21912.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `73.33%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `96.67%` |
| Completeness | `80.00%` |
| Correctness vs gold (correct) | `70.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `20.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `18.89%` |
| recall@3 | `50.00%` |
| mrr@3 | `46.67%` |
| ndcg@3 | `45.65%` |
| hit@5 | `60.00%` |
| precision@5 | `12.00%` |
| recall@5 | `53.33%` |
| mrr@5 | `47.50%` |
| ndcg@5 | `47.08%` |
| hit@7 | `60.00%` |
| precision@7 | `8.57%` |
| recall@7 | `53.33%` |
| mrr@7 | `47.50%` |
| ndcg@7 | `47.08%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `50.0%` | `25.0%` | `21.2%` | `62.5%` | `75.0%` | `21516.2 ms` |
| simple | 22 | `63.6%` | `63.6%` | `56.5%` | `77.3%` | `68.2%` | `22056.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `56.5%` | `77.3%` | `68.2%` | `22056.5 ms` |
| medium | 8 | `50.0%` | `25.0%` | `21.2%` | `62.5%` | `75.0%` | `21516.2 ms` |
