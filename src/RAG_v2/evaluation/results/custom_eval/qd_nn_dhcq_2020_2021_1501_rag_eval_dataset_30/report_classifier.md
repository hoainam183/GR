# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:46:30
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `70.00%` |
| **precision@3** | `24.44%` |
| **recall@3** | `63.33%` |
| **mrr@3** | `60.00%` |
| **ndcg@3** | `58.03%` |
| **hit@5** | `70.00%` |
| **precision@5** | `16.00%` |
| **recall@5** | `66.67%` |
| **mrr@5** | `60.00%` |
| **ndcg@5** | `59.61%` |
| **hit@7** | `70.00%` |
| **precision@7** | `11.43%` |
| **recall@7** | `66.67%` |
| **mrr@7** | `60.00%` |
| **ndcg@7** | `59.61%` |
| **Avg Total Latency** | `4558.2 ms` |
| **Avg Routing Latency** | `618.0 ms` |
| **Avg Retrieval Latency** | `3940.1 ms` |
| **Gemini Fallback Rate** | `20.00%` (`6` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `62.5%` | `62.5%` | `62.5%` | `50.0%` | `45.2%` | `54.2%` | `5646.2 ms` |
| **simple** | 22 | `72.7%` | `72.7%` | `72.7%` | `72.7%` | `64.8%` | `62.1%` | `4162.5 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `77.8%` | `77.8%` | `77.8%` | `77.8%` | `70.9%` | `68.5%` | `4267.0 ms` |
| **hard** | 1 | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `4105.9 ms` |
| **medium** | 11 | `63.6%` | `63.6%` | `63.6%` | `54.5%` | `46.6%` | `51.5%` | `5075.8 ms` |
