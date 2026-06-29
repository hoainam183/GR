# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 10:46:55
- **Total queries**: `30`
- **Avg latency**: `24852.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `6.67%` |
| Hallucination rate | `93.33%` (28) |
| Answer relevance | `6.67%` |
| Completeness | `6.67%` |
| Correctness vs gold (correct) | `3.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `96.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `28.89%` |
| recall@3 | `76.67%` |
| mrr@3 | `65.00%` |
| ndcg@3 | `66.76%` |
| hit@5 | `86.67%` |
| precision@5 | `19.33%` |
| recall@5 | `85.00%` |
| mrr@5 | `66.67%` |
| ndcg@5 | `70.52%` |
| hit@7 | `86.67%` |
| precision@7 | `13.81%` |
| recall@7 | `85.00%` |
| mrr@7 | `66.67%` |
| ndcg@7 | `70.52%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `68.8%` | `0.0%` | `0.0%` | `31464.4 ms` |
| simple | 22 | `86.4%` | `86.4%` | `71.1%` | `9.1%` | `4.5%` | `22448.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `82.6%` | `82.6%` | `68.0%` | `8.7%` | `4.3%` | `22881.6 ms` |
| hard | 1 | `100.0%` | `100.0%` | `65.1%` | `0.0%` | `0.0%` | `41255.4 ms` |
| medium | 6 | `100.0%` | `91.7%` | `81.0%` | `0.0%` | `0.0%` | `29675.2 ms` |
