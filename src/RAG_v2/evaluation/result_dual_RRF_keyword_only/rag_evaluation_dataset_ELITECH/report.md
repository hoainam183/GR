# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `25356.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `66.67%` |
| Hallucination rate | `30.00%` (9) |
| Answer relevance | `90.00%` |
| Completeness | `66.67%` |
| Correctness vs gold (correct) | `73.33%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `23.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `53.33%` |
| precision@3 | `17.78%` |
| recall@3 | `50.00%` |
| mrr@3 | `47.78%` |
| ndcg@3 | `46.63%` |
| hit@5 | `60.00%` |
| precision@5 | `12.00%` |
| recall@5 | `53.33%` |
| mrr@5 | `49.44%` |
| ndcg@5 | `48.39%` |
| hit@7 | `60.00%` |
| precision@7 | `8.57%` |
| recall@7 | `53.33%` |
| mrr@7 | `49.44%` |
| ndcg@7 | `48.39%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `50.0%` | `25.0%` | `21.9%` | `50.0%` | `75.0%` | `26892.3 ms` |
| simple | 22 | `63.6%` | `63.6%` | `58.0%` | `72.7%` | `72.7%` | `24798.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `58.0%` | `72.7%` | `72.7%` | `24798.0 ms` |
| medium | 8 | `50.0%` | `25.0%` | `21.9%` | `50.0%` | `75.0%` | `26892.3 ms` |
