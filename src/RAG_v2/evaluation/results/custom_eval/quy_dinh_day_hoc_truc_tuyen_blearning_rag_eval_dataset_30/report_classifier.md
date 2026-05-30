# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:54:47
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `76.67%` |
| **precision@3** | `27.78%` |
| **recall@3** | `76.67%` |
| **mrr@3** | `76.67%` |
| **ndcg@3** | `76.67%` |
| **hit@5** | `76.67%` |
| **precision@5** | `16.67%` |
| **recall@5** | `76.67%` |
| **mrr@5** | `76.67%` |
| **ndcg@5** | `76.67%` |
| **hit@7** | `76.67%` |
| **precision@7** | `11.91%` |
| **recall@7** | `76.67%` |
| **mrr@7** | `76.67%` |
| **ndcg@7** | `76.67%` |
| **Avg Total Latency** | `4220.7 ms` |
| **Avg Routing Latency** | `214.2 ms` |
| **Avg Retrieval Latency** | `4006.5 ms` |
| **Gemini Fallback Rate** | `10.00%` (`3` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `75.0%` | `75.0%` | `75.0%` | `75.0%` | `75.0%` | `4374.8 ms` |
| **simple** | 22 | `77.3%` | `77.3%` | `77.3%` | `77.3%` | `77.3%` | `77.3%` | `4164.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 16 | `68.8%` | `68.8%` | `68.8%` | `68.8%` | `68.8%` | `68.8%` | `4241.7 ms` |
| **medium** | 14 | `85.7%` | `85.7%` | `85.7%` | `85.7%` | `85.7%` | `85.7%` | `4196.7 ms` |
