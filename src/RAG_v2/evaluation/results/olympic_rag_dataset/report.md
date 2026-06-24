# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 17:11:09
- **Total queries**: `30`
- **Avg latency**: `20450.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `30.00%` |
| recall@3 | `83.33%` |
| mrr@3 | `83.33%` |
| ndcg@3 | `82.10%` |
| hit@5 | `90.00%` |
| precision@5 | `18.67%` |
| recall@5 | `86.67%` |
| mrr@5 | `84.17%` |
| ndcg@5 | `83.54%` |
| hit@7 | `90.00%` |
| precision@7 | `13.34%` |
| recall@7 | `86.67%` |
| mrr@7 | `84.17%` |
| ndcg@7 | `83.54%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `67.9%` | `100.0%` | `87.5%` | `20080.4 ms` |
| simple | 22 | `90.9%` | `90.9%` | `89.2%` | `95.5%` | `90.9%` | `20585.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `89.7%` | `95.7%` | `91.3%` | `20322.3 ms` |
| medium | 7 | `85.7%` | `71.4%` | `63.3%` | `100.0%` | `85.7%` | `20872.4 ms` |
