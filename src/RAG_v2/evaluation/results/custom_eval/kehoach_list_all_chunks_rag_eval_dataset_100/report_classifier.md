# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:06:46
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `100`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `44.00%` |
| **precision@3** | `16.33%` |
| **recall@3** | `42.00%` |
| **mrr@3** | `39.00%` |
| **ndcg@3** | `38.83%` |
| **hit@5** | `45.00%` |
| **precision@5** | `10.20%` |
| **recall@5** | `43.50%` |
| **mrr@5** | `39.25%` |
| **ndcg@5** | `39.53%` |
| **hit@7** | `45.00%` |
| **precision@7** | `7.29%` |
| **recall@7** | `43.50%` |
| **mrr@7** | `39.25%` |
| **ndcg@7** | `39.53%` |
| **Avg Total Latency** | `4555.2 ms` |
| **Avg Routing Latency** | `327.3 ms` |
| **Avg Retrieval Latency** | `4227.9 ms` |
| **Gemini Fallback Rate** | `14.00%` (`14` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 30 | `50.0%` | `50.0%` | `50.0%` | `45.0%` | `41.5%` | `43.9%` | `4676.0 ms` |
| **simple** | 70 | `41.4%` | `42.9%` | `42.9%` | `42.9%` | `38.7%` | `37.3%` | `4503.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 51 | `52.9%` | `54.9%` | `54.9%` | `54.9%` | `49.9%` | `48.2%` | `4586.6 ms` |
| **hard** | 4 | `25.0%` | `25.0%` | `25.0%` | `25.0%` | `25.0%` | `25.0%` | `4606.3 ms` |
| **medium** | 45 | `35.6%` | `35.6%` | `35.6%` | `32.2%` | `29.0%` | `30.4%` | `4515.1 ms` |
