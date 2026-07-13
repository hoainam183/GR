# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 21:57:45
- **Total queries**: `30`
- **Avg latency**: `24852.7 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `13.33%` |
| Hallucination rate | `86.67%` (26) |
| Answer relevance | `96.67%` |
| Completeness | `80.00%` |
| Correctness vs gold (correct) | `83.33%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `31.11%` |
| recall@3 | `83.33%` |
| mrr@3 | `73.33%` |
| ndcg@3 | `74.66%` |
| hit@5 | `86.67%` |
| precision@5 | `19.33%` |
| recall@5 | `85.00%` |
| mrr@5 | `73.33%` |
| ndcg@5 | `75.54%` |
| hit@7 | `86.67%` |
| precision@7 | `13.81%` |
| recall@7 | `85.00%` |
| mrr@7 | `73.33%` |
| ndcg@7 | `75.54%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `73.5%` | `0.0%` | `75.0%` | `31464.4 ms` |
| simple | 22 | `86.4%` | `86.4%` | `76.3%` | `18.2%` | `86.4%` | `22448.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `82.6%` | `82.6%` | `73.0%` | `17.4%` | `82.6%` | `22881.6 ms` |
| hard | 1 | `100.0%` | `100.0%` | `65.1%` | `0.0%` | `100.0%` | `41255.4 ms` |
| medium | 6 | `100.0%` | `91.7%` | `87.1%` | `0.0%` | `83.3%` | `29675.2 ms` |
