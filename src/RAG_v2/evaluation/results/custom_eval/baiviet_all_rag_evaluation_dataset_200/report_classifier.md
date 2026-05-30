# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:36:31
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `170`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `40.59%` |
| **precision@3** | `14.51%` |
| **recall@3** | `36.47%` |
| **mrr@3** | `31.76%` |
| **ndcg@3** | `31.57%` |
| **hit@5** | `44.71%` |
| **precision@5** | `10.47%` |
| **recall@5** | `41.76%` |
| **mrr@5** | `32.71%` |
| **ndcg@5** | `34.07%` |
| **hit@7** | `44.71%` |
| **precision@7** | `7.48%` |
| **recall@7** | `41.76%` |
| **mrr@7** | `32.71%` |
| **ndcg@7** | `34.07%` |
| **Avg Total Latency** | `4340.7 ms` |
| **Avg Routing Latency** | `443.1 ms` |
| **Avg Retrieval Latency** | `3897.6 ms` |
| **Gemini Fallback Rate** | `32.94%` (`56` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 50 | `38.0%` | `46.0%` | `46.0%` | `36.0%` | `27.8%` | `29.2%` | `4640.9 ms` |
| **simple** | 120 | `41.7%` | `44.2%` | `44.2%` | `44.2%` | `36.7%` | `34.2%` | `4215.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 120 | `41.7%` | `44.2%` | `44.2%` | `44.2%` | `36.7%` | `34.2%` | `4215.7 ms` |
| **medium** | 50 | `38.0%` | `46.0%` | `46.0%` | `36.0%` | `27.8%` | `29.2%` | `4640.9 ms` |
