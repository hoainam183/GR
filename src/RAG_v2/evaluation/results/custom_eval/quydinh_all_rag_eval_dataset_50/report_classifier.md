# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 23:04:57
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `50`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `78.00%` |
| **precision@3** | `32.00%` |
| **recall@3** | `77.33%` |
| **mrr@3** | `74.00%` |
| **ndcg@3** | `74.22%` |
| **hit@5** | `78.00%` |
| **precision@5** | `19.20%` |
| **recall@5** | `77.33%` |
| **mrr@5** | `74.00%` |
| **ndcg@5** | `74.22%` |
| **hit@7** | `78.00%` |
| **precision@7** | `13.72%` |
| **recall@7** | `77.33%` |
| **mrr@7** | `74.00%` |
| **ndcg@7** | `74.22%` |
| **Avg Total Latency** | `4633.9 ms` |
| **Avg Routing Latency** | `252.3 ms` |
| **Avg Retrieval Latency** | `4381.6 ms` |
| **Gemini Fallback Rate** | `12.00%` (`6` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 15 | `86.7%` | `86.7%` | `86.7%` | `84.4%` | `82.0%` | `83.3%` | `5180.0 ms` |
| **simple** | 35 | `74.3%` | `74.3%` | `74.3%` | `74.3%` | `70.9%` | `70.0%` | `4399.8 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 28 | `64.3%` | `64.3%` | `64.3%` | `64.3%` | `60.0%` | `58.9%` | `4367.2 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `92.0%` | `100.0%` | `4004.0 ms` |
| **medium** | 21 | `95.2%` | `95.2%` | `95.2%` | `93.7%` | `92.3%` | `92.9%` | `5019.4 ms` |
