# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 17:20:04
- **Total queries**: `30`
- **Avg latency**: `36180.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `83.33%` |
| Completeness | `66.67%` |
| Correctness vs gold (correct) | `36.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `63.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `60.00%` |
| precision@3 | `22.22%` |
| recall@3 | `60.00%` |
| mrr@3 | `48.33%` |
| ndcg@3 | `51.04%` |
| hit@5 | `66.67%` |
| precision@5 | `14.67%` |
| recall@5 | `65.00%` |
| mrr@5 | `50.00%` |
| ndcg@5 | `53.36%` |
| hit@7 | `70.00%` |
| precision@7 | `10.95%` |
| recall@7 | `68.33%` |
| mrr@7 | `50.48%` |
| ndcg@7 | `54.47%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `31.2%` | `27.3%` | `50.0%` | `0.0%` | `34931.9 ms` |
| simple | 22 | `77.3%` | `77.3%` | `62.8%` | `95.5%` | `50.0%` | `36635.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `77.3%` | `77.3%` | `62.8%` | `95.5%` | `50.0%` | `36635.0 ms` |
| medium | 8 | `37.5%` | `31.2%` | `27.3%` | `50.0%` | `0.0%` | `34931.9 ms` |
