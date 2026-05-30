# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:50:43
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `93.33%` |
| **precision@3** | `32.22%` |
| **recall@3** | `81.67%` |
| **mrr@3** | `81.11%` |
| **ndcg@3** | `76.85%` |
| **hit@5** | `100.00%` |
| **precision@5** | `23.33%` |
| **recall@5** | `93.33%` |
| **mrr@5** | `82.61%` |
| **ndcg@5** | `82.46%` |
| **hit@7** | `100.00%` |
| **precision@7** | `16.67%` |
| **recall@7** | `93.33%` |
| **mrr@7** | `82.61%` |
| **ndcg@7** | `82.46%` |
| **Avg Total Latency** | `4506.1 ms` |
| **Avg Routing Latency** | `164.0 ms` |
| **Avg Retrieval Latency** | `4342.1 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `100.0%` | `100.0%` | `75.0%` | `65.7%` | `78.1%` | `3977.3 ms` |
| **simple** | 22 | `95.5%` | `100.0%` | `100.0%` | `100.0%` | `88.5%` | `84.2%` | `4698.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 13 | `92.3%` | `100.0%` | `100.0%` | `100.0%` | `83.9%` | `78.5%` | `4640.5 ms` |
| **hard** | 4 | `75.0%` | `100.0%` | `100.0%` | `87.5%` | `69.8%` | `68.8%` | `4049.6 ms` |
| **medium** | 13 | `100.0%` | `100.0%` | `100.0%` | `88.5%` | `84.9%` | `91.0%` | `4512.3 ms` |
