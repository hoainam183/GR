# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 23:12:27
- **Total queries**: `30`
- **Avg latency**: `14864.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `80.00%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `43.33%` |
| precision@3 | `14.44%` |
| recall@3 | `41.67%` |
| mrr@3 | `43.33%` |
| ndcg@3 | `42.04%` |
| hit@5 | `76.67%` |
| precision@5 | `15.33%` |
| recall@5 | `71.67%` |
| mrr@5 | `51.17%` |
| ndcg@5 | `54.85%` |
| hit@7 | `76.67%` |
| precision@7 | `10.96%` |
| recall@7 | `71.67%` |
| mrr@7 | `51.17%` |
| ndcg@7 | `54.85%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `68.8%` | `49.5%` | `87.5%` | `87.5%` | `15231.2 ms` |
| simple | 22 | `72.7%` | `72.7%` | `56.8%` | `77.3%` | `77.3%` | `14731.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `73.9%` | `73.9%` | `56.2%` | `78.3%` | `78.3%` | `14703.4 ms` |
| medium | 7 | `85.7%` | `64.3%` | `50.4%` | `85.7%` | `85.7%` | `15393.3 ms` |
