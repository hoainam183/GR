# RAG Evaluation Report (production config)

- **Date**: 2026-07-09 00:45:50
- **Total queries**: `30`
- **Avg latency**: `16261.4 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `16.67%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `40.00%` |
| precision@3 | `13.33%` |
| recall@3 | `38.33%` |
| mrr@3 | `38.33%` |
| ndcg@3 | `37.96%` |
| hit@5 | `76.67%` |
| precision@5 | `15.33%` |
| recall@5 | `71.67%` |
| mrr@5 | `47.00%` |
| ndcg@5 | `52.20%` |
| hit@7 | `80.00%` |
| precision@7 | `11.91%` |
| recall@7 | `76.67%` |
| mrr@7 | `47.56%` |
| ndcg@7 | `54.12%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `68.8%` | `46.7%` | `87.5%` | `87.5%` | `13990.3 ms` |
| simple | 22 | `72.7%` | `72.7%` | `54.2%` | `95.5%` | `72.7%` | `17087.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `73.9%` | `73.9%` | `53.7%` | `95.7%` | `73.9%` | `16924.6 ms` |
| medium | 7 | `85.7%` | `64.3%` | `47.2%` | `85.7%` | `85.7%` | `14082.6 ms` |
