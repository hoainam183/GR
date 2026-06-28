# RAG Evaluation Report (production config)

- **Date**: 2026-06-27 14:18:50
- **Total queries**: `30`
- **Avg latency**: `12084.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `76.67%` |
| precision@3 | `28.89%` |
| recall@3 | `71.67%` |
| mrr@3 | `71.67%` |
| ndcg@3 | `69.05%` |
| hit@5 | `80.00%` |
| precision@5 | `18.67%` |
| recall@5 | `75.00%` |
| mrr@5 | `72.33%` |
| ndcg@5 | `70.72%` |
| hit@7 | `83.33%` |
| precision@7 | `14.29%` |
| recall@7 | `78.33%` |
| mrr@7 | `72.81%` |
| ndcg@7 | `72.13%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `68.8%` | `61.9%` | `100.0%` | `87.5%` | `17053.5 ms` |
| simple | 22 | `77.3%` | `77.3%` | `73.9%` | `100.0%` | `86.4%` | `10278.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `75.0%` | `75.0%` | `73.2%` | `100.0%` | `85.0%` | `9958.6 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `100.0%` | `100.0%` | `7340.3 ms` |
| medium | 9 | `88.9%` | `72.2%` | `65.5%` | `100.0%` | `88.9%` | `17336.9 ms` |
