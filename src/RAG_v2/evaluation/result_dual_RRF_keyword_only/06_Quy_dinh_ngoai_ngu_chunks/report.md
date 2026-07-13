# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
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
| hit@3 | `43.33%` |
| precision@3 | `14.44%` |
| recall@3 | `40.00%` |
| mrr@3 | `35.56%` |
| ndcg@3 | `34.96%` |
| hit@5 | `46.67%` |
| precision@5 | `9.33%` |
| recall@5 | `41.67%` |
| mrr@5 | `36.22%` |
| ndcg@5 | `35.75%` |
| hit@7 | `53.33%` |
| precision@7 | `7.62%` |
| recall@7 | `48.33%` |
| mrr@7 | `37.25%` |
| ndcg@7 | `38.05%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `18.8%` | `18.3%` | `62.5%` | `0.0%` | `14036.8 ms` |
| simple | 22 | `50.0%` | `50.0%` | `42.1%` | `90.9%` | `68.2%` | `16928.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `50.0%` | `50.0%` | `42.1%` | `90.9%` | `68.2%` | `16928.5 ms` |
| medium | 8 | `37.5%` | `18.8%` | `18.3%` | `62.5%` | `0.0%` | `14036.8 ms` |
