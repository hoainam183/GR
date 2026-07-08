# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 16:20:29
- **Total queries**: `30`
- **Avg latency**: `29601.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `73.33%` |
| precision@3 | `28.89%` |
| recall@3 | `70.00%` |
| mrr@3 | `69.44%` |
| ndcg@3 | `68.33%` |
| hit@5 | `86.67%` |
| precision@5 | `20.00%` |
| recall@5 | `83.33%` |
| mrr@5 | `72.78%` |
| ndcg@5 | `77.58%` |
| hit@7 | `90.00%` |
| precision@7 | `15.24%` |
| recall@7 | `86.67%` |
| mrr@7 | `73.33%` |
| ndcg@7 | `79.59%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `88.1%` | `75.0%` | `87.5%` | `20803.4 ms` |
| simple | 22 | `86.4%` | `86.4%` | `73.7%` | `100.0%` | `90.9%` | `32800.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `74.9%` | `100.0%` | `91.3%` | `33417.4 ms` |
| medium | 7 | `85.7%` | `71.4%` | `86.5%` | `71.4%` | `85.7%` | `17063.2 ms` |
