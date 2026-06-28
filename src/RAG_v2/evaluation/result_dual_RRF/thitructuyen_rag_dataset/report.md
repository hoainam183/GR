# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 00:02:55
- **Total queries**: `30`
- **Avg latency**: `28705.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `73.33%` |
| Completeness | `63.33%` |
| Correctness vs gold (correct) | `43.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `56.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `18.89%` |
| recall@3 | `55.00%` |
| mrr@3 | `52.78%` |
| ndcg@3 | `52.48%` |
| hit@5 | `66.67%` |
| precision@5 | `13.33%` |
| recall@5 | `62.78%` |
| mrr@5 | `55.28%` |
| ndcg@5 | `56.03%` |
| hit@7 | `66.67%` |
| precision@7 | `10.00%` |
| recall@7 | `63.89%` |
| mrr@7 | `55.28%` |
| ndcg@7 | `56.58%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `60.4%` | `48.5%` | `87.5%` | `12.5%` | `34106.1 ms` |
| simple | 22 | `63.6%` | `63.6%` | `58.8%` | `81.8%` | `54.5%` | `26741.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `63.6%` | `63.6%` | `58.8%` | `81.8%` | `54.5%` | `26741.9 ms` |
| medium | 8 | `75.0%` | `60.4%` | `48.5%` | `87.5%` | `12.5%` | `34106.1 ms` |
