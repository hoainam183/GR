# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 15:05:01
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `66.67%` | `22` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `80.00%` | Context facts coverage rate |
| **Hallucination Rate** | `26.67%` | `8` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `66.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `16.67%` | Partially matches reference answer |
| **Ref Match Incorrect** | `16.67%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `43.33%` |
| **precision@3** | `14.44%` |
| **recall@3** | `43.33%` |
| **mrr@3** | `30.00%` |
| **ndcg@3** | `33.49%` |
| **hit@5** | `46.67%` |
| **precision@5** | `9.33%` |
| **recall@5** | `46.67%` |
| **mrr@5** | `30.83%` |
| **ndcg@5** | `34.93%` |
| **hit@7** | `46.67%` |
| **precision@7** | `6.67%` |
| **recall@7** | `46.67%` |
| **mrr@7** | `30.83%` |
| **ndcg@7** | `34.93%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `10906.5 ms` |
| Routing Latency | `573.9 ms` |
| Search Latency | `109.5 ms` |
| Rerank Latency | `5519.2 ms` |
| Generation Latency | `1537.1 ms` |
| Self-Evaluation Latency | `1157.1 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `25.0%` | `25.0%` | `20.4%` | `75.0%` | `37.5%` | `11467.9 ms` |
| **simple** | 22 | `54.5%` | `54.5%` | `40.2%` | `63.6%` | `77.3%` | `10702.3 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 19 | `47.4%` | `47.4%` | `34.7%` | `57.9%` | `73.7%` | `10601.4 ms` |
| **medium** | 11 | `45.5%` | `45.5%` | `35.4%` | `81.8%` | `54.5%` | `11433.4 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `46.7%` | `46.7%` | `34.9%` | `66.7%` | `66.7%` | `10906.5 ms` |
