# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:23:20
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `100.00%` |
| **precision@3** | `34.44%` |
| **recall@3** | `100.00%` |
| **mrr@3** | `94.44%` |
| **ndcg@3** | `95.87%` |
| **hit@5** | `100.00%` |
| **precision@5** | `20.67%` |
| **recall@5** | `100.00%` |
| **mrr@5** | `94.44%` |
| **ndcg@5** | `95.87%` |
| **hit@7** | `100.00%` |
| **precision@7** | `14.77%` |
| **recall@7** | `100.00%` |
| **mrr@7** | `94.44%` |
| **ndcg@7** | `95.87%` |
| **Avg Total Latency** | `5232.8 ms` |
| **Avg Routing Latency** | `229.9 ms` |
| **Avg Retrieval Latency** | `5002.9 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `5508.5 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `94.4%` | `92.4%` | `5132.6 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 22 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `94.4%` | `92.4%` | `5132.6 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `5510.3 ms` |
| **medium** | 7 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `5508.2 ms` |
