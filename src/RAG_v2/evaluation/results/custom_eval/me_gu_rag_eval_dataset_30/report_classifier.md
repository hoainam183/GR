# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:33:26
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `80.00%` |
| **precision@3** | `32.22%` |
| **recall@3** | `77.22%` |
| **mrr@3** | `76.67%` |
| **ndcg@3** | `75.68%` |
| **hit@5** | `80.00%` |
| **precision@5** | `20.67%` |
| **recall@5** | `80.00%` |
| **mrr@5** | `76.67%` |
| **ndcg@5** | `77.08%` |
| **hit@7** | `80.00%` |
| **precision@7** | `14.76%` |
| **recall@7** | `80.00%` |
| **mrr@7** | `76.67%` |
| **ndcg@7** | `77.08%` |
| **Avg Total Latency** | `4940.0 ms` |
| **Avg Routing Latency** | `265.5 ms` |
| **Avg Retrieval Latency** | `4674.5 ms` |
| **Gemini Fallback Rate** | `10.00%` (`3` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `75.0%` | `75.0%` | `75.0%` | `64.0%` | `62.5%` | `4537.9 ms` |
| **simple** | 22 | `81.8%` | `81.8%` | `81.8%` | `81.8%` | `81.8%` | `81.8%` | `5086.2 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 11 | `81.8%` | `81.8%` | `81.8%` | `81.8%` | `81.8%` | `81.8%` | `5162.7 ms` |
| **hard** | 3 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `75.7%` | `66.7%` | `4469.2 ms` |
| **medium** | 16 | `75.0%` | `75.0%` | `75.0%` | `75.0%` | `74.1%` | `75.0%` | `4875.2 ms` |
