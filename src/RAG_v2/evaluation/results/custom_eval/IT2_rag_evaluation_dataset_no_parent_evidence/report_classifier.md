# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:20:23
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `26`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `84.62%` |
| **precision@3** | `29.48%` |
| **recall@3** | `75.64%` |
| **mrr@3** | `73.08%` |
| **ndcg@3** | `69.04%` |
| **hit@5** | `84.62%` |
| **precision@5** | `19.23%` |
| **recall@5** | `78.85%` |
| **mrr@5** | `73.08%` |
| **ndcg@5** | `70.83%` |
| **hit@7** | `84.62%` |
| **precision@7** | `13.74%` |
| **recall@7** | `78.85%` |
| **mrr@7** | `73.08%` |
| **ndcg@7** | `70.83%` |
| **Avg Total Latency** | `3759.2 ms` |
| **Avg Routing Latency** | `103.9 ms` |
| **Avg Retrieval Latency** | `3655.3 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `62.5%` | `62.5%` | `62.5%` | `43.8%` | `45.4%` | `62.5%` | `4089.9 ms` |
| **simple** | 18 | `94.4%` | `94.4%` | `94.4%` | `94.4%` | `82.1%` | `77.8%` | `3612.2 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `94.4%` | `94.4%` | `94.4%` | `94.4%` | `82.1%` | `77.8%` | `3612.2 ms` |
| **hard** | 2 | `100.0%` | `100.0%` | `100.0%` | `41.7%` | `54.1%` | `100.0%` | `4256.4 ms` |
| **medium** | 6 | `50.0%` | `50.0%` | `50.0%` | `44.5%` | `42.5%` | `50.0%` | `4034.5 ms` |
