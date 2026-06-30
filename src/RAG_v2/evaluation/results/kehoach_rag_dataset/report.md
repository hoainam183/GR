# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 12:32:16
- **Total queries**: `50`
- **Avg latency**: `18193.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `92.00%` |
| Hallucination rate | `2.00%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `94.00%` |
| Correctness vs gold (correct) | `72.00%` |
| Correctness vs gold (partial) | `12.00%` |
| Correctness vs gold (incorrect) | `16.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.00%` |
| precision@3 | `20.67%` |
| recall@3 | `55.00%` |
| mrr@3 | `50.00%` |
| ndcg@3 | `50.80%` |
| hit@5 | `64.00%` |
| precision@5 | `14.40%` |
| recall@5 | `64.00%` |
| mrr@5 | `51.80%` |
| ndcg@5 | `54.54%` |
| hit@7 | `66.00%` |
| precision@7 | `10.57%` |
| recall@7 | `66.00%` |
| mrr@7 | `52.09%` |
| ndcg@7 | `55.92%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `58.3%` | `58.3%` | `48.9%` | `83.3%` | `83.3%` | `25599.2 ms` |
| simple | 38 | `65.8%` | `65.8%` | `56.3%` | `94.7%` | `68.4%` | `15854.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `65.8%` | `65.8%` | `56.3%` | `94.7%` | `68.4%` | `15854.5 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `18921.3 ms` |
| medium | 11 | `54.5%` | `54.5%` | `44.3%` | `81.8%` | `81.8%` | `26206.3 ms` |
