# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:25:08
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `100.00%` |
| **precision@3** | `38.89%` |
| **recall@3** | `98.33%` |
| **mrr@3** | `91.67%` |
| **ndcg@3** | `92.50%` |
| **hit@5** | `100.00%` |
| **precision@5** | `23.33%` |
| **recall@5** | `98.33%` |
| **mrr@5** | `91.67%` |
| **ndcg@5** | `92.50%` |
| **hit@7** | `100.00%` |
| **precision@7** | `16.67%` |
| **recall@7** | `98.33%` |
| **mrr@7** | `91.67%` |
| **ndcg@7** | `92.50%` |
| **Avg Total Latency** | `3606.5 ms` |
| **Avg Routing Latency** | `121.6 ms` |
| **Avg Retrieval Latency** | `3484.9 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `93.8%` | `90.3%` | `93.8%` | `4193.2 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `93.3%` | `90.9%` | `3393.2 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `94.5%` | `92.5%` | `3386.1 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `3387.2 ms` |
| **medium** | 9 | `100.0%` | `100.0%` | `100.0%` | `94.4%` | `87.3%` | `88.9%` | `4120.8 ms` |
