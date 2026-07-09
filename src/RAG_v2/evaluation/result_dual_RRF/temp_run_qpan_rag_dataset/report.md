# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 15:23:57
- **Total queries**: `2`
- **Avg latency**: `12290.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `50.00%` |
| Hallucination rate | `50.00%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `50.00%` |
| Correctness vs gold (correct) | `0.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `100.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `16.66%` |
| recall@3 | `25.00%` |
| mrr@3 | `25.00%` |
| ndcg@3 | `19.35%` |
| hit@5 | `50.00%` |
| precision@5 | `10.00%` |
| recall@5 | `25.00%` |
| mrr@5 | `25.00%` |
| ndcg@5 | `19.35%` |
| hit@7 | `100.00%` |
| precision@7 | `14.29%` |
| recall@7 | `75.00%` |
| mrr@7 | `33.33%` |
| ndcg@7 | `37.16%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 2 | `50.0%` | `25.0%` | `19.4%` | `50.0%` | `0.0%` | `12290.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| medium | 2 | `50.0%` | `25.0%` | `19.4%` | `50.0%` | `0.0%` | `12290.2 ms` |
