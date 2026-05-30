# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 22:48:31
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `93.33%` |
| **precision@3** | `31.11%` |
| **recall@3** | `86.67%` |
| **mrr@3** | `89.44%` |
| **ndcg@3** | `85.28%` |
| **hit@5** | `93.33%` |
| **precision@5** | `19.33%` |
| **recall@5** | `88.33%` |
| **mrr@5** | `89.44%` |
| **ndcg@5** | `86.16%` |
| **hit@7** | `93.33%` |
| **precision@7** | `13.81%` |
| **recall@7** | `88.33%` |
| **mrr@7** | `89.44%` |
| **ndcg@7** | `86.16%` |
| **Avg Total Latency** | `4054.5 ms` |
| **Avg Routing Latency** | `213.1 ms` |
| **Avg Retrieval Latency** | `3841.3 ms` |
| **Gemini Fallback Rate** | `13.33%` (`4` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `100.0%` | `81.2%` | `84.0%` | `100.0%` | `4406.9 ms` |
| **simple** | 22 | `90.9%` | `90.9%` | `90.9%` | `90.9%` | `87.0%` | `85.6%` | `3926.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 17 | `94.1%` | `94.1%` | `94.1%` | `94.1%` | `89.0%` | `87.2%` | `3945.1 ms` |
| **hard** | 2 | `100.0%` | `100.0%` | `100.0%` | `50.0%` | `61.3%` | `100.0%` | `4037.0 ms` |
| **medium** | 11 | `90.9%` | `90.9%` | `90.9%` | `86.4%` | `86.3%` | `90.9%` | `4226.6 ms` |
