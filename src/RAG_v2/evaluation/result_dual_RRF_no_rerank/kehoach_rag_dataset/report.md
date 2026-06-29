# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:40:00
- **Total queries**: `50`
- **Avg latency**: `19847.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `8.00%` (4) |
| Answer relevance | `100.00%` |
| Completeness | `88.00%` |
| Correctness vs gold (correct) | `64.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `26.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `32.00%` |
| precision@3 | `10.67%` |
| recall@3 | `31.00%` |
| mrr@3 | `28.00%` |
| ndcg@3 | `28.27%` |
| hit@5 | `42.00%` |
| precision@5 | `8.80%` |
| recall@5 | `41.00%` |
| mrr@5 | `30.30%` |
| ndcg@5 | `32.60%` |
| hit@7 | `50.00%` |
| precision@7 | `7.72%` |
| recall@7 | `50.00%` |
| mrr@7 | `31.63%` |
| ndcg@7 | `35.86%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `41.7%` | `37.5%` | `26.3%` | `91.7%` | `50.0%` | `25866.1 ms` |
| simple | 38 | `42.1%` | `42.1%` | `34.6%` | `89.5%` | `68.4%` | `17946.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `42.1%` | `42.1%` | `34.6%` | `89.5%` | `68.4%` | `17946.4 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `12745.9 ms` |
| medium | 11 | `36.4%` | `31.8%` | `19.6%` | `90.9%` | `45.5%` | `27058.8 ms` |
