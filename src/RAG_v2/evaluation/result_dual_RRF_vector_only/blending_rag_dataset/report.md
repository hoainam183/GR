# RAG Evaluation Report (production config)

- **Date**: 2026-06-27 13:57:25
- **Total queries**: `30`
- **Avg latency**: `11117.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `83.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `32.22%` |
| recall@3 | `78.33%` |
| mrr@3 | `75.56%` |
| ndcg@3 | `75.38%` |
| hit@5 | `80.00%` |
| precision@5 | `19.33%` |
| recall@5 | `78.33%` |
| mrr@5 | `75.56%` |
| ndcg@5 | `76.66%` |
| hit@7 | `80.00%` |
| precision@7 | `13.81%` |
| recall@7 | `78.33%` |
| mrr@7 | `75.56%` |
| ndcg@7 | `77.21%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `87.5%` | `100.0%` | `62.5%` | `13313.7 ms` |
| simple | 22 | `77.3%` | `77.3%` | `72.7%` | `90.9%` | `90.9%` | `10319.1 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `78.3%` | `78.3%` | `73.9%` | `91.3%` | `91.3%` | `10450.6 ms` |
| medium | 7 | `85.7%` | `78.6%` | `85.7%` | `100.0%` | `57.1%` | `13309.5 ms` |
