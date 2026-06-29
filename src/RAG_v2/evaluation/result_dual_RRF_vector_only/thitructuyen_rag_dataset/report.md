# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:03:26
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
| hit@3 | `53.33%` |
| precision@3 | `18.89%` |
| recall@3 | `50.56%` |
| mrr@3 | `50.00%` |
| ndcg@3 | `49.25%` |
| hit@5 | `63.33%` |
| precision@5 | `14.00%` |
| recall@5 | `61.67%` |
| mrr@5 | `52.50%` |
| ndcg@5 | `54.23%` |
| hit@7 | `63.33%` |
| precision@7 | `10.00%` |
| recall@7 | `61.67%` |
| mrr@7 | `52.50%` |
| ndcg@7 | `55.31%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `48.0%` | `100.0%` | `62.5%` | `21394.4 ms` |
| simple | 22 | `59.1%` | `59.1%` | `56.5%` | `77.3%` | `63.6%` | `21899.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `59.1%` | `59.1%` | `56.5%` | `77.3%` | `63.6%` | `21899.3 ms` |
| medium | 8 | `75.0%` | `68.8%` | `48.0%` | `100.0%` | `62.5%` | `21394.4 ms` |
