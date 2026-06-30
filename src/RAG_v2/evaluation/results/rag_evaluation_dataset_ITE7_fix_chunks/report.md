# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 16:05:09
- **Total queries**: `30`
- **Avg latency**: `14595.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `33.33%` |
| recall@3 | `85.00%` |
| mrr@3 | `90.00%` |
| ndcg@3 | `85.86%` |
| hit@5 | `93.33%` |
| precision@5 | `21.33%` |
| recall@5 | `88.33%` |
| mrr@5 | `90.83%` |
| ndcg@5 | `87.53%` |
| hit@7 | `93.33%` |
| precision@7 | `15.24%` |
| recall@7 | `88.33%` |
| mrr@7 | `90.83%` |
| ndcg@7 | `88.26%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `68.8%` | `65.8%` | `75.0%` | `75.0%` | `15977.2 ms` |
| simple | 22 | `95.5%` | `95.5%` | `95.5%` | `100.0%` | `90.9%` | `14092.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `95.5%` | `95.5%` | `95.5%` | `100.0%` | `90.9%` | `14092.4 ms` |
| hard | 2 | `100.0%` | `75.0%` | `63.2%` | `100.0%` | `50.0%` | `21317.4 ms` |
| medium | 6 | `83.3%` | `66.7%` | `66.6%` | `66.7%` | `83.3%` | `14197.1 ms` |
