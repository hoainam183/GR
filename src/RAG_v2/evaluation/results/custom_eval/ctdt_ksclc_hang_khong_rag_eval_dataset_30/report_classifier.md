# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-28 21:52:37
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `30`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **hit@3** | `83.33%` |
| **precision@3** | `31.11%` |
| **recall@3** | `76.11%` |
| **mrr@3** | `67.22%` |
| **ndcg@3** | `67.65%` |
| **hit@5** | `86.67%` |
| **precision@5** | `20.00%` |
| **recall@5** | `81.11%` |
| **mrr@5** | `67.89%` |
| **ndcg@5** | `69.82%` |
| **hit@7** | `86.67%` |
| **precision@7** | `14.29%` |
| **recall@7** | `81.11%` |
| **mrr@7** | `67.89%` |
| **ndcg@7** | `69.82%` |
| **Avg Total Latency** | `3819.8 ms` |
| **Avg Routing Latency** | `184.7 ms` |
| **Avg Retrieval Latency** | `3635.1 ms` |
| **Gemini Fallback Rate** | `6.67%` (`2` queries) |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `87.5%` | `87.5%` | `66.7%` | `49.1%` | `50.0%` | `3670.8 ms` |
| **simple** | 22 | `81.8%` | `86.4%` | `86.4%` | `86.4%` | `77.3%` | `74.4%` | `3873.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 21 | `81.0%` | `85.7%` | `85.7%` | `85.7%` | `76.3%` | `73.2%` | `3820.6 ms` |
| **hard** | 3 | `100.0%` | `100.0%` | `100.0%` | `66.7%` | `53.8%` | `55.5%` | `3599.5 ms` |
| **medium** | 6 | `83.3%` | `83.3%` | `83.3%` | `72.2%` | `55.2%` | `55.5%` | `3926.9 ms` |
