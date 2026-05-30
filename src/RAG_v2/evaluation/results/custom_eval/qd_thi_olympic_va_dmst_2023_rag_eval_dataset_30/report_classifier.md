# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:50:43
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `76.67%` |
| **precision@3** | `32.22%` |
| **recall@3** | `73.89%` |
| **mrr@3** | `74.44%` |
| **ndcg@3** | `73.37%` |
| **hit@5** | `76.67%` |
| **precision@5** | `20.67%` |
| **recall@5** | `76.67%` |
| **mrr@5** | `74.44%` |
| **ndcg@5** | `74.76%` |
| **hit@7** | `76.67%` |
| **precision@7** | `14.76%` |
| **recall@7** | `76.67%` |
| **mrr@7** | `74.44%` |
| **ndcg@7** | `74.76%` |
| **Avg Total Latency** | `4393.1 ms` |
| **Avg Routing Latency** | `316.5 ms` |
| **Avg Retrieval Latency** | `4076.6 ms` |
| **Gemini Fallback Rate** | `20.00%` (`6` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `87.5%` | `80.4%` | `79.2%` | `4311.8 ms` |
| **simple** | 22 | `72.7%` | `72.7%` | `72.7%` | `72.7%` | `72.7%` | `72.7%` | `4422.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 13 | `76.9%` | `76.9%` | `76.9%` | `76.9%` | `76.9%` | `76.9%` | `4405.6 ms` |
| **hard** | 3 | `66.7%` | `66.7%` | `66.7%` | `66.7%` | `62.8%` | `66.7%` | `4006.8 ms` |
| **medium** | 14 | `78.6%` | `78.6%` | `78.6%` | `78.6%` | `75.3%` | `73.8%` | `4464.3 ms` |
