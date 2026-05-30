# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:42:03
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `90.00%` |
| **precision@3** | `32.22%` |
| **recall@3** | `86.67%` |
| **mrr@3** | `81.67%` |
| **ndcg@3** | `81.75%` |
| **hit@5** | `90.00%` |
| **precision@5** | `19.33%` |
| **recall@5** | `86.67%` |
| **mrr@5** | `81.67%` |
| **ndcg@5** | `81.75%` |
| **hit@7** | `90.00%` |
| **precision@7** | `13.81%` |
| **recall@7** | `86.67%` |
| **mrr@7** | `81.67%` |
| **ndcg@7** | `81.75%` |
| **Avg Total Latency** | `4029.9 ms` |
| **Avg Routing Latency** | `114.5 ms` |
| **Avg Retrieval Latency** | `3915.4 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `75.0%` | `75.0%` | `62.5%` | `57.9%` | `62.5%` | `4416.5 ms` |
| **simple** | 22 | `95.5%` | `95.5%` | `95.5%` | `95.5%` | `90.4%` | `88.6%` | `3889.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `95.0%` | `95.0%` | `95.0%` | `95.0%` | `91.3%` | `90.0%` | `3860.9 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `50.0%` | `61.3%` | `100.0%` | `4740.1 ms` |
| **medium** | 9 | `77.8%` | `77.8%` | `77.8%` | `72.2%` | `62.8%` | `61.1%` | `4326.7 ms` |
