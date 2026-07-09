# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 14:06:29
- **Total queries**: `30`
- **Avg latency**: `22620.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `28.89%` |
| recall@3 | `83.33%` |
| mrr@3 | `83.33%` |
| ndcg@3 | `83.07%` |
| hit@5 | `96.67%` |
| precision@5 | `20.00%` |
| recall@5 | `93.33%` |
| mrr@5 | `86.67%` |
| ndcg@5 | `87.70%` |
| hit@7 | `96.67%` |
| precision@7 | `14.77%` |
| recall@7 | `95.00%` |
| mrr@7 | `86.67%` |
| ndcg@7 | `88.43%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `68.1%` | `87.5%` | `75.0%` | `19901.3 ms` |
| simple | 22 | `100.0%` | `100.0%` | `94.8%` | `100.0%` | `100.0%` | `23608.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `95.8%` | `95.8%` | `91.1%` | `95.8%` | `100.0%` | `22839.2 ms` |
| medium | 6 | `100.0%` | `83.3%` | `74.1%` | `100.0%` | `66.7%` | `21743.9 ms` |
