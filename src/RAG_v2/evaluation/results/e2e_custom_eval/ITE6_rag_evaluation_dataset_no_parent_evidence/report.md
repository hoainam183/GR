# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-31 12:41:29
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `92.31%` | `25` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `96.15%` | Context facts coverage rate |
| **Hallucination Rate** | `3.85%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `76.92%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `7.69%` | Partially matches reference answer |
| **Ref Match Incorrect** | `15.38%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `61.54%` |
| **precision@3** | `20.51%` |
| **recall@3** | `59.62%` |
| **mrr@3** | `51.28%` |
| **ndcg@3** | `52.45%` |
| **hit@5** | `65.38%` |
| **precision@5** | `13.08%` |
| **recall@5** | `63.46%` |
| **mrr@5** | `52.24%` |
| **ndcg@5** | `54.11%` |
| **hit@7** | `69.23%` |
| **precision@7** | `9.89%` |
| **recall@7** | `64.74%` |
| **mrr@7** | `52.79%` |
| **ndcg@7** | `54.71%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `15650.8 ms` |
| Routing Latency | `812.1 ms` |
| Search Latency | `93.8 ms` |
| Rerank Latency | `5232.2 ms` |
| Generation Latency | `2837.1 ms` |
| Self-Evaluation Latency | `3087.2 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `62.5%` | `56.2%` | `41.3%` | `75.0%` | `62.5%` | `13958.2 ms` |
| **simple** | 18 | `66.7%` | `66.7%` | `59.8%` | `100.0%` | `83.3%` | `16403.1 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `66.7%` | `66.7%` | `59.8%` | `100.0%` | `83.3%` | `16403.1 ms` |
| **medium** | 8 | `62.5%` | `56.2%` | `41.3%` | `75.0%` | `62.5%` | `13958.2 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `65.4%` | `63.5%` | `54.1%` | `92.3%` | `76.9%` | `15650.8 ms` |
