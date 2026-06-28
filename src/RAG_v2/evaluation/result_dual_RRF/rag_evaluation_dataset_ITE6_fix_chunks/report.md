# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 21:50:29
- **Total queries**: `30`
- **Avg latency**: `24693.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `10.00%` (3) |
| Answer relevance | `93.33%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `66.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `30.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `33.33%` |
| recall@3 | `81.67%` |
| mrr@3 | `81.11%` |
| ndcg@3 | `79.09%` |
| hit@5 | `90.00%` |
| precision@5 | `21.33%` |
| recall@5 | `85.00%` |
| mrr@5 | `81.94%` |
| ndcg@5 | `80.85%` |
| hit@7 | `90.00%` |
| precision@7 | `15.24%` |
| recall@7 | `85.00%` |
| mrr@7 | `81.94%` |
| ndcg@7 | `80.85%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `81.2%` | `71.9%` | `75.0%` | `37.5%` | `32835.4 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.1%` | `95.5%` | `77.3%` | `21732.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.1%` | `95.5%` | `77.3%` | `21732.1 ms` |
| hard | 2 | `100.0%` | `75.0%` | `45.8%` | `50.0%` | `50.0%` | `30807.3 ms` |
| medium | 6 | `100.0%` | `83.3%` | `80.7%` | `83.3%` | `33.3%` | `33511.5 ms` |
