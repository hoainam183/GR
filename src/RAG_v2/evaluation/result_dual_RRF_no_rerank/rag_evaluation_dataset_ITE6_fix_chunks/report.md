# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:08:53
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
| hit@3 | `63.33%` |
| precision@3 | `21.11%` |
| recall@3 | `53.33%` |
| mrr@3 | `56.67%` |
| ndcg@3 | `51.89%` |
| hit@5 | `80.00%` |
| precision@5 | `16.67%` |
| recall@5 | `68.33%` |
| mrr@5 | `60.50%` |
| ndcg@5 | `58.51%` |
| hit@7 | `83.33%` |
| precision@7 | `12.86%` |
| recall@7 | `73.33%` |
| mrr@7 | `60.98%` |
| ndcg@7 | `60.30%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `56.2%` | `47.5%` | `62.5%` | `75.0%` | `4033.4 ms` |
| simple | 22 | `72.7%` | `72.7%` | `62.5%` | `72.7%` | `81.8%` | `3323.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `72.7%` | `72.7%` | `62.5%` | `72.7%` | `81.8%` | `3323.0 ms` |
| hard | 2 | `100.0%` | `75.0%` | `54.4%` | `100.0%` | `100.0%` | `4623.7 ms` |
| medium | 6 | `100.0%` | `50.0%` | `45.3%` | `50.0%` | `66.7%` | `3836.6 ms` |
