# Search Strategy Benchmark Report

This file is append-only. Each benchmark run adds a new section so retrieval changes can be compared over time.

Run command:

```bash
cd src/RAG_v2
.venv/bin/python evaluation/search_strategy_benchmark.py
```

Each run writes `evaluation/search_strategy_results.json`, updates cached LLM labels in `evaluation/search_strategy_labels.jsonl`, and appends a new section to this report.

## Run - 2026-05-15T23:48:31+07:00

- Golden: `/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/eval/golden_dataset.json`
- Labels: `/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/evaluation/search_strategy_labels.jsonl`
- Cases: 10
- Strategies: 10
- Judge pool: 40 | k: 10 | recall_k: 50
- Skip judge: `False` | Failures: 0

### Overall Ranking

| Rank | Strategy | nDCG@10 | MRR@10 | Recall@50 |
|---:|---|---:|---:|---:|
| 1 | `current_hybrid_reranked` | 0.4948 | 0.7833 | 0.4451 |
| 2 | `current_hybrid` | 0.4098 | 0.6833 | 0.7642 |
| 3 | `linear_v0.80_k0.20` | 0.4098 | 0.6833 | 0.7642 |
| 4 | `linear_v0.60_k0.40` | 0.4085 | 0.7000 | 0.7347 |
| 5 | `linear_v0.40_k0.60` | 0.3882 | 0.6833 | 0.7204 |
| 6 | `e5_only` | 0.3569 | 0.4867 | 0.4728 |
| 7 | `linear_v0.20_k0.80` | 0.3382 | 0.5458 | 0.7151 |
| 8 | `bge_only` | 0.3174 | 0.5325 | 0.5851 |
| 9 | `bm25_only` | 0.3008 | 0.5625 | 0.4293 |
| 10 | `global_rrf` | 0.0909 | 0.2750 | 0.6728 |

### Winners

- Best nDCG@10: `current_hybrid_reranked` = 0.4948
- Best MRR@10: `current_hybrid_reranked` = 0.7833
- Best Recall@50: `current_hybrid` = 0.7642

### Best By Query Class

| Query class | Best nDCG@10 strategy | nDCG@10 | Best Recall@50 strategy | Recall@50 |
|---|---|---:|---|---:|
| `comparison` | `e5_only` | 0.6222 | `bge_only` | 1.0000 |
| `course` | `e5_only` | 0.8509 | `bge_only` | 1.0000 |
| `general` | `current_hybrid_reranked` | 0.6332 | `current_hybrid` | 1.0000 |
| `negation` | `current_hybrid_reranked` | 0.4572 | `current_hybrid` | 0.5000 |
| `policy` | `bge_only` | 0.6427 | `bge_only` | 0.8947 |
| `stsv_form` | `current_hybrid_reranked` | 0.9105 | `linear_v0.20_k0.80` | 1.0000 |
| `typo_no_diacritic` | `bm25_only` | 0.7536 | `bm25_only` | 0.9500 |

### Notes

- This run used 10 cases and 331 LLM-judged query-document labels, so the direction is useful but not yet statistically stable. Treat this as a baseline, not a final model decision.
- `current_hybrid_reranked` is the best answer-facing strategy: nDCG@10 `0.4948` and MRR@10 `0.7833`. It improves top-rank quality over `current_hybrid` by `+0.0850` nDCG and `+0.1000` MRR.
- `current_hybrid` / `linear_v0.80_k0.20` is still the best candidate-generation baseline: Recall@50 `0.7642`. Reranking improves precision but reduces retained recall to `0.4451`, likely because reranker thresholding/filtering removes relevant-but-lower-scored candidates.
- `global_rrf` should not replace the current linear fusion yet. It has acceptable Recall@50 `0.6728`, but very weak nDCG@10 `0.0909`, meaning it can find relevant documents but ranks them poorly.
- The alpha sweep supports staying vector-heavy overall. `0.80/0.20` and `0.60/0.40` are close, while `0.20/0.80` loses overall quality despite helping lexical/no-diacritic cases.
- Query-class signal is strong:
  - `policy`: `bge_only` wins. Dense semantic retrieval is important for regulations.
  - `course`: `e5_only` wins nDCG and dense-only recall is high, but current hybrid Recall@50 is only `0.1111`; course queries need a dedicated course-code/course-name path.
  - `typo_no_diacritic`: `bm25_only` dominates. ES analyzer/folding is carrying this case; dense embeddings are weak for accentless Vietnamese.
  - `negation`: raw strategies rank badly even when hybrid recall exists. Keep explicit exclude filters, then add reranker/context penalties for excluded terms.
  - `stsv_form`: reranking helps top quality; keyword-heavy search gives the broadest recall.
