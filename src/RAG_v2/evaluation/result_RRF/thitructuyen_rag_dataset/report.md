# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 11:43:41
- **Total queries**: `30`
- **Avg latency**: `15291.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `83.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `28.89%` |
| recall@3 | `80.56%` |
| mrr@3 | `78.33%` |
| ndcg@3 | `78.02%` |
| hit@5 | `86.67%` |
| precision@5 | `18.67%` |
| recall@5 | `85.00%` |
| mrr@5 | `79.17%` |
| ndcg@5 | `81.42%` |
| hit@7 | `90.00%` |
| precision@7 | `13.81%` |
| recall@7 | `88.33%` |
| mrr@7 | `79.64%` |
| ndcg@7 | `83.61%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `79.5%` | `100.0%` | `100.0%` | `14082.6 ms` |
| simple | 22 | `86.4%` | `86.4%` | `82.1%` | `100.0%` | `77.3%` | `15731.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `82.1%` | `100.0%` | `77.3%` | `15731.1 ms` |
| medium | 8 | `87.5%` | `81.2%` | `79.5%` | `100.0%` | `100.0%` | `14082.6 ms` |
