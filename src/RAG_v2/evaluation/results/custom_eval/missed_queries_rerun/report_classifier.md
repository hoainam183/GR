# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-29 18:22:30
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `575`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `13.74%` |
| **precision@3** | `4.81%` |
| **recall@3** | `6.93%` |
| **mrr@3** | `10.99%` |
| **ndcg@3** | `7.24%` |
| **hit@5** | `15.48%` |
| **precision@5** | `3.30%` |
| **recall@5** | `7.89%` |
| **mrr@5** | `11.39%` |
| **ndcg@5** | `7.73%` |
| **hit@7** | `15.48%` |
| **precision@7** | `2.36%` |
| **recall@7** | `7.89%` |
| **mrr@7** | `11.39%` |
| **ndcg@7** | `7.73%` |
| **Avg Total Latency** | `6128.7 ms` |
| **Avg Routing Latency** | `752.3 ms` |
| **Avg Retrieval Latency** | `5376.4 ms` |
| **Gemini Fallback Rate** | `13.04%` (`75` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 227 | `33.5%` | `37.9%` | `37.9%` | `18.9%` | `18.5%` | `27.8%` | `6983.6 ms` |
| **simple** | 348 | `0.9%` | `0.9%` | `0.9%` | `0.7%` | `0.7%` | `0.7%` | `5571.1 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 316 | `0.6%` | `0.6%` | `0.6%` | `0.5%` | `0.5%` | `0.6%` | `5336.3 ms` |
| **hard** | 19 | `63.2%` | `68.4%` | `68.4%` | `32.6%` | `33.1%` | `51.3%` | `9312.4 ms` |
| **medium** | 240 | `27.1%` | `30.8%` | `30.8%` | `15.7%` | `15.2%` | `22.4%` | `6920.0 ms` |
