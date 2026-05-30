# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:30:58
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `26`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `11.54%` |
| **precision@3** | `3.85%` |
| **recall@3** | `11.54%` |
| **mrr@3** | `9.62%` |
| **ndcg@3** | `10.12%` |
| **hit@5** | `11.54%` |
| **precision@5** | `2.31%` |
| **recall@5** | `11.54%` |
| **mrr@5** | `9.62%` |
| **ndcg@5** | `10.12%` |
| **hit@7** | `11.54%` |
| **precision@7** | `1.65%` |
| **recall@7** | `11.54%` |
| **mrr@7** | `9.62%` |
| **ndcg@7** | `10.12%` |
| **Avg Total Latency** | `4503.4 ms` |
| **Avg Routing Latency** | `100.1 ms` |
| **Avg Retrieval Latency** | `4403.3 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `4353.0 ms` |
| **simple** | 18 | `16.7%` | `16.7%` | `16.7%` | `16.7%` | `14.6%` | `13.9%` | `4570.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `16.7%` | `16.7%` | `16.7%` | `16.7%` | `14.6%` | `13.9%` | `4570.3 ms` |
| **medium** | 8 | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `4353.0 ms` |
