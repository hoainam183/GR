# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 10:11:18
- **Total queries**: `30`
- **Avg latency**: `18229.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `96.67%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `66.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `30.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `60.00%` |
| precision@3 | `24.44%` |
| recall@3 | `60.00%` |
| mrr@3 | `60.00%` |
| ndcg@3 | `59.73%` |
| hit@5 | `66.67%` |
| precision@5 | `16.67%` |
| recall@5 | `65.00%` |
| mrr@5 | `61.50%` |
| ndcg@5 | `63.87%` |
| hit@7 | `66.67%` |
| precision@7 | `11.91%` |
| recall@7 | `65.00%` |
| mrr@7 | `61.50%` |
| ndcg@7 | `64.59%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `64.5%` | `87.5%` | `87.5%` | `16936.9 ms` |
| simple | 22 | `63.6%` | `63.6%` | `63.6%` | `95.5%` | `59.1%` | `18699.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `63.6%` | `95.5%` | `59.1%` | `18699.1 ms` |
| hard | 2 | `50.0%` | `50.0%` | `50.0%` | `100.0%` | `50.0%` | `22487.9 ms` |
| medium | 6 | `83.3%` | `75.0%` | `69.3%` | `83.3%` | `100.0%` | `15086.5 ms` |
