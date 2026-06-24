# RAG Evaluation Report (production config)

- **Date**: 2026-06-21 16:00:55
- **Total queries**: `30`
- **Avg latency**: `11196.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `86.67%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `93.33%` |
| Completeness | `90.00%` |
| Correctness vs gold (correct) | `76.67%` |
| Correctness vs gold (partial) | `10.00%` |
| Correctness vs gold (incorrect) | `13.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `83.33%` |
| precision@3 | `30.00%` |
| recall@3 | `83.33%` |
| mrr@3 | `78.33%` |
| ndcg@3 | `79.37%` |
| hit@5 | `86.67%` |
| precision@5 | `18.67%` |
| recall@5 | `85.00%` |
| mrr@5 | `79.00%` |
| ndcg@5 | `80.17%` |
| hit@7 | `86.67%` |
| precision@7 | `13.34%` |
| recall@7 | `85.00%` |
| mrr@7 | `79.00%` |
| ndcg@7 | `80.17%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `75.0%` | `68.8%` | `64.5%` | `87.5%` | `62.5%` | `13464.8 ms` |
| simple | 22 | `90.9%` | `90.9%` | `85.9%` | `86.4%` | `81.8%` | `10371.8 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 23 | `87.0%` | `87.0%` | `82.1%` | `87.0%` | `78.3%` | `10533.4 ms` |
| hard | 1 | `100.0%` | `50.0%` | `23.7%` | `0.0%` | `100.0%` | `14010.1 ms` |
| medium | 6 | `83.3%` | `83.3%` | `82.0%` | `100.0%` | `66.7%` | `13270.0 ms` |
