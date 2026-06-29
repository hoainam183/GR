# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 13:44:11
- **Total queries**: `30`
- **Avg latency**: `18101.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `83.33%` |
| Hallucination rate | `16.67%` (5) |
| Answer relevance | `80.00%` |
| Completeness | `80.00%` |
| Correctness vs gold (correct) | `66.67%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `30.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `31.11%` |
| recall@3 | `78.33%` |
| mrr@3 | `78.33%` |
| ndcg@3 | `77.21%` |
| hit@5 | `86.67%` |
| precision@5 | `20.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `80.00%` |
| ndcg@5 | `79.76%` |
| hit@7 | `86.67%` |
| precision@7 | `14.76%` |
| recall@7 | `83.33%` |
| mrr@7 | `80.00%` |
| ndcg@7 | `80.49%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `66.2%` | `37.5%` | `25.0%` | `17343.5 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.7%` | `100.0%` | `81.8%` | `18377.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.7%` | `100.0%` | `81.8%` | `18377.3 ms` |
| hard | 2 | `100.0%` | `75.0%` | `63.2%` | `50.0%` | `50.0%` | `18913.8 ms` |
| medium | 6 | `83.3%` | `75.0%` | `67.2%` | `33.3%` | `16.7%` | `16820.0 ms` |
