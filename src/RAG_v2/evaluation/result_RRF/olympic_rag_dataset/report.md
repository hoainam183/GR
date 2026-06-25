# RAG Evaluation Report (production config)

- **Date**: 2026-06-24 22:58:13
- **Total queries**: `30`
- **Avg latency**: `13042.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `96.67%` |
| precision@3 | `33.33%` |
| recall@3 | `93.33%` |
| mrr@3 | `91.67%` |
| ndcg@3 | `91.35%` |
| hit@5 | `96.67%` |
| precision@5 | `20.00%` |
| recall@5 | `93.33%` |
| mrr@5 | `91.67%` |
| ndcg@5 | `91.35%` |
| hit@7 | `96.67%` |
| precision@7 | `14.29%` |
| recall@7 | `93.33%` |
| mrr@7 | `91.67%` |
| ndcg@7 | `91.35%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `72.2%` | `100.0%` | `75.0%` | `14157.8 ms` |
| simple | 22 | `100.0%` | `100.0%` | `98.3%` | `95.5%` | `100.0%` | `12636.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `100.0%` | `100.0%` | `98.4%` | `95.7%` | `100.0%` | `13028.4 ms` |
| medium | 7 | `85.7%` | `71.4%` | `68.2%` | `100.0%` | `71.4%` | `13088.3 ms` |
