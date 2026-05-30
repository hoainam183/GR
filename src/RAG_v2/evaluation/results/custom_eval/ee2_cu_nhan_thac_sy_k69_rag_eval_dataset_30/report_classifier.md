# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:54:45
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `80.00%` |
| **precision@3** | `27.78%` |
| **recall@3** | `74.44%` |
| **mrr@3** | `76.67%` |
| **ndcg@3** | `73.19%` |
| **hit@5** | `86.67%` |
| **precision@5** | `18.67%` |
| **recall@5** | `82.78%` |
| **mrr@5** | `78.33%` |
| **ndcg@5** | `76.94%` |
| **hit@7** | `86.67%` |
| **precision@7** | `13.34%` |
| **recall@7** | `82.78%` |
| **mrr@7** | `78.33%` |
| **ndcg@7** | `76.94%` |
| **Avg Total Latency** | `4264.3 ms` |
| **Avg Routing Latency** | `195.1 ms` |
| **Avg Retrieval Latency** | `4069.2 ms` |
| **Gemini Fallback Rate** | `3.33%` (`1` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `72.9%` | `74.5%` | `87.5%` | `4488.4 ms` |
| **simple** | 22 | `77.3%` | `86.4%` | `86.4%` | `86.4%` | `77.8%` | `75.0%` | `4182.8 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `88.9%` | `88.9%` | `88.9%` | `88.9%` | `84.8%` | `83.3%` | `4141.2 ms` |
| **hard** | 2 | `100.0%` | `100.0%` | `100.0%` | `66.7%` | `73.5%` | `100.0%` | `3810.4 ms` |
| **medium** | 10 | `60.0%` | `80.0%` | `80.0%` | `75.0%` | `63.5%` | `65.0%` | `4576.7 ms` |
