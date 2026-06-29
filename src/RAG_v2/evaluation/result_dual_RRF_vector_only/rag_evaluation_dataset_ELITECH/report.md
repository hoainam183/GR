# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 13:31:46
- **Total queries**: `30`
- **Avg latency**: `24803.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `76.67%` |
| Hallucination rate | `20.00%` (6) |
| Answer relevance | `96.67%` |
| Completeness | `80.00%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `20.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `18.89%` |
| recall@3 | `51.67%` |
| mrr@3 | `51.11%` |
| ndcg@3 | `48.67%` |
| hit@5 | `60.00%` |
| precision@5 | `12.00%` |
| recall@5 | `53.33%` |
| mrr@5 | `51.78%` |
| ndcg@5 | `49.46%` |
| hit@7 | `60.00%` |
| precision@7 | `8.57%` |
| recall@7 | `53.33%` |
| mrr@7 | `51.78%` |
| ndcg@7 | `49.46%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `50.0%` | `25.0%` | `26.0%` | `100.0%` | `62.5%` | `26465.0 ms` |
| simple | 22 | `63.6%` | `63.6%` | `58.0%` | `68.2%` | `81.8%` | `24198.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `58.0%` | `68.2%` | `81.8%` | `24198.8 ms` |
| medium | 8 | `50.0%` | `25.0%` | `26.0%` | `100.0%` | `62.5%` | `26465.0 ms` |
