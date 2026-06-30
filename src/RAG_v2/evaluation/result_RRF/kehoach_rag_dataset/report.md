# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 11:16:27
- **Total queries**: `50`
- **Avg latency**: `17637.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `92.00%` |
| Hallucination rate | `4.00%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `94.00%` |
| Correctness vs gold (correct) | `80.00%` |
| Correctness vs gold (partial) | `4.00%` |
| Correctness vs gold (incorrect) | `16.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `62.00%` |
| precision@3 | `22.00%` |
| recall@3 | `62.00%` |
| mrr@3 | `52.67%` |
| ndcg@3 | `55.09%` |
| hit@5 | `66.00%` |
| precision@5 | `14.00%` |
| recall@5 | `66.00%` |
| mrr@5 | `53.57%` |
| ndcg@5 | `56.73%` |
| hit@7 | `68.00%` |
| precision@7 | `10.29%` |
| recall@7 | `67.00%` |
| mrr@7 | `53.85%` |
| ndcg@7 | `57.14%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `58.3%` | `58.3%` | `50.1%` | `83.3%` | `83.3%` | `19602.3 ms` |
| simple | 38 | `68.4%` | `68.4%` | `58.8%` | `94.7%` | `79.0%` | `17016.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `68.4%` | `68.4%` | `58.8%` | `94.7%` | `79.0%` | `17016.5 ms` |
| hard | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `10393.4 ms` |
| medium | 11 | `54.5%` | `54.5%` | `45.6%` | `81.8%` | `81.8%` | `20439.5 ms` |
