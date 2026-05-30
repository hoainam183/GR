# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:29:01
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `100.00%` |
| **precision@3** | `36.66%` |
| **recall@3** | `92.22%` |
| **mrr@3** | `98.33%` |
| **ndcg@3** | `93.10%` |
| **hit@5** | `100.00%` |
| **precision@5** | `22.67%` |
| **recall@5** | `93.89%` |
| **mrr@5** | `98.33%` |
| **ndcg@5** | `93.98%` |
| **hit@7** | `100.00%` |
| **precision@7** | `16.19%` |
| **recall@7** | `93.89%` |
| **mrr@7** | `98.33%` |
| **ndcg@7** | `93.98%` |
| **Avg Total Latency** | `3146.8 ms` |
| **Avg Routing Latency** | `83.6 ms` |
| **Avg Retrieval Latency** | `3063.3 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `77.1%` | `77.4%` | `93.8%` | `3179.2 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `3135.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 19 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `3207.4 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `66.7%` | `70.4%` | `100.0%` | `2707.1 ms` |
| **medium** | 10 | `100.0%` | `100.0%` | `100.0%` | `85.0%` | `84.9%` | `95.0%` | `3075.7 ms` |
