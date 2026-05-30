# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:22:17
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `26`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `69.23%` |
| **precision@3** | `23.07%` |
| **recall@3** | `67.31%` |
| **mrr@3** | `61.54%` |
| **ndcg@3** | `62.06%` |
| **hit@5** | `73.08%` |
| **precision@5** | `14.62%` |
| **recall@5** | `68.59%` |
| **mrr@5** | `62.31%` |
| **ndcg@5** | `62.76%` |
| **hit@7** | `73.08%` |
| **precision@7** | `10.44%` |
| **recall@7** | `68.59%` |
| **mrr@7** | `62.31%` |
| **ndcg@7** | `62.76%` |
| **Avg Total Latency** | `4375.3 ms` |
| **Avg Routing Latency** | `178.4 ms` |
| **Avg Retrieval Latency** | `4196.9 ms` |
| **Gemini Fallback Rate** | `7.69%` (`2` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `50.0%` | `62.5%` | `62.5%` | `47.9%` | `42.8%` | `46.2%` | `4052.0 ms` |
| **simple** | 18 | `77.8%` | `77.8%` | `77.8%` | `77.8%` | `71.6%` | `69.4%` | `4519.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `77.8%` | `77.8%` | `77.8%` | `77.8%` | `71.6%` | `69.4%` | `4519.0 ms` |
| **medium** | 8 | `50.0%` | `62.5%` | `62.5%` | `47.9%` | `42.8%` | `46.2%` | `4052.0 ms` |
