# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 19:44:38
- **Total queries**: `50`
- **Avg latency**: `10419.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `92.00%` |
| Hallucination rate | `4.00%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `94.00%` |
| Correctness vs gold (correct) | `68.00%` |
| Correctness vs gold (partial) | `6.00%` |
| Correctness vs gold (incorrect) | `26.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `38.00%` |
| precision@3 | `12.67%` |
| recall@3 | `38.00%` |
| mrr@3 | `35.00%` |
| ndcg@3 | `35.79%` |
| hit@5 | `56.00%` |
| precision@5 | `11.20%` |
| recall@5 | `55.00%` |
| mrr@5 | `39.00%` |
| ndcg@5 | `42.77%` |
| hit@7 | `62.00%` |
| precision@7 | `8.86%` |
| recall@7 | `61.00%` |
| mrr@7 | `39.90%` |
| ndcg@7 | `44.81%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 12 | `33.3%` | `29.2%` | `17.3%` | `83.3%` | `58.3%` | `12196.8 ms` |
| simple | 38 | `63.2%` | `63.2%` | `50.8%` | `94.7%` | `71.0%` | `9857.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 38 | `63.2%` | `63.2%` | `50.8%` | `94.7%` | `71.0%` | `9857.6 ms` |
| hard | 1 | `0.0%` | `0.0%` | `0.0%` | `100.0%` | `0.0%` | `12968.2 ms` |
| medium | 11 | `36.4%` | `31.8%` | `18.9%` | `81.8%` | `63.6%` | `12126.6 ms` |
