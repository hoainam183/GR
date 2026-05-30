# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:27:26
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `26`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `88.46%` |
| **precision@3** | `35.90%` |
| **recall@3** | `84.62%` |
| **mrr@3** | `78.21%` |
| **ndcg@3** | `78.06%` |
| **hit@5** | `88.46%` |
| **precision@5** | `22.31%` |
| **recall@5** | `86.54%` |
| **mrr@5** | `78.21%` |
| **ndcg@5** | `79.07%` |
| **hit@7** | `88.46%` |
| **precision@7** | `15.94%` |
| **recall@7** | `86.54%` |
| **mrr@7** | `78.21%` |
| **ndcg@7** | `79.07%` |
| **Avg Total Latency** | `5315.1 ms` |
| **Avg Routing Latency** | `210.0 ms` |
| **Avg Retrieval Latency** | `5105.1 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `81.2%` | `76.3%` | `81.2%` | `5253.3 ms` |
| **simple** | 18 | `88.9%` | `88.9%` | `88.9%` | `88.9%` | `80.3%` | `76.8%` | `5342.5 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `88.9%` | `88.9%` | `88.9%` | `88.9%` | `80.3%` | `76.8%` | `5342.5 ms` |
| **medium** | 8 | `87.5%` | `87.5%` | `87.5%` | `81.2%` | `76.3%` | `81.2%` | `5253.3 ms` |
