# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 17:34:29
- **Total queries**: `30`
- **Avg latency**: `20209.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `28.89%` |
| recall@3 | `81.67%` |
| mrr@3 | `83.33%` |
| ndcg@3 | `81.78%` |
| hit@5 | `86.67%` |
| precision@5 | `18.67%` |
| recall@5 | `85.00%` |
| mrr@5 | `84.17%` |
| ndcg@5 | `83.54%` |
| hit@7 | `90.00%` |
| precision@7 | `13.81%` |
| recall@7 | `88.33%` |
| mrr@7 | `84.72%` |
| ndcg@7 | `84.72%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `75.8%` | `87.5%` | `62.5%` | `24715.5 ms` |
| simple | 22 | `86.4%` | `86.4%` | `86.4%` | `100.0%` | `81.8%` | `18570.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `87.5%` | `87.5%` | `87.5%` | `100.0%` | `83.3%` | `18912.4 ms` |
| medium | 6 | `83.3%` | `75.0%` | `67.7%` | `83.3%` | `50.0%` | `25397.8 ms` |
