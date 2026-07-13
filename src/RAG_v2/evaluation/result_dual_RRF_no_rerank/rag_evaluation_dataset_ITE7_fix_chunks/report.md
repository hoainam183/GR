# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
- **Total queries**: `30`
- **Avg latency**: `12765.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `70.00%` |
| Hallucination rate | `26.67%` (8) |
| Answer relevance | `96.67%` |
| Completeness | `73.33%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `63.33%` |
| precision@3 | `24.44%` |
| recall@3 | `61.67%` |
| mrr@3 | `52.78%` |
| ndcg@3 | `54.91%` |
| hit@5 | `73.33%` |
| precision@5 | `18.00%` |
| recall@5 | `71.67%` |
| mrr@5 | `55.28%` |
| ndcg@5 | `59.69%` |
| hit@7 | `80.00%` |
| precision@7 | `13.81%` |
| recall@7 | `78.33%` |
| mrr@7 | `56.23%` |
| ndcg@7 | `61.91%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `51.0%` | `37.5%` | `75.0%` | `11540.1 ms` |
| simple | 22 | `72.7%` | `72.7%` | `62.8%` | `81.8%` | `77.3%` | `13210.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `72.7%` | `72.7%` | `62.8%` | `81.8%` | `77.3%` | `13210.7 ms` |
| hard | 2 | `100.0%` | `75.0%` | `63.2%` | `50.0%` | `50.0%` | `17515.9 ms` |
| medium | 6 | `66.7%` | `66.7%` | `47.0%` | `33.3%` | `83.3%` | `9548.2 ms` |