- Priority decisions from this run:
  - Keep production default as current linear hybrid `0.8 vector / 0.2 keyword` plus reranker for final answer context.
  - Do not switch global fusion to RRF.
  - Add query-class adaptive retrieval: BM25-heavy for no-diacritic/typo, dense-heavy for policy, E5/course-specific retrieval for course queries.
  - Track raw candidate Recall@50 before rerank separately from post-rerank Recall@50, because they answer different questions.
## Run - 2026-05-27T19:25:47+07:00

- Golden: `/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/eval/golden_dataset.json`
- Labels: `/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/evaluation/search_strategy_labels.jsonl`
- Cases: 10
- Strategies: 10
- Judge pool: 40 | k: 10 | recall_k: 50
- Skip judge: `True` | Failures: 0

### Overall Ranking

| Rank | Strategy | nDCG@10 | MRR@10 | Recall@50 |
|---:|---|---:|---:|---:|
| 1 | `current_hybrid_reranked` | 0.3538 | 0.5800 | 0.3128 |
| 2 | `linear_v0.40_k0.60` | 0.3433 | 0.6667 | 0.6024 |
| 3 | `linear_v0.60_k0.40` | 0.3430 | 0.6833 | 0.6174 |
| 4 | `linear_v0.20_k0.80` | 0.3117 | 0.6044 | 0.5698 |
| 5 | `current_hybrid` | 0.2981 | 0.6333 | 0.6064 |
| 6 | `linear_v0.80_k0.20` | 0.2981 | 0.6333 | 0.6064 |
| 7 | `bm25_only` | 0.2970 | 0.5833 | 0.5898 |
| 8 | `e5_only` | 0.2818 | 0.4333 | 0.4628 |
| 9 | `bge_only` | 0.2704 | 0.5125 | 0.5398 |
| 10 | `global_rrf` | 0.0430 | 0.1726 | 0.5612 |

### Winners

- Best nDCG@10: `current_hybrid_reranked` = 0.3538
- Best MRR@10: `linear_v0.60_k0.40` = 0.6833
- Best Recall@50: `linear_v0.60_k0.40` = 0.6174

### Best By Query Class

| Query class | Best nDCG@10 strategy | nDCG@10 | Best Recall@50 strategy | Recall@50 |
|---|---|---:|---|---:|
| `comparison` | `e5_only` | 0.4411 | `bge_only` | 1.0000 |
| `course` | `current_hybrid_reranked` | 0.7747 | `current_hybrid` | 0.8182 |
| `negation` | `linear_v0.20_k0.80` | 0.0279 | `bm25_only` | 0.5000 |
| `policy` | `current_hybrid_reranked` | 0.6521 | `current_hybrid` | 0.8684 |
| `schedule` | `e5_only` | 0.8509 | `bge_only` | 1.0000 |
| `stsv_form` | `current_hybrid_reranked` | 0.8973 | `bm25_only` | 0.9412 |
| `typo_no_diacritic` | `bm25_only` | 0.4492 | `bm25_only` | 0.7833 |

### Notes

- Add manual interpretation here after inspecting changed rows and labels.
- Keep this section append-only so runs remain comparable over time.
