# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 11:12:22
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
| hit@3 | `42.00%` |
| precision@3 | `15.33%` |
| recall@3 | `42.00%` |
| mrr@3 | `37.67%` |
| ndcg@3 | `38.79%` |
| hit@5 | `56.00%` |
| precision@5 | `12.00%` |
| recall@5 | `56.00%` |
| mrr@5 | `40.77%` |
| ndcg@5 | `44.46%` |
| hit@7 | `60.00%` |
| precision@7 | `9.15%` |
| recall@7 | `60.00%` |
| mrr@7 | `41.39%` |
| ndcg@7 | `45.84%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `50.0%` | `50.0%` | `40.2%` | `58.3%` | `58.3%` | `12527.3 ms` |
| simple | 38 | `57.9%` | `57.9%` | `45.8%` | `89.5%` | `68.4%` | `9409.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `57.9%` | `57.9%` | `45.8%` | `89.5%` | `68.4%` | `9409.4 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `0.0%` | `100.0%` | `11538.6 ms` |
| medium | 11 | `45.5%` | `45.5%` | `34.7%` | `63.6%` | `54.5%` | `12617.2 ms` |
