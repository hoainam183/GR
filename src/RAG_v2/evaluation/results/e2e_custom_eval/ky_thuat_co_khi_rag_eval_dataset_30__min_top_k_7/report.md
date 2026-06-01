# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 18:04:39
- **Total Queries Evaluated**: `30`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `93.33%` | `29` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `100.00%` | Context facts coverage rate |
| **Hallucination Rate** | `3.33%` | `1` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `96.67%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `0.00%` | Partially matches reference answer |
| **Ref Match Incorrect** | `3.33%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `100.00%` |
| **precision@3** | `37.78%` |
| **recall@3** | `96.67%` |
| **mrr@3** | `93.33%` |
| **ndcg@3** | `92.71%` |
| **hit@5** | `100.00%` |
| **precision@5** | `23.33%` |
| **recall@5** | `98.33%` |
| **mrr@5** | `93.33%` |
| **ndcg@5** | `93.59%` |
| **hit@7** | `100.00%` |
| **precision@7** | `16.67%` |
| **recall@7** | `98.33%` |
| **mrr@7** | `93.33%` |
| **ndcg@7** | `93.59%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `7300.1 ms` |
| Routing Latency | `520.4 ms` |
| Search Latency | `102.8 ms` |
| Rerank Latency | `3476.7 ms` |
| Generation Latency | `1199.7 ms` |
| Self-Evaluation Latency | `1042.9 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `100.0%` | `93.8%` | `89.8%` | `75.0%` | `87.5%` | `9060.4 ms` |
| **simple** | 22 | `100.0%` | `100.0%` | `95.0%` | `100.0%` | `100.0%` | `6660.0 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 20 | `100.0%` | `100.0%` | `96.3%` | `100.0%` | `100.0%` | `6541.1 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `0.0%` | `100.0%` | `9152.7 ms` |
| **medium** | 9 | `100.0%` | `94.4%` | `86.8%` | `88.9%` | `88.9%` | `8781.0 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 30 | `100.0%` | `98.3%` | `93.6%` | `93.3%` | `96.7%` | `7300.1 ms` |
