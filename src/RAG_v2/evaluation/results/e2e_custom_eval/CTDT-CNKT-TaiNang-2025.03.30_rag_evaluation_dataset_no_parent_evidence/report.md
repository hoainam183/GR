# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-30 13:48:02
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `76.92%` | `22` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `84.62%` | Context facts coverage rate |
| **Hallucination Rate** | `15.38%` | `4` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `65.38%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `23.08%` | Partially matches reference answer |
| **Ref Match Incorrect** | `11.54%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `65.38%` |
| **precision@3** | `23.08%` |
| **recall@3** | `55.13%` |
| **mrr@3** | `41.67%` |
| **ndcg@3** | `42.36%` |
| **hit@5** | `73.08%` |
| **precision@5** | `15.38%` |
| **recall@5** | `60.90%` |
| **mrr@5** | `43.40%` |
| **ndcg@5** | `44.93%` |
| **hit@7** | `80.77%` |
| **precision@7** | `13.74%` |
| **recall@7** | `72.44%` |
| **mrr@7** | `44.59%` |
| **ndcg@7** | `49.50%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `40951.8 ms` |
| Routing Latency | `1300.2 ms` |
| Search Latency | `218.7 ms` |
| Rerank Latency | `7235.4 ms` |
| Generation Latency | `5296.5 ms` |
| Self-Evaluation Latency | `4379.3 ms` |
| **HyDE Fallback Trigger Rate** | `84.62%` (`22` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `75.0%` | `41.7%` | `35.5%` | `75.0%` | `50.0%` | `44043.6 ms` |
| **simple** | 18 | `72.2%` | `69.4%` | `49.1%` | `77.8%` | `72.2%` | `39577.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `71.4%` | `71.4%` | `53.2%` | `78.6%` | `78.6%` | `37126.8 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `39439.1 ms` |
| **medium** | 11 | `72.7%` | `43.9%` | `29.3%` | `72.7%` | `45.5%` | `45957.5 ms` |
