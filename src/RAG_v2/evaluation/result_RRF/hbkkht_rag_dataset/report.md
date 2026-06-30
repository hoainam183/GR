# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 11:15:09
- **Total queries**: `30`
- **Avg latency**: `11202.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `32.22%` |
| recall@3 | `85.00%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `83.61%` |
| hit@5 | `90.00%` |
| precision@5 | `20.00%` |
| recall@5 | `88.33%` |
| mrr@5 | `85.67%` |
| ndcg@5 | `84.90%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `88.33%` |
| mrr@7 | `85.67%` |
| ndcg@7 | `84.90%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `80.7%` | `100.0%` | `75.0%` | `12422.4 ms` |
| simple | 22 | `90.9%` | `90.9%` | `86.4%` | `90.9%` | `90.9%` | `10758.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `82.7%` | `91.3%` | `87.0%` | `10684.0 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `19120.8 ms` |
| medium | 6 | `100.0%` | `91.7%` | `90.9%` | `100.0%` | `83.3%` | `11868.4 ms` |
