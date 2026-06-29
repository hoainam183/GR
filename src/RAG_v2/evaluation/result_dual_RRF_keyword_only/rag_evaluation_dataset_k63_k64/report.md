# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 10:27:21
- **Total queries**: `30`
- **Avg latency**: `25779.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `60.00%` |
| Hallucination rate | `33.33%` (10) |
| Answer relevance | `83.33%` |
| Completeness | `53.33%` |
| Correctness vs gold (correct) | `60.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `30.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `16.67%` |
| recall@3 | `48.33%` |
| mrr@3 | `46.67%` |
| ndcg@3 | `46.25%` |
| hit@5 | `53.33%` |
| precision@5 | `10.67%` |
| recall@5 | `51.67%` |
| mrr@5 | `47.50%` |
| ndcg@5 | `47.69%` |
| hit@7 | `56.67%` |
| precision@7 | `8.10%` |
| recall@7 | `53.33%` |
| mrr@7 | `47.98%` |
| ndcg@7 | `48.37%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `6.2%` | `7.7%` | `12.5%` | `37.5%` | `28964.3 ms` |
| simple | 22 | `68.2%` | `68.2%` | `62.2%` | `77.3%` | `68.2%` | `24622.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `68.2%` | `68.2%` | `62.2%` | `77.3%` | `68.2%` | `24622.0 ms` |
| medium | 8 | `12.5%` | `6.2%` | `7.7%` | `12.5%` | `37.5%` | `28964.3 ms` |
