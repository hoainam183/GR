# RAG Evaluation Report (production config)

- **Date**: 2026-06-24 20:03:02
- **Total queries**: `30`
- **Avg latency**: `10746.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `31.11%` |
| recall@3 | `81.67%` |
| mrr@3 | `81.67%` |
| ndcg@3 | `80.28%` |
| hit@5 | `83.33%` |
| precision@5 | `18.67%` |
| recall@5 | `81.67%` |
| mrr@5 | `81.67%` |
| ndcg@5 | `80.28%` |
| hit@7 | `83.33%` |
| precision@7 | `13.34%` |
| recall@7 | `81.67%` |
| mrr@7 | `81.67%` |
| ndcg@7 | `80.28%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `80.7%` | `100.0%` | `75.0%` | `12422.4 ms` |
| simple | 22 | `81.8%` | `81.8%` | `80.1%` | `90.9%` | `81.8%` | `10136.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `78.3%` | `78.3%` | `76.7%` | `91.3%` | `78.3%` | `10089.3 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `19120.8 ms` |
| medium | 6 | `100.0%` | `91.7%` | `90.9%` | `100.0%` | `83.3%` | `11868.4 ms` |
