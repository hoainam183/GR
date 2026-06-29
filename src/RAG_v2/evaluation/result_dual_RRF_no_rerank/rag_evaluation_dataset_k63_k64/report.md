# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 18:02:28
- **Total queries**: `30`
- **Avg latency**: `23960.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `56.67%` |
| Hallucination rate | `40.00%` (12) |
| Answer relevance | `63.33%` |
| Completeness | `60.00%` |
| Correctness vs gold (correct) | `36.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `56.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `16.67%` |
| recall@3 | `48.33%` |
| mrr@3 | `38.33%` |
| ndcg@3 | `40.02%` |
| hit@5 | `50.00%` |
| precision@5 | `10.00%` |
| recall@5 | `48.33%` |
| mrr@5 | `38.33%` |
| ndcg@5 | `40.02%` |
| hit@7 | `53.33%` |
| precision@7 | `7.62%` |
| recall@7 | `51.67%` |
| mrr@7 | `38.89%` |
| ndcg@7 | `41.21%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `6.2%` | `7.7%` | `0.0%` | `12.5%` | `24791.4 ms` |
| simple | 22 | `63.6%` | `63.6%` | `51.8%` | `77.3%` | `45.5%` | `23657.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `51.8%` | `77.3%` | `45.5%` | `23657.8 ms` |
| medium | 8 | `12.5%` | `6.2%` | `7.7%` | `0.0%` | `12.5%` | `24791.4 ms` |
