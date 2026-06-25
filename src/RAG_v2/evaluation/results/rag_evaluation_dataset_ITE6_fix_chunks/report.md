# RAG Evaluation Report (production config)

- **Date**: 2026-06-25 18:34:59
- **Total queries**: `30`
- **Avg latency**: `11366.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `3.33%` (1) |
| Answer relevance | `100.00%` |
| Completeness | `96.67%` |
| Correctness vs gold (correct) | `90.00%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `90.00%` |
| precision@3 | `34.44%` |
| recall@3 | `83.33%` |
| mrr@3 | `86.67%` |
| ndcg@3 | `82.05%` |
| hit@5 | `90.00%` |
| precision@5 | `20.67%` |
| recall@5 | `83.33%` |
| mrr@5 | `86.67%` |
| ndcg@5 | `82.84%` |
| hit@7 | `90.00%` |
| precision@7 | `14.77%` |
| recall@7 | `83.33%` |
| mrr@7 | `86.67%` |
| ndcg@7 | `84.21%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `75.0%` | `77.8%` | `100.0%` | `87.5%` | `11949.0 ms` |
| simple | 22 | `86.4%` | `86.4%` | `84.7%` | `95.5%` | `90.9%` | `11154.5 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `86.4%` | `86.4%` | `84.7%` | `95.5%` | `90.9%` | `11154.5 ms` |
| hard | 2 | `100.0%` | `75.0%` | `88.5%` | `100.0%` | `100.0%` | `12830.6 ms` |
| medium | 6 | `100.0%` | `75.0%` | `74.2%` | `100.0%` | `83.3%` | `11655.1 ms` |
