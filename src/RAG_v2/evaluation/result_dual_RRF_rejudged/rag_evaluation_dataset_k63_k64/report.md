# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 01:39:49
- **Total queries**: `30`
- **Avg latency**: `36862.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `53.33%` |
| Hallucination rate | `43.33%` (13) |
| Answer relevance | `63.33%` |
| Completeness | `33.33%` |
| Correctness vs gold (correct) | `70.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `20.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `17.78%` |
| recall@3 | `50.00%` |
| mrr@3 | `46.11%` |
| ndcg@3 | `47.10%` |
| hit@5 | `60.00%` |
| precision@5 | `12.67%` |
| recall@5 | `60.00%` |
| mrr@5 | `48.61%` |
| ndcg@5 | `51.41%` |
| hit@7 | `60.00%` |
| precision@7 | `9.05%` |
| recall@7 | `60.00%` |
| mrr@7 | `48.61%` |
| ndcg@7 | `51.41%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `12.5%` | `12.5%` | `37.5%` | `62.5%` | `46304.9 ms` |
| simple | 22 | `77.3%` | `77.3%` | `65.6%` | `59.1%` | `72.7%` | `33428.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `77.3%` | `77.3%` | `65.6%` | `59.1%` | `72.7%` | `33428.4 ms` |
| medium | 8 | `12.5%` | `12.5%` | `12.5%` | `37.5%` | `62.5%` | `46304.9 ms` |
