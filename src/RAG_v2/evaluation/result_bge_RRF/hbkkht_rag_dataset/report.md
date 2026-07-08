# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 12:52:17
- **Total queries**: `30`
- **Avg latency**: `17941.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `33.33%` |
| recall@3 | `90.00%` |
| mrr@3 | `88.33%` |
| ndcg@3 | `87.27%` |
| hit@5 | `96.67%` |
| precision@5 | `21.33%` |
| recall@5 | `95.00%` |
| mrr@5 | `89.17%` |
| ndcg@5 | `93.40%` |
| hit@7 | `100.00%` |
| precision@7 | `15.72%` |
| recall@7 | `98.33%` |
| mrr@7 | `89.72%` |
| ndcg@7 | `96.42%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `86.2%` | `100.0%` | `87.5%` | `16430.4 ms` |
| simple | 22 | `100.0%` | `100.0%` | `96.0%` | `100.0%` | `100.0%` | `18491.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `95.7%` | `95.7%` | `91.8%` | `100.0%` | `100.0%` | `18396.5 ms` |
| hard | 1 | `100.0%` | `100.0%` | `62.4%` | `100.0%` | `100.0%` | `15326.0 ms` |
| medium | 6 | `100.0%` | `91.7%` | `104.5%` | `100.0%` | `83.3%` | `16633.4 ms` |
