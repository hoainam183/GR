# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 16:10:44
- **Total queries**: `30`
- **Avg latency**: `12196.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `83.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `10.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `32.22%` |
| recall@3 | `80.00%` |
| mrr@3 | `85.00%` |
| ndcg@3 | `80.01%` |
| hit@5 | `86.67%` |
| precision@5 | `19.33%` |
| recall@5 | `80.00%` |
| mrr@5 | `85.00%` |
| ndcg@5 | `80.01%` |
| hit@7 | `86.67%` |
| precision@7 | `13.81%` |
| recall@7 | `80.00%` |
| mrr@7 | `85.00%` |
| ndcg@7 | `80.74%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `62.5%` | `67.2%` | `75.0%` | `87.5%` | `14113.9 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.7%` | `100.0%` | `81.8%` | `11499.9 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.7%` | `100.0%` | `81.8%` | `11499.9 ms` |
| hard | 2 | `100.0%` | `75.0%` | `80.7%` | `100.0%` | `50.0%` | `11847.5 ms` |
| medium | 6 | `83.3%` | `58.3%` | `62.6%` | `66.7%` | `100.0%` | `14869.3 ms` |
