# RAG Evaluation Report (production config)

- **Date**: 2026-06-30 16:02:24
- **Total queries**: `30`
- **Avg latency**: `12952.3 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `93.33%` |
| Correctness vs gold (partial) | `6.67%` |
| Correctness vs gold (incorrect) | `0.00%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `93.33%` |
| precision@3 | `35.55%` |
| recall@3 | `86.67%` |
| mrr@3 | `90.00%` |
| ndcg@3 | `85.39%` |
| hit@5 | `93.33%` |
| precision@5 | `21.33%` |
| recall@5 | `86.67%` |
| mrr@5 | `90.00%` |
| ndcg@5 | `86.18%` |
| hit@7 | `93.33%` |
| precision@7 | `15.24%` |
| recall@7 | `86.67%` |
| mrr@7 | `90.00%` |
| ndcg@7 | `87.54%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `100.0%` | `75.0%` | `77.8%` | `87.5%` | `87.5%` | `13787.3 ms` |
| simple | 22 | `90.9%` | `90.9%` | `89.2%` | `95.5%` | `95.5%` | `12648.6 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 22 | `90.9%` | `90.9%` | `89.2%` | `95.5%` | `95.5%` | `12648.6 ms` |
| hard | 2 | `100.0%` | `75.0%` | `88.5%` | `100.0%` | `100.0%` | `12830.6 ms` |
| medium | 6 | `100.0%` | `75.0%` | `74.2%` | `83.3%` | `83.3%` | `14106.2 ms` |
