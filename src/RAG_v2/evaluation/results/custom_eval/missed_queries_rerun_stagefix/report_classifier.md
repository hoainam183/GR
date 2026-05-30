# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-30 01:25:58
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `5`
- **Total Queries Evaluated**: `575`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **router_recall** | `92.70%` |
| **router_hit** | `92.70%` |
| **candidate_hit@20** | `70.26%` |
| **candidate_recall@20** | `66.43%` |
| **rerank_hit@5** | `52.00%` |
| **rerank_recall@5** | `43.04%` |
| **final_hit@5** | `56.70%` |
| **final_recall@5** | `48.78%` |
| **hit@3** | `48.00%` |
| **precision@3** | `18.20%` |
| **recall@3** | `38.72%` |
| **mrr@3** | `37.91%` |
| **ndcg@3** | `34.68%` |
| **hit@5** | `56.70%` |
| **precision@5** | `13.98%` |
| **recall@5** | `48.78%` |
| **mrr@5** | `39.95%` |
| **ndcg@5** | `39.35%` |
| **hit@7** | `56.70%` |
| **precision@7** | `9.99%` |
| **recall@7** | `48.78%` |
| **mrr@7** | `39.95%` |
| **ndcg@7** | `39.35%` |
| **Avg Total Latency** | `8626.6 ms` |
| **Avg Routing Latency** | `1271.8 ms` |
| **Avg Retrieval Latency** | `7354.8 ms` |
| **Gemini Fallback Rate** | `13.04%` (`75` queries) |

## Stage Metrics

| Stage | Metric | Score |
| :--- | :--- | :---: |
| Router | router_recall | `92.70%` |
| Router | router_hit | `92.70%` |
| Pre-rerank candidates | candidate_recall@20 | `66.43%` |
| Strict rerank | rerank_recall@5 | `43.04%` |
| Final | final_recall@5 | `48.78%` |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 227 | `63.9%` | `74.0%` | `74.0%` | `54.0%` | `45.7%` | `52.5%` | `8669.1 ms` |
| **simple** | 348 | `37.6%` | `45.4%` | `45.4%` | `45.4%` | `35.2%` | `31.8%` | `8598.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 316 | `37.7%` | `45.9%` | `45.9%` | `45.7%` | `35.6%` | `32.3%` | `8519.0 ms` |
| **hard** | 19 | `68.4%` | `73.7%` | `73.7%` | `43.9%` | `43.7%` | `61.0%` | `7773.0 ms` |
| **medium** | 240 | `60.0%` | `69.6%` | `69.6%` | `53.2%` | `44.0%` | `48.3%` | `8835.8 ms` |
