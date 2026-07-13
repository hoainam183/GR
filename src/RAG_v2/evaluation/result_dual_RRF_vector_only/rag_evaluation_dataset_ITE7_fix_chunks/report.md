# RAG Evaluation Report (production config)

- **Date**: 2026-07-13 22:04:35
- **Total queries**: `30`
- **Avg latency**: `18101.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `93.33%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `34.44%` |
| recall@3 | `83.33%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `82.59%` |
| hit@5 | `86.67%` |
| precision@5 | `20.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `85.00%` |
| ndcg@5 | `82.59%` |
| hit@7 | `86.67%` |
| precision@7 | `14.76%` |
| recall@7 | `83.33%` |
| mrr@7 | `85.00%` |
| ndcg@7 | `83.32%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `76.8%` | `37.5%` | `62.5%` | `17343.5 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.7%` | `100.0%` | `81.8%` | `18377.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.7%` | `100.0%` | `81.8%` | `18377.3 ms` |
| hard | 2 | `100.0%` | `75.0%` | `80.7%` | `50.0%` | `50.0%` | `18913.8 ms` |
| medium | 6 | `83.3%` | `75.0%` | `75.5%` | `33.3%` | `66.7%` | `16820.0 ms` |
