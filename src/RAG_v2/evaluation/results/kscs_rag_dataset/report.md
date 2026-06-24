# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 16:54:54
- **Total queries**: `30`
- **Avg latency**: `20160.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `96.67%` |
| Hallucination rate | `0.00%` (0) |
| Answer relevance | `100.00%` |
| Completeness | `100.00%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `6.67%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `80.00%` |
| precision@3 | `27.78%` |
| recall@3 | `78.33%` |
| mrr@3 | `71.11%` |
| ndcg@3 | `72.77%` |
| hit@5 | `83.33%` |
| precision@5 | `18.00%` |
| recall@5 | `81.67%` |
| mrr@5 | `71.94%` |
| ndcg@5 | `74.53%` |
| hit@7 | `90.00%` |
| precision@7 | `14.29%` |
| recall@7 | `90.00%` |
| mrr@7 | `72.98%` |
| ndcg@7 | `79.73%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `81.2%` | `63.7%` | `87.5%` | `100.0%` | `21697.9 ms` |
| simple | 22 | `81.8%` | `81.8%` | `78.5%` | `100.0%` | `90.9%` | `19601.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 21 | `81.0%` | `81.0%` | `77.4%` | `100.0%` | `90.5%` | `18771.4 ms` |
| medium | 9 | `88.9%` | `83.3%` | `67.7%` | `88.9%` | `100.0%` | `23401.1 ms` |
