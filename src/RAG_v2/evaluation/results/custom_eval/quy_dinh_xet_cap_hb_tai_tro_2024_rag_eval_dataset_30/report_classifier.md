# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 23:01:05
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `96.67%` |
| **precision@3** | `33.33%` |
| **recall@3** | `90.67%` |
| **mrr@3** | `94.44%` |
| **ndcg@3** | `91.27%` |
| **hit@5** | `96.67%` |
| **precision@5** | `20.00%` |
| **recall@5** | `90.67%` |
| **mrr@5** | `94.44%` |
| **ndcg@5** | `91.05%` |
| **hit@7** | `96.67%` |
| **precision@7** | `14.29%` |
| **recall@7** | `90.67%` |
| **mrr@7** | `94.44%` |
| **ndcg@7** | `91.05%` |
| **Avg Total Latency** | `3975.5 ms` |
| **Avg Routing Latency** | `224.3 ms` |
| **Avg Retrieval Latency** | `3751.2 ms` |
| **Gemini Fallback Rate** | `10.00%` (`3` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `77.5%` | `78.9%` | `91.7%` | `4249.5 ms` |
| **simple** | 22 | `95.5%` | `95.5%` | `95.5%` | `95.5%` | `95.5%` | `95.5%` | `3875.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `92.9%` | `92.9%` | `92.9%` | `92.9%` | `92.9%` | `92.9%` | `3909.4 ms` |
| **hard** | 2 | `100.0%` | `100.0%` | `100.0%` | `60.0%` | `54.5%` | `66.7%` | `4861.6 ms` |
| **medium** | 14 | `100.0%` | `100.0%` | `100.0%` | `92.9%` | `94.5%` | `100.0%` | `3915.0 ms` |
