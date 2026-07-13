# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `30`
- **Avg latency**: `12593.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `30.00%` |
| recall@3 | `85.00%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `83.39%` |
| hit@5 | `90.00%` |
| precision@5 | `18.00%` |
| recall@5 | `85.00%` |
| mrr@5 | `85.00%` |
| ndcg@5 | `83.39%` |
| hit@7 | `90.00%` |
| precision@7 | `12.86%` |
| recall@7 | `85.00%` |
| mrr@7 | `85.00%` |
| ndcg@7 | `83.39%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `68.8%` | `67.3%` | `100.0%` | `75.0%` | `13010.4 ms` |
| simple | 22 | `90.9%` | `90.9%` | `89.2%` | `95.5%` | `90.9%` | `12441.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `89.7%` | `95.7%` | `91.3%` | `12332.8 ms` |
| medium | 7 | `85.7%` | `64.3%` | `62.7%` | `100.0%` | `71.4%` | `13449.6 ms` |
