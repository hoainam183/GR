# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:40:31
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `100.00%` |
| **precision@3** | `34.44%` |
| **recall@3** | `96.67%` |
| **mrr@3** | `63.33%` |
| **ndcg@3** | `71.51%` |
| **hit@5** | `100.00%` |
| **precision@5** | `21.33%` |
| **recall@5** | `98.33%` |
| **mrr@5** | `63.33%` |
| **ndcg@5** | `72.39%` |
| **hit@7** | `100.00%` |
| **precision@7** | `15.24%` |
| **recall@7** | `98.33%` |
| **mrr@7** | `63.33%` |
| **ndcg@7** | `72.39%` |
| **Avg Total Latency** | `3991.4 ms` |
| **Avg Routing Latency** | `186.8 ms` |
| **Avg Retrieval Latency** | `3804.6 ms` |
| **Gemini Fallback Rate** | `10.00%` (`3` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `93.8%` | `61.1%` | `50.0%` | `4142.8 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `76.5%` | `68.2%` | `3936.4 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 21 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `75.4%` | `66.7%` | `3939.2 ms` |
| **medium** | 9 | `100.0%` | `100.0%` | `100.0%` | `94.4%` | `65.4%` | `55.6%` | `4113.2 ms` |
