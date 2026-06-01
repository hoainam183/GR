# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 16:55:24
- **Total Queries Evaluated**: `100`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `85.00%` | `89` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `87.00%` | Context facts coverage rate |
| **Hallucination Rate** | `11.00%` | `11` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `53.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `8.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `39.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `44.00%` |
| **precision@3** | `16.67%` |
| **recall@3** | `42.50%` |
| **mrr@3** | `39.17%` |
| **ndcg@3** | `39.27%` |
| **hit@5** | `46.00%` |
| **precision@5** | `10.60%` |
| **recall@5** | `45.00%` |
| **mrr@5** | `39.62%` |
| **ndcg@5** | `40.35%` |
| **hit@7** | `46.00%` |
| **precision@7** | `7.72%` |
| **recall@7** | `45.50%` |
| **mrr@7** | `39.62%` |
| **ndcg@7** | `40.57%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `22461.4 ms` |
| Routing Latency | `1556.7 ms` |
| Search Latency | `187.6 ms` |
| Rerank Latency | `10232.6 ms` |
| Generation Latency | `1577.3 ms` |
| Self-Evaluation Latency | `1321.3 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 30 | `50.0%` | `46.7%` | `42.1%` | `76.7%` | `50.0%` | `37355.6 ms` |
| **simple** | 70 | `44.3%` | `44.3%` | `39.6%` | `88.6%` | `54.3%` | `16078.2 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 51 | `54.9%` | `54.9%` | `49.9%` | `92.2%` | `62.7%` | `14281.6 ms` |
| **hard** | 4 | `25.0%` | `25.0%` | `25.0%` | `50.0%` | `25.0%` | `32367.1 ms` |
| **medium** | 45 | `37.8%` | `35.6%` | `30.9%` | `80.0%` | `44.4%` | `30851.4 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 97 | `46.4%` | `45.9%` | `41.3%` | `85.6%` | `53.6%` | `21664.1 ms` |
| **rag_v2_decomposed** | 3 | `33.3%` | `16.7%` | `10.2%` | `66.7%` | `33.3%` | `48242.0 ms` |
