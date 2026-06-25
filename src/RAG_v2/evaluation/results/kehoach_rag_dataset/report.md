# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 16:22:17
- **Total queries**: `50`
- **Avg latency**: `17891.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `94.00%` |
| Hallucination rate | `2.00%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `94.00%` |
| Correctness vs gold (correct) | `56.00%` |
| Correctness vs gold (partial) | `14.00%` |
| Correctness vs gold (incorrect) | `30.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `48.00%` |
| precision@3 | `17.33%` |
| recall@3 | `48.00%` |
| mrr@3 | `42.00%` |
| ndcg@3 | `43.57%` |
| hit@5 | `50.00%` |
| precision@5 | `10.80%` |
| recall@5 | `50.00%` |
| mrr@5 | `42.50%` |
| ndcg@5 | `44.43%` |
| hit@7 | `50.00%` |
| precision@7 | `7.72%` |
| recall@7 | `50.00%` |
| mrr@7 | `42.50%` |
| ndcg@7 | `45.14%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `33.3%` | `33.3%` | `30.3%` | `91.7%` | `50.0%` | `26086.7 ms` |
| simple | 38 | `55.3%` | `55.3%` | `48.9%` | `94.7%` | `57.9%` | `15303.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `55.3%` | `55.3%` | `48.9%` | `94.7%` | `57.9%` | `15303.4 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `18921.3 ms` |
| medium | 11 | `27.3%` | `27.3%` | `23.9%` | `90.9%` | `45.5%` | `26738.1 ms` |
