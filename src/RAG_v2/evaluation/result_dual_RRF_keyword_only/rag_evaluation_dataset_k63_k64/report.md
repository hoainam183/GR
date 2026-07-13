# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `25779.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `63.33%` |
| Hallucination rate | `30.00%` (9) |
| Answer relevance | `96.67%` |
| Completeness | `63.33%` |
| Correctness vs gold (correct) | `73.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `16.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `53.33%` |
| precision@3 | `17.78%` |
| recall@3 | `51.67%` |
| mrr@3 | `50.00%` |
| ndcg@3 | `49.58%` |
| hit@5 | `53.33%` |
| precision@5 | `10.67%` |
| recall@5 | `51.67%` |
| mrr@5 | `50.00%` |
| ndcg@5 | `49.58%` |
| hit@7 | `56.67%` |
| precision@7 | `8.10%` |
| recall@7 | `53.33%` |
| mrr@7 | `50.48%` |
| ndcg@7 | `50.26%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `6.2%` | `7.7%` | `25.0%` | `87.5%` | `28964.3 ms` |
| simple | 22 | `68.2%` | `68.2%` | `64.8%` | `77.3%` | `68.2%` | `24622.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `68.2%` | `68.2%` | `64.8%` | `77.3%` | `68.2%` | `24622.0 ms` |
| medium | 8 | `12.5%` | `6.2%` | `7.7%` | `25.0%` | `87.5%` | `28964.3 ms` |
