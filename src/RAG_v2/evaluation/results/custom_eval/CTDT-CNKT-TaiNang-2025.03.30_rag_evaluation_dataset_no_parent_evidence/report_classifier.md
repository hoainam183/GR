# RAG Retrieval Quality Evaluation Report (CLASSIFIER)

- **Date**: 2026-05-30 22:19:19
- **Router Mode**: `classifier`
- **Metric Cutoff (Top K)**: `7`
- **Total Queries Evaluated**: `26`

## Overall Performance

| Metric | Score (Average) |
| :--- | :--- |
| **router_recall** | `96.15%` |
| **router_hit** | `96.15%` |
| **candidate_hit@20** | `84.62%` |
| **candidate_recall@20** | `77.56%` |
| **rerank_hit@5** | `84.62%` |
| **rerank_recall@5** | `71.47%` |
| **final_hit@5** | `84.62%` |
| **final_recall@5** | `71.47%` |
| **hit@3** | `76.92%` |
| **precision@3** | `26.92%` |
| **recall@3** | `62.82%` |
| **mrr@3** | `46.15%` |
| **ndcg@3** | `46.75%` |
| **hit@5** | `84.62%` |
| **precision@5** | `19.23%` |
| **recall@5** | `71.47%` |
| **mrr@5** | `48.08%` |
| **ndcg@5** | `50.88%` |
| **hit@7** | `84.62%` |
| **precision@7** | `14.84%` |
| **recall@7** | `74.68%` |
| **mrr@7** | `48.08%` |
| **ndcg@7** | `52.36%` |
| **Avg Total Latency** | `7215.0 ms` |
| **Avg Routing Latency** | `461.1 ms` |
| **Avg Retrieval Latency** | `6753.9 ms` |
| **Gemini Fallback Rate** | `3.85%` (`1` queries) |

## Stage Metrics

| Stage | Metric | Score |
| :--- | :--- | :---: |
| Router | router_recall | `96.15%` |
| Router | router_hit | `96.15%` |
| Pre-rerank candidates | candidate_recall@20 | `77.56%` |
| Strict rerank | rerank_recall@5 | `71.47%` |
| Final | final_recall@5 | `71.47%` |

## Breakdown by Question Type

| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `100.0%` | `100.0%` | `63.5%` | `50.2%` | `57.3%` | `10590.3 ms` |
| **simple** | 18 | `72.2%` | `77.8%` | `77.8%` | `75.0%` | `51.2%` | `44.0%` | `5714.9 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `71.4%` | `78.6%` | `78.6%` | `78.6%` | `55.9%` | `48.2%` | `5877.9 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `14134.6 ms` |
| **medium** | 11 | `81.8%` | `90.9%` | `90.9%` | `59.9%` | `40.1%` | `43.2%` | `8287.8 ms` |
