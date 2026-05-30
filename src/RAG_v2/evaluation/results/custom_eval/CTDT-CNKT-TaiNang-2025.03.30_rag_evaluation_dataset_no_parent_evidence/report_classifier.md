# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:18:46
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `26`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `76.92%` |
| **precision@3** | `26.92%` |
| **recall@3** | `62.82%` |
| **mrr@3** | `47.43%` |
| **ndcg@3** | `47.11%` |
| **hit@5** | `80.77%` |
| **precision@5** | `18.46%` |
| **recall@5** | `69.87%` |
| **mrr@5** | `48.40%` |
| **ndcg@5** | `50.46%` |
| **hit@7** | `80.77%` |
| **precision@7** | `13.19%` |
| **recall@7** | `69.87%` |
| **mrr@7** | `48.40%` |
| **ndcg@7** | `50.46%` |
| **Avg Total Latency** | `3489.2 ms` |
| **Avg Routing Latency** | `214.7 ms` |
| **Avg Retrieval Latency** | `3274.6 ms` |
| **Gemini Fallback Rate** | `3.85%` (`1` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `58.3%` | `48.9%` | `58.3%` | `3710.6 ms` |
| **simple** | 18 | `72.2%` | `77.8%` | `77.8%` | `75.0%` | `51.2%` | `44.0%` | `3390.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `71.4%` | `78.6%` | `78.6%` | `78.6%` | `55.9%` | `48.2%` | `3523.3 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `3598.9 ms` |
| **medium** | 11 | `81.8%` | `81.8%` | `81.8%` | `56.1%` | `39.1%` | `43.9%` | `3435.9 ms` |
