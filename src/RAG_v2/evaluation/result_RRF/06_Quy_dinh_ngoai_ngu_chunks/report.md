# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 22:11:57
- **Total queries**: `30`
- **Avg latency**: `16912.2 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `86.67%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `83.33%` |
| Correctness vs gold (correct) | `66.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `23.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `60.00%` |
| precision@3 | `22.22%` |
| recall@3 | `56.67%` |
| mrr@3 | `48.33%` |
| ndcg@3 | `49.11%` |
| hit@5 | `66.67%` |
| precision@5 | `14.67%` |
| recall@5 | `63.33%` |
| mrr@5 | `50.00%` |
| ndcg@5 | `51.98%` |
| hit@7 | `73.33%` |
| precision@7 | `11.43%` |
| recall@7 | `70.00%` |
| mrr@7 | `51.03%` |
| ndcg@7 | `54.28%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `50.0%` | `37.5%` | `35.5%` | `75.0%` | `0.0%` | `18691.3 ms` |
| simple | 22 | `72.7%` | `72.7%` | `58.0%` | `90.9%` | `90.9%` | `16265.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `72.7%` | `72.7%` | `58.0%` | `90.9%` | `90.9%` | `16265.3 ms` |
| medium | 8 | `50.0%` | `37.5%` | `35.5%` | `75.0%` | `0.0%` | `18691.3 ms` |
