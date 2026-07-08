# RAG Evaluation Report (production config)

- **Date**: 2026-07-08 20:11:46
- **Total queries**: `30`
- **Avg latency**: `17209.6 ms`

## E2E generation quality

| Metric | Score |
| :--- | :---: |
| Groundedness (Faithfulness) | `93.33%` |
| Hallucination rate | `6.67%` (2) |
| Answer relevance | `100.00%` |
| Completeness | `93.33%` |
| Correctness vs gold (correct) | `96.67%` |
| Correctness vs gold (partial) | `0.00%` |
| Correctness vs gold (incorrect) | `3.33%` |

## Retrieval metrics (averaged)

| Metric | Score |
| :--- | :---: |
| hit@3 | `76.67%` |
| precision@3 | `25.55%` |
| recall@3 | `65.00%` |
| mrr@3 | `73.33%` |
| ndcg@3 | `65.18%` |
| hit@5 | `90.00%` |
| precision@5 | `20.00%` |
| recall@5 | `83.33%` |
| mrr@5 | `76.67%` |
| ndcg@5 | `73.56%` |
| hit@7 | `90.00%` |
| precision@7 | `14.77%` |
| recall@7 | `85.00%` |
| mrr@7 | `76.67%` |
| ndcg@7 | `74.24%` |

## Breakdown by question type

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| multi_hop | 8 | `87.5%` | `62.5%` | `63.5%` | `75.0%` | `100.0%` | `11982.9 ms` |
| simple | 22 | `90.9%` | `90.9%` | `77.2%` | `100.0%` | `95.5%` | `19110.2 ms` |

## Breakdown by difficulty

| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| easy | 20 | `95.0%` | `95.0%` | `81.8%` | `100.0%` | `95.0%` | `19087.9 ms` |
| hard | 1 | `100.0%` | `100.0%` | `87.7%` | `100.0%` | `100.0%` | `10935.9 ms` |
| medium | 9 | `77.8%` | `55.6%` | `53.8%` | `77.8%` | `100.0%` | `13732.5 ms` |
