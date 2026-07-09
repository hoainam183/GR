# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 13:37:45
- **Total queries**: `30`
- **Avg latency**: `21882.1 ms`

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
| hit@3 | `83.33%` |
| precision@3 | `30.00%` |
| recall@3 | `81.67%` |
| mrr@3 | `81.67%` |
| ndcg@3 | `80.81%` |
| hit@5 | `93.33%` |
| precision@5 | `20.00%` |
| recall@5 | `91.67%` |
| mrr@5 | `84.17%` |
| ndcg@5 | `85.12%` |
| hit@7 | `93.33%` |
| precision@7 | `14.29%` |
| recall@7 | `91.67%` |
| mrr@7 | `84.17%` |
| ndcg@7 | `85.12%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `82.7%` | `100.0%` | `87.5%` | `24060.4 ms` |
| simple | 22 | `95.5%` | `95.5%` | `86.0%` | `90.9%` | `95.5%` | `21089.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `95.7%` | `95.7%` | `86.6%` | `91.3%` | `95.7%` | `21317.6 ms` |
| medium | 7 | `85.7%` | `78.6%` | `80.2%` | `100.0%` | `85.7%` | `23736.7 ms` |
