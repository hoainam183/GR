# RAG Evaluation Report (production config)

- **Date**: 2026-06-23 17:31:07
- **Total queries**: `30`
- **Avg latency**: `12959.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `93.33%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `66.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `30.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `66.67%` |
| precision@3 | `23.33%` |
| recall@3 | `63.89%` |
| mrr@3 | `62.78%` |
| ndcg@3 | `61.49%` |
| hit@5 | `73.33%` |
| precision@5 | `15.33%` |
| recall@5 | `70.56%` |
| mrr@5 | `64.44%` |
| ndcg@5 | `64.36%` |
| hit@7 | `73.33%` |
| precision@7 | `11.43%` |
| recall@7 | `71.67%` |
| mrr@7 | `64.44%` |
| ndcg@7 | `64.92%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `77.1%` | `67.2%` | `87.5%` | `87.5%` | `14096.8 ms` |
| simple | 22 | `68.2%` | `68.2%` | `63.3%` | `90.9%` | `59.1%` | `12545.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `68.2%` | `68.2%` | `63.3%` | `90.9%` | `59.1%` | `12545.5 ms` |
| medium | 8 | `87.5%` | `77.1%` | `67.2%` | `87.5%` | `87.5%` | `14096.8 ms` |
