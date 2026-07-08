# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 23:33:46
- **Total queries**: `30`
- **Avg latency**: `18929.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `26.66%` |
| recall@3 | `76.67%` |
| mrr@3 | `80.00%` |
| ndcg@3 | `77.42%` |
| hit@5 | `93.33%` |
| precision@5 | `20.00%` |
| recall@5 | `91.67%` |
| mrr@5 | `83.33%` |
| ndcg@5 | `87.15%` |
| hit@7 | `96.67%` |
| precision@7 | `14.77%` |
| recall@7 | `95.00%` |
| mrr@7 | `83.89%` |
| ndcg@7 | `89.07%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `62.4%` | `75.0%` | `62.5%` | `17656.6 ms` |
| simple | 22 | `100.0%` | `100.0%` | `96.2%` | `100.0%` | `100.0%` | `19392.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `95.8%` | `95.8%` | `92.3%` | `100.0%` | `100.0%` | `19449.5 ms` |
| medium | 6 | `83.3%` | `75.0%` | `66.5%` | `66.7%` | `50.0%` | `16850.0 ms` |
