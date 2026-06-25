# RAG Evaluation Report (production config)

- **Date**: 2026-06-24 22:41:03
- **Total queries**: `30`
- **Avg latency**: `14474.0 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `96.67%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `86.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `73.33%` |
| precision@3 | `25.55%` |
| recall@3 | `71.67%` |
| mrr@3 | `67.78%` |
| ndcg@3 | `68.56%` |
| hit@5 | `80.00%` |
| precision@5 | `18.00%` |
| recall@5 | `80.00%` |
| mrr@5 | `69.28%` |
| ndcg@5 | `73.69%` |
| hit@7 | `80.00%` |
| precision@7 | `12.86%` |
| recall@7 | `80.00%` |
| mrr@7 | `69.28%` |
| ndcg@7 | `74.88%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `100.0%` | `88.6%` | `100.0%` | `100.0%` | `17434.8 ms` |
| simple | 22 | `72.7%` | `72.7%` | `68.3%` | `90.9%` | `81.8%` | `13397.3 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `71.4%` | `71.4%` | `66.8%` | `90.5%` | `81.0%` | `12865.0 ms` |
| medium | 9 | `100.0%` | `100.0%` | `89.9%` | `100.0%` | `100.0%` | `18228.2 ms` |
