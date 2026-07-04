# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 15:07:11
- **Total queries**: `30`
- **Avg latency**: `29633.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `100.00%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `96.67%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `100.00%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `33.33%` |
| recall@3 | `80.00%` |
| mrr@3 | `81.11%` |
| ndcg@3 | `78.82%` |
| hit@5 | `90.00%` |
| precision@5 | `21.33%` |
| recall@5 | `86.67%` |
| mrr@5 | `82.78%` |
| ndcg@5 | `81.69%` |
| hit@7 | `90.00%` |
| precision@7 | `15.24%` |
| recall@7 | `86.67%` |
| mrr@7 | `82.78%` |
| ndcg@7 | `81.69%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `93.8%` | `87.0%` | `100.0%` | `100.0%` | `32103.8 ms` |
| simple | 22 | `86.4%` | `84.1%` | `79.7%` | `100.0%` | `100.0%` | `28734.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `84.8%` | `80.6%` | `100.0%` | `100.0%` | `28521.2 ms` |
| medium | 7 | `100.0%` | `92.9%` | `85.2%` | `100.0%` | `100.0%` | `33287.1 ms` |
