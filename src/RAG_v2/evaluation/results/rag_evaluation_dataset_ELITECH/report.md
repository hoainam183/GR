# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 16:01:01
- **Total queries**: `30`
- **Avg latency**: `49601.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `76.67%` |
| Hallucination rate | `20.00%` (6) |
| Answer relevance | `93.33%` |
| Completeness | `80.00%` |
| Correctness vs gold (correct) | `63.33%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `23.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `53.33%` |
| precision@3 | `17.78%` |
| recall@3 | `50.00%` |
| mrr@3 | `46.11%` |
| ndcg@3 | `45.40%` |
| hit@5 | `60.00%` |
| precision@5 | `12.00%` |
| recall@5 | `55.00%` |
| mrr@5 | `47.61%` |
| ndcg@5 | `47.62%` |
| hit@7 | `60.00%` |
| precision@7 | `8.57%` |
| recall@7 | `55.00%` |
| mrr@7 | `47.61%` |
| ndcg@7 | `47.62%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `18.8%` | `18.3%` | `62.5%` | `37.5%` | `117217.4 ms` |
| simple | 22 | `68.2%` | `68.2%` | `58.3%` | `81.8%` | `72.7%` | `25014.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `68.2%` | `68.2%` | `58.3%` | `81.8%` | `72.7%` | `25014.5 ms` |
| medium | 8 | `37.5%` | `18.8%` | `18.3%` | `62.5%` | `37.5%` | `117217.4 ms` |
