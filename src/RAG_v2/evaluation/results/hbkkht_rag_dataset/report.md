# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 12:28:15
- **Total queries**: `30`
- **Avg latency**: `11826.5 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `90.00%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `32.22%` |
| recall@3 | `88.33%` |
| mrr@3 | `82.78%` |
| ndcg@3 | `83.73%` |
| hit@5 | `93.33%` |
| precision@5 | `20.00%` |
| recall@5 | `90.00%` |
| mrr@5 | `83.44%` |
| ndcg@5 | `84.52%` |
| hit@7 | `93.33%` |
| precision@7 | `14.29%` |
| recall@7 | `90.00%` |
| mrr@7 | `83.44%` |
| ndcg@7 | `84.52%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `68.3%` | `87.5%` | `75.0%` | `14438.2 ms` |
| simple | 22 | `95.5%` | `95.5%` | `90.4%` | `90.9%` | `95.5%` | `10876.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `91.3%` | `91.3%` | `86.5%` | `91.3%` | `91.3%` | `11016.4 ms` |
| hard | 1 | `100.0%` | `50.0%` | `23.7%` | `0.0%` | `100.0%` | `14010.1 ms` |
| medium | 6 | `100.0%` | `91.7%` | `87.1%` | `100.0%` | `83.3%` | `14567.9 ms` |
