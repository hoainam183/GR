# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 11:19:14
- **Total queries**: `30`
- **Avg latency**: `13440.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `96.67%` |
| precision@3 | `33.33%` |
| recall@3 | `93.33%` |
| mrr@3 | `91.67%` |
| ndcg@3 | `91.35%` |
| hit@5 | `100.00%` |
| precision@5 | `21.33%` |
| recall@5 | `96.67%` |
| mrr@5 | `92.50%` |
| ndcg@5 | `93.02%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `96.67%` |
| mrr@7 | `92.50%` |
| ndcg@7 | `93.02%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `87.5%` | `78.4%` | `100.0%` | `87.5%` | `15651.4 ms` |
| simple | 22 | `100.0%` | `100.0%` | `98.3%` | `95.5%` | `100.0%` | `12636.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `100.0%` | `100.0%` | `98.4%` | `95.7%` | `100.0%` | `13028.4 ms` |
| medium | 7 | `100.0%` | `85.7%` | `75.4%` | `100.0%` | `85.7%` | `14795.3 ms` |
