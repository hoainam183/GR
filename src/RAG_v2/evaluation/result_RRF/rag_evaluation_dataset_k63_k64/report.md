# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 16:46:38
- **Total queries**: `30`
- **Avg latency**: `13366.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `70.00%` |
| Hallucination rate | `23.33%` (7) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `70.00%` |
| Correctness vs gold (partial) | `13.33%` |
| Correctness vs gold (incorrect) | `16.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `53.33%` |
| precision@3 | `18.89%` |
| recall@3 | `53.33%` |
| mrr@3 | `51.67%` |
| ndcg@3 | `52.10%` |
| hit@5 | `60.00%` |
| precision@5 | `12.67%` |
| recall@5 | `60.00%` |
| mrr@5 | `53.33%` |
| ndcg@5 | `54.97%` |
| hit@7 | `60.00%` |
| precision@7 | `9.05%` |
| recall@7 | `60.00%` |
| mrr@7 | `53.33%` |
| ndcg@7 | `54.97%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `12.5%` | `12.5%` | `12.5%` | `75.0%` | `62.5%` | `14896.3 ms` |
| simple | 22 | `77.3%` | `77.3%` | `70.4%` | `68.2%` | `72.7%` | `12810.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `77.3%` | `77.3%` | `70.4%` | `68.2%` | `72.7%` | `12810.2 ms` |
| medium | 8 | `12.5%` | `12.5%` | `12.5%` | `75.0%` | `62.5%` | `14896.3 ms` |
