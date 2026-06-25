# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 18:30:56
- **Total queries**: `30`
- **Avg latency**: `11566.9 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `86.67%` |
| precision@3 | `31.11%` |
| recall@3 | `86.67%` |
| mrr@3 | `81.67%` |
| ndcg@3 | `82.71%` |
| hit@5 | `90.00%` |
| precision@5 | `19.33%` |
| recall@5 | `88.33%` |
| mrr@5 | `82.33%` |
| ndcg@5 | `83.50%` |
| hit@7 | `90.00%` |
| precision@7 | `13.81%` |
| recall@7 | `88.33%` |
| mrr@7 | `82.33%` |
| ndcg@7 | `83.50%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `64.5%` | `87.5%` | `62.5%` | `13464.8 ms` |
| simple | 22 | `95.5%` | `95.5%` | `90.4%` | `90.9%` | `95.5%` | `10876.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `86.5%` | `91.3%` | `91.3%` | `11016.4 ms` |
| hard | 1 | `100.0%` | `50.0%` | `23.7%` | `0.0%` | `100.0%` | `14010.1 ms` |
| medium | 6 | `83.3%` | `83.3%` | `82.0%` | `100.0%` | `66.7%` | `13270.0 ms` |
