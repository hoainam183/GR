# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 11:12:13
- **Total queries**: `30`
- **Avg latency**: `15452.8 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `13.33%` (4) |
| Answer relevance | `100.00%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `73.33%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `23.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `56.67%` |
| precision@3 | `21.11%` |
| recall@3 | `55.00%` |
| mrr@3 | `47.22%` |
| ndcg@3 | `48.09%` |
| hit@5 | `63.33%` |
| precision@5 | `14.00%` |
| recall@5 | `61.67%` |
| mrr@5 | `48.89%` |
| ndcg@5 | `50.96%` |
| hit@7 | `70.00%` |
| precision@7 | `10.95%` |
| recall@7 | `68.33%` |
| mrr@7 | `49.92%` |
| ndcg@7 | `53.25%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `37.5%` | `31.2%` | `31.7%` | `62.5%` | `12.5%` | `16742.4 ms` |
| simple | 22 | `72.7%` | `72.7%` | `58.0%` | `90.9%` | `95.5%` | `14983.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `72.7%` | `72.7%` | `58.0%` | `90.9%` | `95.5%` | `14983.8 ms` |
| medium | 8 | `37.5%` | `31.2%` | `31.7%` | `62.5%` | `12.5%` | `16742.4 ms` |
