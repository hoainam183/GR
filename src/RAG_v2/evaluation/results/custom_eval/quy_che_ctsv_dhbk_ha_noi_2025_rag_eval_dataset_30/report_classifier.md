# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:52:40
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `63.33%` |
| **precision@3** | `21.11%` |
| **recall@3** | `58.33%` |
| **mrr@3** | `55.56%` |
| **ndcg@3** | `54.15%` |
| **hit@5** | `63.33%` |
| **precision@5** | `12.67%` |
| **recall@5** | `58.33%` |
| **mrr@5** | `55.56%` |
| **ndcg@5** | `54.15%` |
| **hit@7** | `63.33%` |
| **precision@7** | `9.05%` |
| **recall@7** | `58.33%` |
| **mrr@7** | `55.56%` |
| **ndcg@7** | `54.15%` |
| **Avg Total Latency** | `3902.2 ms` |
| **Avg Routing Latency** | `161.7 ms` |
| **Avg Retrieval Latency** | `3740.5 ms` |
| **Gemini Fallback Rate** | `3.33%` (`1` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `75.0%` | `75.0%` | `56.2%` | `57.7%` | `68.8%` | `4112.0 ms` |
| **simple** | 22 | `59.1%` | `59.1%` | `59.1%` | `59.1%` | `52.9%` | `50.8%` | `3825.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 17 | `58.8%` | `58.8%` | `58.8%` | `58.8%` | `52.9%` | `51.0%` | `3725.7 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `50.0%` | `38.7%` | `50.0%` | `3960.6 ms` |
| **medium** | 12 | `66.7%` | `66.7%` | `66.7%` | `58.3%` | `57.1%` | `62.5%` | `4147.3 ms` |
