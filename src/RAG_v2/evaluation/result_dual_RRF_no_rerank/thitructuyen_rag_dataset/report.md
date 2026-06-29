# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 18:42:09
- **Total queries**: `30`
- **Avg latency**: `19294.1 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `63.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `26.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `50.00%` |
| precision@3 | `18.89%` |
| recall@3 | `48.89%` |
| mrr@3 | `46.11%` |
| ndcg@3 | `46.50%` |
| hit@5 | `53.33%` |
| precision@5 | `12.67%` |
| recall@5 | `53.33%` |
| mrr@5 | `46.94%` |
| ndcg@5 | `48.61%` |
| hit@7 | `63.33%` |
| precision@7 | `10.48%` |
| recall@7 | `63.33%` |
| mrr@7 | `48.45%` |
| ndcg@7 | `52.02%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `62.5%` | `62.5%` | `58.2%` | `100.0%` | `50.0%` | `21333.1 ms` |
| simple | 22 | `50.0%` | `50.0%` | `45.1%` | `90.9%` | `68.2%` | `18552.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `50.0%` | `50.0%` | `45.1%` | `90.9%` | `68.2%` | `18552.6 ms` |
| medium | 8 | `62.5%` | `62.5%` | `58.2%` | `100.0%` | `50.0%` | `21333.1 ms` |
