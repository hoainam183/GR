# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 01:12:07
- **Total queries**: `30`
- **Avg latency**: `23849.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `86.67%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `34.44%` |
| recall@3 | `83.33%` |
| mrr@3 | `82.78%` |
| ndcg@3 | `81.84%` |
| hit@5 | `90.00%` |
| precision@5 | `22.00%` |
| recall@5 | `86.67%` |
| mrr@5 | `83.61%` |
| ndcg@5 | `83.51%` |
| hit@7 | `90.00%` |
| precision@7 | `15.72%` |
| recall@7 | `86.67%` |
| mrr@7 | `83.61%` |
| ndcg@7 | `83.51%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `87.5%` | `80.3%` | `75.0%` | `75.0%` | `30829.7 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.7%` | `95.5%` | `90.9%` | `21311.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.7%` | `95.5%` | `90.9%` | `21311.0 ms` |
| hard | 2 | `100.0%` | `75.0%` | `65.3%` | `50.0%` | `50.0%` | `30496.3 ms` |
| medium | 6 | `100.0%` | `91.7%` | `85.2%` | `83.3%` | `83.3%` | `30940.8 ms` |
