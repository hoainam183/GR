# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 16:06:34
- **Total queries**: `30`
- **Avg latency**: `30902.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `73.33%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `100.00%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `73.33%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `60.00%` |
| precision@3 | `21.11%` |
| recall@3 | `60.00%` |
| mrr@3 | `54.44%` |
| ndcg@3 | `55.87%` |
| hit@5 | `66.67%` |
| precision@5 | `14.00%` |
| recall@5 | `66.67%` |
| mrr@5 | `56.11%` |
| ndcg@5 | `58.74%` |
| hit@7 | `66.67%` |
| precision@7 | `10.00%` |
| recall@7 | `66.67%` |
| mrr@7 | `56.11%` |
| ndcg@7 | `58.74%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `12.5%` | `12.5%` | `62.5%` | `62.5%` | `55489.2 ms` |
| simple | 22 | `86.4%` | `86.4%` | `75.6%` | `77.3%` | `77.3%` | `21961.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `75.6%` | `77.3%` | `77.3%` | `21961.2 ms` |
| medium | 8 | `12.5%` | `12.5%` | `12.5%` | `62.5%` | `62.5%` | `55489.2 ms` |
