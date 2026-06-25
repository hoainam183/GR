# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 15:16:09
- **Total queries**: `30`
- **Avg latency**: `13465.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `73.33%` |
| Hallucination rate | `20.00%` (6) |
| Answer relevance | `100.00%` |
| Completeness | `86.67%` |
| Correctness vs gold (correct) | `70.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `20.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `60.00%` |
| precision@3 | `20.00%` |
| recall@3 | `55.00%` |
| mrr@3 | `52.78%` |
| ndcg@3 | `50.77%` |
| hit@5 | `63.33%` |
| precision@5 | `12.67%` |
| recall@5 | `56.67%` |
| mrr@5 | `53.44%` |
| ndcg@5 | `51.56%` |
| hit@7 | `63.33%` |
| precision@7 | `9.05%` |
| recall@7 | `56.67%` |
| mrr@7 | `53.44%` |
| ndcg@7 | `51.56%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `50.0%` | `25.0%` | `26.0%` | `50.0%` | `62.5%` | `15930.7 ms` |
| simple | 22 | `68.2%` | `68.2%` | `60.9%` | `81.8%` | `72.7%` | `12569.0 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `68.2%` | `68.2%` | `60.9%` | `81.8%` | `72.7%` | `12569.0 ms` |
| medium | 8 | `50.0%` | `25.0%` | `26.0%` | `50.0%` | `62.5%` | `15930.7 ms` |
