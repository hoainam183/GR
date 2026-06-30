# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 12:33:57
- **Total queries**: `30`
- **Avg latency**: `16414.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `32.22%` |
| recall@3 | `80.00%` |
| mrr@3 | `80.00%` |
| ndcg@3 | `77.00%` |
| hit@5 | `86.67%` |
| precision@5 | `19.33%` |
| recall@5 | `80.00%` |
| mrr@5 | `80.00%` |
| ndcg@5 | `77.00%` |
| hit@7 | `86.67%` |
| precision@7 | `13.81%` |
| recall@7 | `80.00%` |
| mrr@7 | `80.00%` |
| ndcg@7 | `77.00%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `62.5%` | `60.5%` | `100.0%` | `87.5%` | `15231.9 ms` |
| simple | 22 | `86.4%` | `86.4%` | `83.0%` | `100.0%` | `90.9%` | `16844.7 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `85.0%` | `85.0%` | `83.2%` | `100.0%` | `90.0%` | `16836.4 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `100.0%` | `100.0%` | `18978.5 ms` |
| medium | 9 | `88.9%` | `66.7%` | `64.2%` | `100.0%` | `88.9%` | `15192.3 ms` |
