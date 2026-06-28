# RAG Evaluation Report (production config)

- **Date**: 2026-06-27 23:43:47
- **Total queries**: `30`
- **Avg latency**: `16157.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `100.00%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `50.00%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `36.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `36.67%` |
| precision@3 | `12.22%` |
| recall@3 | `35.00%` |
| mrr@3 | `28.89%` |
| ndcg@3 | `29.58%` |
| hit@5 | `46.67%` |
| precision@5 | `9.33%` |
| recall@5 | `41.67%` |
| mrr@5 | `31.22%` |
| ndcg@5 | `32.69%` |
| hit@7 | `53.33%` |
| precision@7 | `7.62%` |
| recall@7 | `48.33%` |
| mrr@7 | `32.25%` |
| ndcg@7 | `34.99%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `18.8%` | `13.9%` | `62.5%` | `0.0%` | `14036.8 ms` |
| simple | 22 | `50.0%` | `50.0%` | `39.5%` | `90.9%` | `68.2%` | `16928.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `50.0%` | `50.0%` | `39.5%` | `90.9%` | `68.2%` | `16928.5 ms` |
| medium | 8 | `37.5%` | `18.8%` | `13.9%` | `62.5%` | `0.0%` | `14036.8 ms` |
