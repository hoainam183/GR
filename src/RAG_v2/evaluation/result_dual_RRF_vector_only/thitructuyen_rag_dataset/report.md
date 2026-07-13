# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `30`
- **Avg latency**: `21764.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `100.00%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `63.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `30.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `63.33%` |
| precision@3 | `22.22%` |
| recall@3 | `60.56%` |
| mrr@3 | `60.00%` |
| ndcg@3 | `59.25%` |
| hit@5 | `63.33%` |
| precision@5 | `14.00%` |
| recall@5 | `61.67%` |
| mrr@5 | `60.00%` |
| ndcg@5 | `59.92%` |
| hit@7 | `63.33%` |
| precision@7 | `10.00%` |
| recall@7 | `61.67%` |
| mrr@7 | `60.00%` |
| ndcg@7 | `61.00%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `62.2%` | `100.0%` | `62.5%` | `21394.4 ms` |
| simple | 22 | `59.1%` | `59.1%` | `59.1%` | `77.3%` | `63.6%` | `21899.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `59.1%` | `59.1%` | `59.1%` | `77.3%` | `63.6%` | `21899.3 ms` |
| medium | 8 | `75.0%` | `68.8%` | `62.2%` | `100.0%` | `62.5%` | `21394.4 ms` |
