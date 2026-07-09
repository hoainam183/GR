# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 10:54:14
- **Total queries**: `30`
- **Avg latency**: `22303.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `70.00%` |
| precision@3 | `25.55%` |
| recall@3 | `68.33%` |
| mrr@3 | `68.33%` |
| ndcg@3 | `67.96%` |
| hit@5 | `90.00%` |
| precision@5 | `19.33%` |
| recall@5 | `88.33%` |
| mrr@5 | `73.17%` |
| ndcg@5 | `76.42%` |
| hit@7 | `90.00%` |
| precision@7 | `13.81%` |
| recall@7 | `88.33%` |
| mrr@7 | `73.17%` |
| ndcg@7 | `76.42%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `72.7%` | `100.0%` | `87.5%` | `23385.3 ms` |
| simple | 22 | `90.9%` | `90.9%` | `77.8%` | `95.5%` | `90.9%` | `21910.4 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `76.3%` | `95.7%` | `91.3%` | `22373.6 ms` |
| medium | 7 | `85.7%` | `78.6%` | `77.0%` | `100.0%` | `85.7%` | `22074.0 ms` |
