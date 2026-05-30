# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:44:13
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `80.00%` |
| **precision@3** | `30.00%` |
| **recall@3** | `75.56%` |
| **mrr@3** | `78.33%` |
| **ndcg@3** | `75.14%` |
| **hit@5** | `80.00%` |
| **precision@5** | `18.67%` |
| **recall@5** | `77.22%` |
| **mrr@5** | `78.33%` |
| **ndcg@5** | `75.93%` |
| **hit@7** | `80.00%` |
| **precision@7** | `13.34%` |
| **recall@7** | `77.22%` |
| **mrr@7** | `78.33%` |
| **ndcg@7** | `75.93%` |
| **Avg Total Latency** | `4321.5 ms` |
| **Avg Routing Latency** | `143.7 ms` |
| **Avg Retrieval Latency** | `4177.8 ms` |
| **Gemini Fallback Rate** | `3.33%` (`1` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `75.0%` | `75.0%` | `64.6%` | `64.4%` | `75.0%` | `4489.0 ms` |
| **simple** | 22 | `81.8%` | `81.8%` | `81.8%` | `81.8%` | `80.1%` | `79.5%` | `4260.6 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 17 | `88.2%` | `88.2%` | `88.2%` | `88.2%` | `86.1%` | `85.3%` | `4152.2 ms` |
| **hard** | 3 | `100.0%` | `100.0%` | `100.0%` | `88.9%` | `89.5%` | `100.0%` | `4511.2 ms` |
| **medium** | 10 | `60.0%` | `60.0%` | `60.0%` | `55.0%` | `54.6%` | `60.0%` | `4552.4 ms` |
