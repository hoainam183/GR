# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 13:31:45
- **Total queries**: `30`
- **Avg latency**: `23412.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `66.67%` |
| Hallucination rate | `26.67%` (8) |
| Answer relevance | `93.33%` |
| Completeness | `73.33%` |
| Correctness vs gold (correct) | `63.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `26.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `40.00%` |
| precision@3 | `14.44%` |
| recall@3 | `40.00%` |
| mrr@3 | `33.33%` |
| ndcg@3 | `34.81%` |
| hit@5 | `56.67%` |
| precision@5 | `12.67%` |
| recall@5 | `55.00%` |
| mrr@5 | `37.50%` |
| ndcg@5 | `41.67%` |
| hit@7 | `63.33%` |
| precision@7 | `10.00%` |
| recall@7 | `61.67%` |
| mrr@7 | `38.61%` |
| ndcg@7 | `44.04%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `31.2%` | `21.1%` | `37.5%` | `0.0%` | `38013.9 ms` |
| simple | 22 | `63.6%` | `63.6%` | `49.2%` | `77.3%` | `86.4%` | `18102.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `49.2%` | `77.3%` | `86.4%` | `18102.8 ms` |
| medium | 8 | `37.5%` | `31.2%` | `21.1%` | `37.5%` | `0.0%` | `38013.9 ms` |
