# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 23:26:43
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `90.00%` |
| **precision@3** | `34.44%` |
| **recall@3** | `90.00%` |
| **mrr@3** | `87.78%` |
| **ndcg@3** | `88.33%` |
| **hit@5** | `90.00%` |
| **precision@5** | `20.67%` |
| **recall@5** | `90.00%` |
| **mrr@5** | `87.78%` |
| **ndcg@5** | `88.33%` |
| **hit@7** | `90.00%` |
| **precision@7** | `14.77%` |
| **recall@7** | `90.00%` |
| **mrr@7** | `87.78%` |
| **ndcg@7** | `88.33%` |
| **Avg Total Latency** | `4435.3 ms` |
| **Avg Routing Latency** | `124.5 ms` |
| **Avg Retrieval Latency** | `4310.8 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `87.5%` | `87.5%` | `87.5%` | `4426.2 ms` |
| **simple** | 22 | `90.9%` | `90.9%` | `90.9%` | `90.9%` | `88.6%` | `87.9%` | `4438.6 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `95.0%` | `95.0%` | `95.0%` | `95.0%` | `92.5%` | `91.7%` | `4440.5 ms` |
| **medium** | 10 | `80.0%` | `80.0%` | `80.0%` | `80.0%` | `80.0%` | `80.0%` | `4424.9 ms` |
