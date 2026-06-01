# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 15:24:41
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `83.33%` | `27` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `90.00%` | Context facts coverage rate |
| **Hallucination Rate** | `10.00%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `83.33%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `13.33%` | Partially matches reference answer |
| **Ref Match Incorrect** | `3.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `83.33%` |
| **precision@3** | `31.11%` |
| **recall@3** | `80.00%` |
| **mrr@3** | `83.33%` |
| **ndcg@3** | `80.49%` |
| **hit@5** | `83.33%` |
| **precision@5** | `18.67%` |
| **recall@5** | `80.00%` |
| **mrr@5** | `83.33%` |
| **ndcg@5** | `80.49%` |
| **hit@7** | `86.67%` |
| **precision@7** | `13.81%` |
| **recall@7** | `81.67%` |
| **mrr@7** | `83.89%` |
| **ndcg@7** | `81.21%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `14609.4 ms` |
| Routing Latency | `655.9 ms` |
| Search Latency | `160.2 ms` |
| Rerank Latency | `6503.8 ms` |
| Generation Latency | `1435.2 ms` |
| Self-Evaluation Latency | `1051.3 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `75.0%` | `76.8%` | `75.0%` | `75.0%` | `13593.1 ms` |
| **simple** | 22 | `81.8%` | `81.8%` | `81.8%` | `86.4%` | `86.4%` | `14979.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `80.0%` | `80.0%` | `80.0%` | `85.0%` | `85.0%` | `14119.1 ms` |
| **medium** | 10 | `90.0%` | `80.0%` | `81.5%` | `80.0%` | `80.0%` | `15590.2 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `83.3%` | `80.0%` | `80.5%` | `83.3%` | `83.3%` | `14609.4 ms` |
