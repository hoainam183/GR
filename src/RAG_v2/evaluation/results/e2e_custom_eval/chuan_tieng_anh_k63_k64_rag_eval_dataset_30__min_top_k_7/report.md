# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 13:27:03
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `100.00%` | `30` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `0.00%` | `0` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `100.00%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `0.00%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `100.00%` |
| **precision@3** | `34.44%` |
| **recall@3** | `96.67%` |
| **mrr@3** | `63.33%` |
| **ndcg@3** | `71.51%` |
| **hit@5** | `100.00%` |
| **precision@5** | `22.00%` |
| **recall@5** | `100.00%` |
| **mrr@5** | `63.33%` |
| **ndcg@5** | `73.19%` |
| **hit@7** | `100.00%` |
| **precision@7** | `15.72%` |
| **recall@7** | `100.00%` |
| **mrr@7** | `63.33%` |
| **ndcg@7** | `73.19%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `9503.9 ms` |
| Routing Latency | `607.7 ms` |
| Search Latency | `200.2 ms` |
| Rerank Latency | `5755.8 ms` |
| Generation Latency | `1226.7 ms` |
| Self-Evaluation Latency | `1012.6 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `100.0%` | `64.0%` | `100.0%` | `100.0%` | `10931.6 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `76.5%` | `100.0%` | `100.0%` | `8984.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 21 | `100.0%` | `100.0%` | `75.4%` | `100.0%` | `100.0%` | `9167.7 ms` |
| **medium** | 9 | `100.0%` | `100.0%` | `68.0%` | `100.0%` | `100.0%` | `10288.4 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 29 | `100.0%` | `100.0%` | `73.5%` | `100.0%` | `100.0%` | `9407.3 ms` |
| **rag_v2_decomposed** | 1 | `100.0%` | `100.0%` | `63.1%` | `100.0%` | `100.0%` | `12305.6 ms` |
