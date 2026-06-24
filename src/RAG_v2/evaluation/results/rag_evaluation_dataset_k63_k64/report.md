# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 18:56:18
- **Total queries**: `30`
- **Avg latency**: `29523.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `76.67%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `100.00%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `73.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `16.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `20.00%` |
| recall@3 | `56.67%` |
| mrr@3 | `51.11%` |
| ndcg@3 | `52.54%` |
| hit@5 | `63.33%` |
| precision@5 | `13.33%` |
| recall@5 | `63.33%` |
| mrr@5 | `52.78%` |
| ndcg@5 | `55.41%` |
| hit@7 | `63.33%` |
| precision@7 | `9.53%` |
| recall@7 | `63.33%` |
| mrr@7 | `52.78%` |
| ndcg@7 | `55.41%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `12.5%` | `12.5%` | `62.5%` | `62.5%` | `55489.2 ms` |
| simple | 22 | `81.8%` | `81.8%` | `71.0%` | `81.8%` | `77.3%` | `20080.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `81.8%` | `81.8%` | `71.0%` | `81.8%` | `77.3%` | `20080.8 ms` |
| medium | 8 | `12.5%` | `12.5%` | `12.5%` | `62.5%` | `62.5%` | `55489.2 ms` |
