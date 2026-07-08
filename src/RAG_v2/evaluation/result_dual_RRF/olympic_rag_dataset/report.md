# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 01:03:22
- **Total queries**: `30`
- **Avg latency**: `15926.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `40.00%` |
| precision@3 | `13.33%` |
| recall@3 | `38.33%` |
| mrr@3 | `40.00%` |
| ndcg@3 | `38.71%` |
| hit@5 | `73.33%` |
| precision@5 | `14.67%` |
| recall@5 | `68.33%` |
| mrr@5 | `47.83%` |
| ndcg@5 | `51.52%` |
| hit@7 | `76.67%` |
| precision@7 | `11.43%` |
| recall@7 | `73.33%` |
| mrr@7 | `48.39%` |
| ndcg@7 | `53.43%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `68.8%` | `42.4%` | `100.0%` | `87.5%` | `13808.4 ms` |
| simple | 22 | `68.2%` | `68.2%` | `54.8%` | `95.5%` | `72.7%` | `16696.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `69.6%` | `69.6%` | `54.3%` | `95.7%` | `73.9%` | `16512.8 ms` |
| medium | 7 | `85.7%` | `64.3%` | `42.3%` | `100.0%` | `85.7%` | `14000.3 ms` |
