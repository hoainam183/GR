# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `50`
- **Avg latency**: `10157.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `82.00%` |
| Hallucination rate | `10.00%` (5) |
| Answer relevance | `98.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `66.00%` |
| Correctness vs gold (partial) | `12.00%` |
| Correctness vs gold (incorrect) | `22.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `58.00%` |
| precision@3 | `20.67%` |
| recall@3 | `58.00%` |
| mrr@3 | `48.67%` |
| ndcg@3 | `51.09%` |
| hit@5 | `60.00%` |
| precision@5 | `12.80%` |
| recall@5 | `60.00%` |
| mrr@5 | `49.17%` |
| ndcg@5 | `51.96%` |
| hit@7 | `60.00%` |
| precision@7 | `9.15%` |
| recall@7 | `60.00%` |
| mrr@7 | `49.17%` |
| ndcg@7 | `51.96%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `50.0%` | `50.0%` | `46.9%` | `58.3%` | `58.3%` | `12527.3 ms` |
| simple | 38 | `63.2%` | `63.2%` | `53.5%` | `89.5%` | `68.4%` | `9409.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `63.2%` | `63.2%` | `53.5%` | `89.5%` | `68.4%` | `9409.4 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `0.0%` | `100.0%` | `11538.6 ms` |
| medium | 11 | `45.5%` | `45.5%` | `42.1%` | `63.6%` | `54.5%` | `12617.2 ms` |
