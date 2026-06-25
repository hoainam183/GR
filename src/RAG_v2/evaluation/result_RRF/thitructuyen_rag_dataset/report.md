# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 17:57:41
- **Total queries**: `30`
- **Avg latency**: `12899.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `60.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `33.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `66.67%` |
| precision@3 | `23.33%` |
| recall@3 | `63.89%` |
| mrr@3 | `63.33%` |
| ndcg@3 | `62.58%` |
| hit@5 | `66.67%` |
| precision@5 | `14.67%` |
| recall@5 | `65.00%` |
| mrr@5 | `63.33%` |
| ndcg@5 | `63.26%` |
| hit@7 | `66.67%` |
| precision@7 | `10.48%` |
| recall@7 | `65.00%` |
| mrr@7 | `63.33%` |
| ndcg@7 | `64.33%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `62.2%` | `100.0%` | `75.0%` | `12406.2 ms` |
| simple | 22 | `63.6%` | `63.6%` | `63.6%` | `100.0%` | `54.5%` | `13078.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `63.6%` | `100.0%` | `54.5%` | `13078.5 ms` |
| medium | 8 | `75.0%` | `68.8%` | `62.2%` | `100.0%` | `75.0%` | `12406.2 ms` |
