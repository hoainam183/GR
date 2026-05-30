# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 23:12:19
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `100`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `81.00%` |
| **precision@3** | `31.00%` |
| **recall@3** | `74.50%` |
| **mrr@3** | `70.17%` |
| **ndcg@3** | `68.68%` |
| **hit@5** | `85.00%` |
| **precision@5** | `20.60%` |
| **recall@5** | `80.50%` |
| **mrr@5** | `71.07%` |
| **ndcg@5** | `71.49%` |
| **hit@7** | `85.00%` |
| **precision@7** | `14.72%` |
| **recall@7** | `80.50%` |
| **mrr@7** | `71.07%` |
| **ndcg@7** | `71.49%` |
| **Avg Total Latency** | `4423.1 ms` |
| **Avg Routing Latency** | `241.7 ms` |
| **Avg Retrieval Latency** | `4181.5 ms` |
| **Gemini Fallback Rate** | `13.00%` (`13` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 30 | `83.3%` | `90.0%` | `90.0%` | `75.0%` | `65.9%` | `71.7%` | `4346.8 ms` |
| **simple** | 70 | `80.0%` | `82.9%` | `82.9%` | `82.9%` | `73.9%` | `70.8%` | `4455.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 70 | `80.0%` | `82.9%` | `82.9%` | `82.9%` | `73.9%` | `70.8%` | `4455.9 ms` |
| **medium** | 30 | `83.3%` | `90.0%` | `90.0%` | `75.0%` | `65.9%` | `71.7%` | `4346.8 ms` |
