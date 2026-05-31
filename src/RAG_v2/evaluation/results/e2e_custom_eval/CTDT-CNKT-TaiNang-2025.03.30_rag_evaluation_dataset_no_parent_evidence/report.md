# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-31 02:12:35
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `84.62%` | `23` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `92.31%` | Context facts coverage rate |
| **Hallucination Rate** | `11.54%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `80.77%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `7.69%` | Partially matches reference answer |
| **Ref Match Incorrect** | `11.54%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `76.92%` |
| **precision@3** | `26.92%` |
| **recall@3** | `62.82%` |
| **mrr@3** | `46.79%` |
| **ndcg@3** | `47.26%` |
| **hit@5** | `80.77%` |
| **precision@5** | `18.46%` |
| **recall@5** | `70.51%` |
| **mrr@5** | `47.76%` |
| **ndcg@5** | `50.74%` |
| **hit@7** | `80.77%` |
| **precision@7** | `14.29%` |
| **recall@7** | `73.72%` |
| **mrr@7** | `47.76%` |
| **ndcg@7** | `52.22%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `16892.1 ms` |
| Routing Latency | `349.0 ms` |
| Search Latency | `82.3 ms` |
| Rerank Latency | `4843.5 ms` |
| Generation Latency | `4587.3 ms` |
| Self-Evaluation Latency | `3978.8 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `87.5%` | `60.4%` | `48.1%` | `75.0%` | `87.5%` | `18428.5 ms` |
| **simple** | 18 | `77.8%` | `75.0%` | `51.9%` | `88.9%` | `77.8%` | `16209.2 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `78.6%` | `78.6%` | `56.8%` | `85.7%` | `85.7%` | `15755.9 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `12341.6 ms` |
| **medium** | 11 | `81.8%` | `57.6%` | `38.5%` | `81.8%` | `72.7%` | `18751.8 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `80.8%` | `70.5%` | `50.7%` | `84.6%` | `80.8%` | `16892.1 ms` |
