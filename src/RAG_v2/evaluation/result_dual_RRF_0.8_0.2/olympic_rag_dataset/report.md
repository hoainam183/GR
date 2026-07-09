# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 06:45:27
- **Total queries**: `30`
- **Avg latency**: `25425.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `66.67%` |
| precision@3 | `23.33%` |
| recall@3 | `65.00%` |
| mrr@3 | `62.78%` |
| ndcg@3 | `62.96%` |
| hit@5 | `93.33%` |
| precision@5 | `20.00%` |
| recall@5 | `91.67%` |
| mrr@5 | `69.28%` |
| ndcg@5 | `74.53%` |
| hit@7 | `93.33%` |
| precision@7 | `14.29%` |
| recall@7 | `91.67%` |
| mrr@7 | `69.28%` |
| ndcg@7 | `74.53%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `66.5%` | `100.0%` | `87.5%` | `27719.5 ms` |
| simple | 22 | `95.5%` | `95.5%` | `77.5%` | `90.9%` | `95.5%` | `24590.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `95.7%` | `95.7%` | `76.0%` | `91.3%` | `95.7%` | `26277.0 ms` |
| medium | 7 | `85.7%` | `78.6%` | `69.8%` | `100.0%` | `85.7%` | `22625.7 ms` |
