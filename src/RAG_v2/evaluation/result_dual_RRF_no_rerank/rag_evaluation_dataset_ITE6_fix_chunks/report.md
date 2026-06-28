# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 14:36:21
- **Total queries**: `30`
- **Avg latency**: `3512.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `70.00%` |
| Hallucination rate | `30.00%` (9) |
| Answer relevance | `96.67%` |
| Completeness | `73.33%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `18.89%` |
| recall@3 | `48.33%` |
| mrr@3 | `52.22%` |
| ndcg@3 | `47.53%` |
| hit@5 | `70.00%` |
| precision@5 | `14.67%` |
| recall@5 | `61.67%` |
| mrr@5 | `55.39%` |
| ndcg@5 | `53.36%` |
| hit@7 | `80.00%` |
| precision@7 | `12.38%` |
| recall@7 | `71.67%` |
| mrr@7 | `56.90%` |
| ndcg@7 | `56.99%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `43.8%` | `40.8%` | `62.5%` | `75.0%` | `4033.4 ms` |
| simple | 22 | `68.2%` | `68.2%` | `58.0%` | `72.7%` | `81.8%` | `3323.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `68.2%` | `68.2%` | `58.0%` | `72.7%` | `81.8%` | `3323.0 ms` |
| hard | 2 | `50.0%` | `50.0%` | `42.5%` | `100.0%` | `100.0%` | `4623.7 ms` |
| medium | 6 | `83.3%` | `41.7%` | `40.2%` | `50.0%` | `66.7%` | `3836.6 ms` |
