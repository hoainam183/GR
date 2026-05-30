# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:56:59
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `80.00%` |
| **precision@3** | `27.78%` |
| **recall@3** | `76.67%` |
| **mrr@3** | `68.89%` |
| **ndcg@3** | `69.73%` |
| **hit@5** | `80.00%` |
| **precision@5** | `17.33%` |
| **recall@5** | `78.33%` |
| **mrr@5** | `68.89%` |
| **ndcg@5** | `70.52%` |
| **hit@7** | `80.00%` |
| **precision@7** | `12.38%` |
| **recall@7** | `78.33%` |
| **mrr@7** | `68.89%` |
| **ndcg@7** | `70.52%` |
| **Avg Total Latency** | `4395.4 ms` |
| **Avg Routing Latency** | `188.2 ms` |
| **Avg Retrieval Latency** | `4207.2 ms` |
| **Gemini Fallback Rate** | `6.67%` (`2` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `81.2%` | `70.7%` | `70.8%` | `4496.5 ms` |
| **simple** | 22 | `77.3%` | `77.3%` | `77.3%` | `77.3%` | `70.5%` | `68.2%` | `4358.6 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `80.0%` | `80.0%` | `80.0%` | `80.0%` | `72.5%` | `70.0%` | `4362.2 ms` |
| **medium** | 10 | `80.0%` | `80.0%` | `80.0%` | `75.0%` | `66.6%` | `66.7%` | `4461.7 ms` |
