# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 23:21:43
- **Total queries**: `30`
- **Avg latency**: `36403.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `86.67%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `80.00%` |
| Completeness | `76.67%` |
| Correctness vs gold (correct) | `53.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `46.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `28.89%` |
| recall@3 | `78.33%` |
| mrr@3 | `64.44%` |
| ndcg@3 | `67.14%` |
| hit@5 | `90.00%` |
| precision@5 | `19.33%` |
| recall@5 | `86.67%` |
| mrr@5 | `66.78%` |
| ndcg@5 | `70.75%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `88.33%` |
| mrr@7 | `66.78%` |
| ndcg@7 | `71.43%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `62.4%` | `75.0%` | `25.0%` | `45737.8 ms` |
| simple | 22 | `90.9%` | `90.9%` | `73.8%` | `90.9%` | `63.6%` | `33009.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `70.6%` | `91.3%` | `60.9%` | `33464.7 ms` |
| hard | 1 | `100.0%` | `50.0%` | `26.4%` | `100.0%` | `0.0%` | `47374.2 ms` |
| medium | 6 | `100.0%` | `91.7%` | `78.8%` | `66.7%` | `33.3%` | `45842.4 ms` |
