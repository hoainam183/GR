# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:38:31
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `100.00%` |
| **precision@3** | `37.78%` |
| **recall@3** | `91.11%` |
| **mrr@3** | `93.89%` |
| **ndcg@3** | `89.60%` |
| **hit@5** | `100.00%` |
| **precision@5** | `25.33%` |
| **recall@5** | `96.67%` |
| **mrr@5** | `93.89%` |
| **ndcg@5** | `92.64%` |
| **hit@7** | `100.00%` |
| **precision@7** | `18.10%` |
| **recall@7** | `96.67%` |
| **mrr@7** | `93.89%` |
| **ndcg@7** | `92.64%` |
| **Avg Total Latency** | `3979.6 ms` |
| **Avg Routing Latency** | `482.7 ms` |
| **Avg Retrieval Latency** | `3496.9 ms` |
| **Gemini Fallback Rate** | `43.33%` (`13` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `87.5%` | `78.6%` | `85.4%` | `3990.1 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `97.7%` | `97.0%` | `3975.8 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `97.2%` | `96.3%` | `3997.9 ms` |
| **medium** | 12 | `100.0%` | `100.0%` | `100.0%` | `91.7%` | `85.8%` | `90.3%` | `3952.1 ms` |
