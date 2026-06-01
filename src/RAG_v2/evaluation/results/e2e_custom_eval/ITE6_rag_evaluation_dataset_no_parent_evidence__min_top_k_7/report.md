# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-06-01 11:53:08
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `84.62%` | `23` grounded responses |
| **Answer Relevance** | `100.00%` | Relevance of answer to question |
| **Completeness** | `88.46%` | Context facts coverage rate |
| **Hallucination Rate** | `11.54%` | `3` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `80.77%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `7.69%` | Partially matches reference answer |
| **Ref Match Incorrect** | `11.54%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `69.23%` |
| **precision@3** | `23.07%` |
| **recall@3** | `67.31%` |
| **mrr@3** | `53.85%` |
| **ndcg@3** | `56.30%` |
| **hit@5** | `73.08%` |
| **precision@5** | `14.62%` |
| **recall@5** | `71.15%` |
| **mrr@5** | `54.81%` |
| **ndcg@5** | `57.95%` |
| **hit@7** | `76.92%` |
| **precision@7** | `10.99%` |
| **recall@7** | `72.44%` |
| **mrr@7** | `55.36%` |
| **ndcg@7** | `58.55%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `56988.1 ms` |
| Routing Latency | `2228.3 ms` |
| Search Latency | `229.8 ms` |
| Rerank Latency | `5426.3 ms` |
| Generation Latency | `20608.3 ms` |
| Self-Evaluation Latency | `17300.0 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `62.5%` | `56.2%` | `41.3%` | `62.5%` | `62.5%` | `56761.7 ms` |
| **simple** | 18 | `77.8%` | `77.8%` | `65.3%` | `94.4%` | `88.9%` | `57088.7 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 18 | `77.8%` | `77.8%` | `65.3%` | `94.4%` | `88.9%` | `57088.7 ms` |
| **medium** | 8 | `62.5%` | `56.2%` | `41.3%` | `62.5%` | `62.5%` | `56761.7 ms` |

## Breakdown by Pipeline Mode

| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **rag_v2** | 26 | `73.1%` | `71.2%` | `58.0%` | `84.6%` | `80.8%` | `56988.1 ms` |
