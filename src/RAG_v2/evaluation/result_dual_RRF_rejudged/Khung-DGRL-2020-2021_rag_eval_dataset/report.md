# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:21:03
- **Total queries**: `30`
- **Avg latency**: `27335.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `96.67%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `34.44%` |
| recall@3 | `83.33%` |
| mrr@3 | `78.33%` |
| ndcg@3 | `79.10%` |
| hit@5 | `93.33%` |
| precision@5 | `22.00%` |
| recall@5 | `88.33%` |
| mrr@5 | `79.83%` |
| ndcg@5 | `81.32%` |
| hit@7 | `93.33%` |
| precision@7 | `16.67%` |
| recall@7 | `91.67%` |
| mrr@7 | `79.83%` |
| ndcg@7 | `82.73%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `81.2%` | `71.3%` | `87.5%` | `87.5%` | `34391.4 ms` |
| simple | 22 | `90.9%` | `90.9%` | `85.0%` | `95.5%` | `90.9%` | `24769.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `90.0%` | `90.0%` | `85.3%` | `95.0%` | `90.0%` | `25531.6 ms` |
| hard | 1 | `100.0%` | `100.0%` | `69.3%` | `100.0%` | `100.0%` | `23901.8 ms` |
| medium | 9 | `100.0%` | `83.3%` | `73.8%` | `88.9%` | `88.9%` | `31724.2 ms` |
