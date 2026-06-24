# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 18:18:09
- **Total queries**: `30`
- **Avg latency**: `22296.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `80.00%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `96.67%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `60.00%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `26.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `53.33%` |
| precision@3 | `17.78%` |
| recall@3 | `50.00%` |
| mrr@3 | `46.11%` |
| ndcg@3 | `45.40%` |
| hit@5 | `53.33%` |
| precision@5 | `10.67%` |
| recall@5 | `50.00%` |
| mrr@5 | `46.11%` |
| ndcg@5 | `45.40%` |
| hit@7 | `53.33%` |
| precision@7 | `7.62%` |
| recall@7 | `50.00%` |
| mrr@7 | `46.11%` |
| ndcg@7 | `45.40%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `25.0%` | `12.5%` | `15.3%` | `75.0%` | `37.5%` | `22569.8 ms` |
| simple | 22 | `63.6%` | `63.6%` | `56.3%` | `81.8%` | `68.2%` | `22196.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `56.3%` | `81.8%` | `68.2%` | `22196.9 ms` |
| medium | 8 | `25.0%` | `12.5%` | `15.3%` | `75.0%` | `37.5%` | `22569.8 ms` |
