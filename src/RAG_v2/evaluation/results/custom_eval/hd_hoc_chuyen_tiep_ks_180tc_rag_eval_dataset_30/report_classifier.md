# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:59:10
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `76.67%` |
| **precision@3** | `27.78%` |
| **recall@3** | `73.33%` |
| **mrr@3** | `76.67%` |
| **ndcg@3** | `74.09%` |
| **hit@5** | `76.67%` |
| **precision@5** | `16.67%` |
| **recall@5** | `73.33%` |
| **mrr@5** | `76.67%` |
| **ndcg@5** | `74.09%` |
| **hit@7** | `76.67%` |
| **precision@7** | `11.91%` |
| **recall@7** | `73.33%` |
| **mrr@7** | `76.67%` |
| **ndcg@7** | `74.09%` |
| **Avg Total Latency** | `4275.8 ms` |
| **Avg Routing Latency** | `93.1 ms` |
| **Avg Retrieval Latency** | `4182.7 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `75.0%` | `75.0%` | `62.5%` | `65.3%` | `75.0%` | `4256.2 ms` |
| **simple** | 22 | `77.3%` | `77.3%` | `77.3%` | `77.3%` | `77.3%` | `77.3%` | `4282.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `75.0%` | `75.0%` | `75.0%` | `75.0%` | `75.0%` | `75.0%` | `4260.9 ms` |
| **medium** | 10 | `80.0%` | `80.0%` | `80.0%` | `70.0%` | `72.3%` | `80.0%` | `4305.6 ms` |
