# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 23:24:30
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `170`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `74.12%` |
| **precision@3** | `29.80%` |
| **recall@3** | `70.29%` |
| **mrr@3** | `57.16%` |
| **ndcg@3** | `59.12%` |
| **hit@5** | `79.41%` |
| **precision@5** | `19.88%` |
| **recall@5** | `77.65%` |
| **mrr@5** | `58.36%` |
| **ndcg@5** | `62.37%` |
| **hit@7** | `79.41%` |
| **precision@7** | `14.20%` |
| **recall@7** | `77.65%` |
| **mrr@7** | `58.36%` |
| **ndcg@7** | `62.37%` |
| **Avg Total Latency** | `4299.7 ms` |
| **Avg Routing Latency** | `211.4 ms` |
| **Avg Retrieval Latency** | `4088.3 ms` |
| **Gemini Fallback Rate** | `11.18%` (`19` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 50 | `78.0%` | `80.0%` | `80.0%` | `74.0%` | `65.6%` | `66.7%` | `4669.3 ms` |
| **simple** | 120 | `72.5%` | `79.2%` | `79.2%` | `79.2%` | `61.0%` | `54.9%` | `4145.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 120 | `72.5%` | `79.2%` | `79.2%` | `79.2%` | `61.0%` | `54.9%` | `4145.7 ms` |
| **medium** | 50 | `78.0%` | `80.0%` | `80.0%` | `74.0%` | `65.6%` | `66.7%` | `4669.3 ms` |
