# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:35:37
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `90.00%` |
| **precision@3** | `36.67%` |
| **recall@3** | `88.33%` |
| **mrr@3** | `88.33%` |
| **ndcg@3** | `86.94%` |
| **hit@5** | `90.00%` |
| **precision@5** | `22.00%` |
| **recall@5** | `88.33%` |
| **mrr@5** | `88.33%` |
| **ndcg@5** | `86.94%` |
| **hit@7** | `90.00%` |
| **precision@7** | `15.72%` |
| **recall@7** | `88.33%` |
| **mrr@7** | `88.33%` |
| **ndcg@7** | `86.94%` |
| **Avg Total Latency** | `4387.4 ms` |
| **Avg Routing Latency** | `194.4 ms` |
| **Avg Retrieval Latency** | `4193.0 ms` |
| **Gemini Fallback Rate** | `3.33%` (`1` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `81.2%` | `80.7%` | `87.5%` | `4989.7 ms` |
| **simple** | 22 | `90.9%` | `90.9%` | `90.9%` | `90.9%` | `89.2%` | `88.6%` | `4168.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 23 | `91.3%` | `91.3%` | `91.3%` | `89.1%` | `87.7%` | `89.1%` | `4124.4 ms` |
| **medium** | 7 | `85.7%` | `85.7%` | `85.7%` | `85.7%` | `84.6%` | `85.7%` | `5251.5 ms` |
