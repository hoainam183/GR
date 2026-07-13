# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:54
- **Total queries**: `30`
- **Avg latency**: `19294.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `63.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `26.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `21.11%` |
| recall@3 | `55.56%` |
| mrr@3 | `50.56%` |
| ndcg@3 | `51.50%` |
| hit@5 | `63.33%` |
| precision@5 | `14.67%` |
| recall@5 | `63.33%` |
| mrr@5 | `52.22%` |
| ndcg@5 | `55.05%` |
| hit@7 | `63.33%` |
| precision@7 | `10.48%` |
| recall@7 | `63.33%` |
| mrr@7 | `52.22%` |
| ndcg@7 | `55.05%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `75.0%` | `63.5%` | `100.0%` | `50.0%` | `21333.1 ms` |
| simple | 22 | `59.1%` | `59.1%` | `52.0%` | `90.9%` | `68.2%` | `18552.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `59.1%` | `59.1%` | `52.0%` | `90.9%` | `68.2%` | `18552.6 ms` |
| medium | 8 | `75.0%` | `75.0%` | `63.5%` | `100.0%` | `50.0%` | `21333.1 ms` |
