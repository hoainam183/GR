# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:37:48
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `90.00%` |
| **precision@3** | `32.22%` |
| **recall@3** | `88.33%` |
| **mrr@3** | `86.67%` |
| **ndcg@3** | `85.98%` |
| **hit@5** | `90.00%` |
| **precision@5** | `19.33%` |
| **recall@5** | `88.33%` |
| **mrr@5** | `86.67%` |
| **ndcg@5** | `85.98%` |
| **hit@7** | `90.00%` |
| **precision@7** | `13.81%` |
| **recall@7** | `88.33%` |
| **mrr@7** | `86.67%` |
| **ndcg@7** | `85.98%` |
| **Avg Total Latency** | `4357.3 ms` |
| **Avg Routing Latency** | `129.5 ms` |
| **Avg Retrieval Latency** | `4227.8 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `93.8%` | `89.5%` | `93.8%` | `4189.8 ms` |
| **simple** | 22 | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `84.7%` | `84.1%` | `4418.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 22 | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `84.7%` | `84.1%` | `4418.3 ms` |
| **medium** | 8 | `100.0%` | `100.0%` | `100.0%` | `93.8%` | `89.5%` | `93.8%` | `4189.8 ms` |
