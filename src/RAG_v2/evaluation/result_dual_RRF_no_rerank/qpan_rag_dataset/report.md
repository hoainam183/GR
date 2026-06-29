# RAG Evaluation Report (production config)

- **Date**: 2026-06-29 16:36:46
- **Total queries**: `30`
- **Avg latency**: `17281.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `3.33%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `28.89%` |
| recall@3 | `81.67%` |
| mrr@3 | `70.56%` |
| ndcg@3 | `73.12%` |
| hit@5 | `93.33%` |
| precision@5 | `19.33%` |
| recall@5 | `90.00%` |
| mrr@5 | `72.89%` |
| ndcg@5 | `76.79%` |
| hit@7 | `100.00%` |
| precision@7 | `15.24%` |
| recall@7 | `98.33%` |
| mrr@7 | `73.84%` |
| ndcg@7 | `79.74%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `75.0%` | `56.8%` | `75.0%` | `75.0%` | `18970.5 ms` |
| simple | 22 | `95.5%` | `95.5%` | `84.1%` | `100.0%` | `100.0%` | `16666.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 24 | `91.7%` | `91.7%` | `79.1%` | `100.0%` | `95.8%` | `16942.7 ms` |
| medium | 6 | `100.0%` | `83.3%` | `67.4%` | `66.7%` | `83.3%` | `18633.9 ms` |
