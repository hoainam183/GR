# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:40:03
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `86.67%` |
| **precision@3** | `30.00%` |
| **recall@3** | `85.00%` |
| **mrr@3** | `71.67%` |
| **ndcg@3** | `74.04%` |
| **hit@5** | `86.67%` |
| **precision@5** | `18.00%` |
| **recall@5** | `85.00%` |
| **mrr@5** | `71.67%` |
| **ndcg@5** | `74.04%` |
| **hit@7** | `86.67%` |
| **precision@7** | `12.86%` |
| **recall@7** | `85.00%` |
| **mrr@7** | `71.67%` |
| **ndcg@7** | `74.04%` |
| **Avg Total Latency** | `4477.0 ms` |
| **Avg Routing Latency** | `147.3 ms` |
| **Avg Retrieval Latency** | `4329.7 ms` |
| **Gemini Fallback Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `81.2%` | `77.0%` | `81.2%` | `5156.5 ms` |
| **simple** | 22 | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `72.9%` | `68.2%` | `4229.8 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 22 | `86.4%` | `86.4%` | `86.4%` | `86.4%` | `72.9%` | `68.2%` | `4229.8 ms` |
| **medium** | 8 | `87.5%` | `87.5%` | `87.5%` | `81.2%` | `77.0%` | `81.2%` | `5156.5 ms` |
