# RAG Evaluation Report (production config)

- **Date**: 2026-06-24 20:48:23
- **Total queries**: `30`
- **Avg latency**: `14958.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `100.00%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `70.00%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `26.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `21.11%` |
| recall@3 | `55.00%` |
| mrr@3 | `47.22%` |
| ndcg@3 | `48.09%` |
| hit@5 | `60.00%` |
| precision@5 | `13.33%` |
| recall@5 | `58.33%` |
| mrr@5 | `48.06%` |
| ndcg@5 | `49.52%` |
| hit@7 | `66.67%` |
| precision@7 | `10.48%` |
| recall@7 | `65.00%` |
| mrr@7 | `49.09%` |
| ndcg@7 | `51.82%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `31.2%` | `31.7%` | `62.5%` | `12.5%` | `16742.4 ms` |
| simple | 22 | `68.2%` | `68.2%` | `56.0%` | `90.9%` | `90.9%` | `14309.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `68.2%` | `68.2%` | `56.0%` | `90.9%` | `90.9%` | `14309.9 ms` |
| medium | 8 | `37.5%` | `31.2%` | `31.7%` | `62.5%` | `12.5%` | `16742.4 ms` |
