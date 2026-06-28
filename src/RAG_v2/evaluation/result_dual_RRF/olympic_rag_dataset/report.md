# RAG Evaluation Report (production config)

- **Date**: 2026-06-28 20:28:52
- **Total queries**: `30`
- **Avg latency**: `30982.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `90.00%` |
| Completeness | `70.00%` |
| Correctness vs gold (correct) | `20.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `80.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `31.11%` |
| recall@3 | `85.00%` |
| mrr@3 | `80.00%` |
| ndcg@3 | `81.14%` |
| hit@5 | `90.00%` |
| precision@5 | `19.33%` |
| recall@5 | `88.33%` |
| mrr@5 | `80.83%` |
| ndcg@5 | `82.58%` |
| hit@7 | `90.00%` |
| precision@7 | `13.81%` |
| recall@7 | `88.33%` |
| mrr@7 | `80.83%` |
| ndcg@7 | `82.58%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `76.0%` | `100.0%` | `12.5%` | `33848.5 ms` |
| simple | 22 | `90.9%` | `90.9%` | `85.0%` | `90.9%` | `22.7%` | `29940.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `85.6%` | `91.3%` | `21.7%` | `31046.9 ms` |
| medium | 7 | `85.7%` | `78.6%` | `72.6%` | `100.0%` | `14.3%` | `30772.9 ms` |
