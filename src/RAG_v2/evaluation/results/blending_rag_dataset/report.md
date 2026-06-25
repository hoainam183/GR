# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 18:29:25
- **Total queries**: `30`
- **Avg latency**: `13776.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `20.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `32.22%` |
| recall@3 | `76.67%` |
| mrr@3 | `77.78%` |
| ndcg@3 | `75.49%` |
| hit@5 | `80.00%` |
| precision@5 | `19.33%` |
| recall@5 | `76.67%` |
| mrr@5 | `77.78%` |
| ndcg@5 | `75.49%` |
| hit@7 | `80.00%` |
| precision@7 | `13.81%` |
| recall@7 | `76.67%` |
| mrr@7 | `77.78%` |
| ndcg@7 | `75.49%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `94.2%` | `87.5%` | `100.0%` | `14650.7 ms` |
| simple | 22 | `72.7%` | `70.5%` | `68.7%` | `100.0%` | `72.7%` | `13459.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `73.9%` | `71.7%` | `70.1%` | `100.0%` | `73.9%` | `13432.2 ms` |
| medium | 7 | `100.0%` | `92.9%` | `93.3%` | `85.7%` | `100.0%` | `14909.5 ms` |
