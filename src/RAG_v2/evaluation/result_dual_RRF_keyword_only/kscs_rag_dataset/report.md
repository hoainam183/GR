# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 13:34:57
- **Total queries**: `30`
- **Avg latency**: `8839.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `73.33%` |
| precision@3 | `25.55%` |
| recall@3 | `71.67%` |
| mrr@3 | `69.44%` |
| ndcg@3 | `69.79%` |
| hit@5 | `86.67%` |
| precision@5 | `18.67%` |
| recall@5 | `85.00%` |
| mrr@5 | `72.44%` |
| ndcg@5 | `77.00%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `90.00%` |
| mrr@7 | `72.92%` |
| ndcg@7 | `80.03%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `83.2%` | `100.0%` | `87.5%` | `10419.9 ms` |
| simple | 22 | `81.8%` | `81.8%` | `74.8%` | `90.9%` | `86.4%` | `8265.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `81.0%` | `81.0%` | `73.6%` | `90.5%` | `85.7%` | `8133.4 ms` |
| medium | 9 | `100.0%` | `94.4%` | `85.0%` | `100.0%` | `88.9%` | `10488.3 ms` |
