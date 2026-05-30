# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:24:13
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `26`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `80.77%` |
| **precision@3** | `32.05%` |
| **recall@3** | `72.44%` |
| **mrr@3** | `76.92%` |
| **ndcg@3** | `71.90%` |
| **hit@5** | `80.77%` |
| **precision@5** | `21.54%` |
| **recall@5** | `76.92%` |
| **mrr@5** | `76.92%` |
| **ndcg@5** | `74.39%` |
| **hit@7** | `80.77%` |
| **precision@7** | `15.39%` |
| **recall@7** | `76.92%` |
| **mrr@7** | `76.92%` |
| **ndcg@7** | `74.39%` |
| **Avg Total Latency** | `4475.7 ms` |
| **Avg Routing Latency** | `139.4 ms` |
| **Avg Retrieval Latency** | `4336.3 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `75.0%` | `71.4%` | `81.2%` | `4328.8 ms` |
| **simple** | 18 | `77.8%` | `77.8%` | `77.8%` | `77.8%` | `75.7%` | `75.0%` | `4541.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 19 | `79.0%` | `79.0%` | `79.0%` | `79.0%` | `76.4%` | `76.3%` | `4550.2 ms` |
| **hard** | 2 | `50.0%` | `50.0%` | `50.0%` | `50.0%` | `47.3%` | `50.0%` | `4113.0 ms` |
| **medium** | 5 | `100.0%` | `100.0%` | `100.0%` | `80.0%` | `77.5%` | `90.0%` | `4337.6 ms` |
