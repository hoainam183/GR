# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:20:43
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `170`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `21.76%` |
| **precision@3** | `7.65%` |
| **recall@3** | `19.12%` |
| **mrr@3** | `14.80%` |
| **ndcg@3** | `14.99%` |
| **hit@5** | `28.24%` |
| **precision@5** | `6.47%` |
| **recall@5** | `26.18%` |
| **mrr@5** | `16.39%` |
| **ndcg@5** | `18.22%` |
| **hit@7** | `28.24%` |
| **precision@7** | `4.62%` |
| **recall@7** | `26.18%` |
| **mrr@7** | `16.39%` |
| **ndcg@7** | `18.22%` |
| **Avg Total Latency** | `4920.1 ms` |
| **Avg Routing Latency** | `385.2 ms` |
| **Avg Retrieval Latency** | `4534.9 ms` |
| **Gemini Fallback Rate** | `22.94%` (`39` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 50 | `22.0%` | `28.0%` | `28.0%` | `21.0%` | `16.0%` | `17.2%` | `5190.8 ms` |
| **simple** | 120 | `21.7%` | `28.3%` | `28.3%` | `28.3%` | `19.1%` | `16.1%` | `4807.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 120 | `21.7%` | `28.3%` | `28.3%` | `28.3%` | `19.1%` | `16.1%` | `4807.3 ms` |
| **medium** | 50 | `22.0%` | `28.0%` | `28.0%` | `21.0%` | `16.0%` | `17.2%` | `5190.8 ms` |
