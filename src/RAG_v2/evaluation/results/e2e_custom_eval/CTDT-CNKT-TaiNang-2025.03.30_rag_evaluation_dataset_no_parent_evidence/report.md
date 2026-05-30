# RAG E2E Pipeline Quality Evaluation Report

- **Date**: 2026-05-30 15:49:31
- **Total Queries Evaluated**: `26`

## E2E Generation Metrics (LLM Quality)

| Metric | Score (Rate) | Details / Counts |
| :--- | :---: | :--- |
| **Faithfulness (Grounded)** | `92.31%` | `24` grounded responses |
| **Answer Relevance** | `96.15%` | Relevance of answer to question |
| **Completeness** | `88.46%` | Context facts coverage rate |
| **Hallucination Rate** | `7.69%` | `2` ungrounded/hallucinated claims |
| **Correctness (Ref Match Correct)** | `61.54%` | Fully correct against golden reference answer |
| **Ref Match Partial** | `15.38%` | Partially matches reference answer |
| **Ref Match Incorrect** | `23.08%` | Missing facts / completely incorrect |

## E2E Retrieval Metrics (After E2E Orchestration)

| Metric | Score (Average) |
| :--- | :---: |
| **hit@3** | `50.00%` |
| **precision@3** | `19.23%` |
| **recall@3** | `48.08%` |
| **mrr@3** | `34.62%` |
| **ndcg@3** | `37.06%` |
| **hit@5** | `57.69%` |
| **precision@5** | `13.08%` |
| **recall@5** | `55.77%` |
| **mrr@5** | `36.54%` |
| **ndcg@5** | `40.38%` |
| **hit@7** | `57.69%` |
| **precision@7** | `9.34%` |
| **recall@7** | `55.77%` |
| **mrr@7** | `36.54%` |
| **ndcg@7** | `40.38%` |

## Performance & Latency Breakdowns

| Phase / Event | Avg Latency / Trigger Rate |
| :--- | :---: |
| **Total Latency** | `63006.6 ms` |
| Routing Latency | `1989.6 ms` |
| Search Latency | `982.4 ms` |
| Rerank Latency | `43237.1 ms` |
| Generation Latency | `3916.6 ms` |
| Self-Evaluation Latency | `2933.6 ms` |
| **HyDE Fallback Trigger Rate** | `0.00%` (`0` queries) |

## Breakdown by Question Type

| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **multi_hop** | 8 | `37.5%` | `31.2%` | `32.7%` | `75.0%` | `37.5%` | `62925.1 ms` |
| **simple** | 18 | `66.7%` | `66.7%` | `43.8%` | `100.0%` | `72.2%` | `63042.8 ms` |

## Breakdown by Difficulty

| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **easy** | 14 | `64.3%` | `64.3%` | `44.7%` | `100.0%` | `71.4%` | `64727.6 ms` |
| **hard** | 1 | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `100.0%` | `56354.5 ms` |
| **medium** | 11 | `45.5%` | `40.9%` | `29.5%` | `81.8%` | `45.5%` | `61420.9 ms` |
