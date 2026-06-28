# RAG Evaluation Report (production config)

- **Date**: 2026-06-27 13:39:51
- **Total queries**: `30`
- **Avg latency**: `15897.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `80.00%` |
| Hallucination rate | `10.00%` (3) |
| Answer relevance | `100.00%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `66.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `23.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `46.67%` |
| precision@3 | `16.67%` |
| recall@3 | `46.67%` |
| mrr@3 | `37.22%` |
| ndcg@3 | `39.37%` |
| hit@5 | `60.00%` |
| precision@5 | `13.33%` |
| recall@5 | `60.00%` |
| mrr@5 | `40.56%` |
| ndcg@5 | `45.35%` |
| hit@7 | `63.33%` |
| precision@7 | `10.00%` |
| recall@7 | `63.33%` |
| mrr@7 | `41.11%` |
| ndcg@7 | `46.54%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `25.0%` | `25.0%` | `17.8%` | `37.5%` | `12.5%` | `13385.9 ms` |
| simple | 22 | `72.7%` | `72.7%` | `55.4%` | `95.5%` | `86.4%` | `16810.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `72.7%` | `72.7%` | `55.4%` | `95.5%` | `86.4%` | `16810.1 ms` |
| medium | 8 | `25.0%` | `25.0%` | `17.8%` | `37.5%` | `12.5%` | `13385.9 ms` |
