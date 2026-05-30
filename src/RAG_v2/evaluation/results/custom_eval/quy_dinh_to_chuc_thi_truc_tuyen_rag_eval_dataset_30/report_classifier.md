# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:59:06
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `86.67%` |
| **precision@3** | `34.44%` |
| **recall@3** | `85.00%` |
| **mrr@3** | `86.67%` |
| **ndcg@3** | `85.38%` |
| **hit@5** | `86.67%` |
| **precision@5** | `21.33%` |
| **recall@5** | `86.67%` |
| **mrr@5** | `86.67%` |
| **ndcg@5** | `86.26%` |
| **hit@7** | `86.67%` |
| **precision@7** | `15.24%` |
| **recall@7** | `86.67%` |
| **mrr@7** | `86.67%` |
| **ndcg@7** | `86.26%` |
| **Avg Total Latency** | `4232.4 ms` |
| **Avg Routing Latency** | `391.5 ms` |
| **Avg Retrieval Latency** | `3840.9 ms` |
| **Gemini Fallback Rate** | `33.33%` (`10` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `87.5%` | `86.0%` | `87.5%` | `4140.7 ms` |
| **simple** | 22 | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `4265.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 22 | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `4265.7 ms` |
| **medium** | 8 | `87.5%` | `87.5%` | `87.5%` | `87.5%` | `86.0%` | `87.5%` | `4140.7 ms` |
