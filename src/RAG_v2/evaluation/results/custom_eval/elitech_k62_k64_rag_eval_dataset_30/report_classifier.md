# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:57:02
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `36.67%` |
| **precision@3** | `12.22%` |
| **recall@3** | `36.67%` |
| **mrr@3** | `25.00%` |
| **ndcg@3** | `28.05%` |
| **hit@5** | `40.00%` |
| **precision@5** | `8.00%` |
| **recall@5** | `40.00%` |
| **mrr@5** | `25.83%` |
| **ndcg@5** | `29.49%` |
| **hit@7** | `40.00%` |
| **precision@7** | `5.72%` |
| **recall@7** | `40.00%` |
| **mrr@7** | `25.83%` |
| **ndcg@7** | `29.49%` |
| **Avg Total Latency** | `4566.3 ms` |
| **Avg Routing Latency** | `268.3 ms` |
| **Avg Retrieval Latency** | `4298.1 ms` |
| **Gemini Fallback Rate** | `10.00%` (`3` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `12.5%` | `12.5%` | `12.5%` | `12.5%` | `7.9%` | `6.2%` | `4571.8 ms` |
| **simple** | 22 | `45.5%` | `50.0%` | `50.0%` | `50.0%` | `37.4%` | `33.0%` | `4564.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 19 | `36.8%` | `42.1%` | `42.1%` | `42.1%` | `31.3%` | `27.6%` | `4615.2 ms` |
| **medium** | 11 | `36.4%` | `36.4%` | `36.4%` | `36.4%` | `26.3%` | `22.7%` | `4482.0 ms` |
