# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `30`
- **Avg latency**: `23960.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `66.67%` |
| Hallucination rate | `30.00%` (9) |
| Answer relevance | `86.67%` |
| Completeness | `70.00%` |
| Correctness vs gold (correct) | `63.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `26.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `16.66%` |
| recall@3 | `48.33%` |
| mrr@3 | `38.33%` |
| ndcg@3 | `40.02%` |
| hit@5 | `53.33%` |
| precision@5 | `10.67%` |
| recall@5 | `51.67%` |
| mrr@5 | `39.17%` |
| ndcg@5 | `41.46%` |
| hit@7 | `53.33%` |
| precision@7 | `7.62%` |
| recall@7 | `51.67%` |
| mrr@7 | `39.17%` |
| ndcg@7 | `41.46%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `6.2%` | `7.7%` | `37.5%` | `62.5%` | `24791.4 ms` |
| simple | 22 | `68.2%` | `68.2%` | `53.7%` | `77.3%` | `63.6%` | `23657.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `68.2%` | `68.2%` | `53.7%` | `77.3%` | `63.6%` | `23657.8 ms` |
| medium | 8 | `12.5%` | `6.2%` | `7.7%` | `37.5%` | `62.5%` | `24791.4 ms` |
