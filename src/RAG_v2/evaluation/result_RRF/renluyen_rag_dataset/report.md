# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 17:09:01
- **Total queries**: `30`
- **Avg latency**: `14603.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `83.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `30.00%` |
| recall@3 | `83.33%` |
| mrr@3 | `73.33%` |
| ndcg@3 | `74.45%` |
| hit@5 | `86.67%` |
| precision@5 | `18.00%` |
| recall@5 | `83.33%` |
| mrr@5 | `73.33%` |
| ndcg@5 | `74.45%` |
| hit@7 | `90.00%` |
| precision@7 | `13.81%` |
| recall@7 | `86.67%` |
| mrr@7 | `73.89%` |
| ndcg@7 | `75.86%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `62.5%` | `56.9%` | `100.0%` | `75.0%` | `16908.2 ms` |
| simple | 22 | `90.9%` | `90.9%` | `80.8%` | `100.0%` | `86.4%` | `13766.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `77.3%` | `100.0%` | `82.6%` | `14282.2 ms` |
| hard | 1 | `0.0%` | `0.0%` | `0.0%` | `100.0%` | `100.0%` | `15154.2 ms` |
| medium | 6 | `100.0%` | `83.3%` | `75.8%` | `100.0%` | `83.3%` | `15745.6 ms` |
