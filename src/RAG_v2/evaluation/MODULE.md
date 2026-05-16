# Module: `evaluation` - Two-Layer RAG Evaluation & Offline Dashboard

## 1. Tong quan

Module `evaluation` la tang danh gia offline cho RAG v2. Muc tieu chinh la tach ro hai nhom bai test co ban chat khac nhau:

- **Historical Email Eval**: danh gia nang luc tu van theo hoi thoai lich su, ca nhan hoa, follow-up, hoi lai khi thieu thong tin va logic tu van. Suite nay dung email cu lam ground truth hanh vi, khong dung lam production factual golden vi quy dinh co the da thay doi.
- **Current Policy Eval**: danh gia he thong production hien tai dua tren tai lieu dang index trong RAG. Suite nay moi la golden cho production, dung de canh bao regression sau moi indexing job.

Module nay cung cap:

- Schema chung cho case, run, ket qua tung case.
- Loader cho historical email dataset va current policy golden dataset.
- Runner CLI `evaluation.two_layer_eval`.
- Retrieval eval cho stack production that: `Settings -> RetrievalService -> QueryRouter -> CollectionSelector -> MultiCollectionSearch -> reranker`.
- Luu ket qua vao MongoDB va artifact JSON/CSV.
- API dashboard batch offline qua `/metrics/eval`.
- Frontend route `/eval`.
- Trigger fail-soft sau indexing job.

Nguyen tac thiet ke quan trong: **Historical Email Eval khong duoc tinh vao production pass/fail cua du lieu hien hanh**. Current Policy Eval moi dung de canh bao chat luong data/index/retrieval/citation/freshness.

---

## 2. Cau truc module hien tai

```text
evaluation/
├── __init__.py                       # Package marker de chay python -m evaluation...
├── eval_schemas.py                   # Dataclass schemas, dataset loaders, judge parser, freshness helpers
├── eval_store.py                     # Persist MongoDB, ghi JSON/CSV artifacts, doc dashboard payload
├── build_current_policy_ground_truth.py
│                                      # Tao inventory/case draft/seed labels/audit CSV cho current golden
├── evaluate_current_pipeline.py      # Retrieval eval tren stack production that
├── post_index.py                     # Trigger eval fail-soft sau indexing job
├── two_layer_eval.py                 # CLI runner cho current_policy va historical_email
├── search_strategy_benchmark.py      # Benchmark cac chien luoc search/fusion/rerank
├── search_strategy_labels.jsonl      # Label retrieval chi tiet cho benchmark search strategy
├── search_strategy_results.json      # Ket qua benchmark search strategy gan nhat
├── search_strategy_report.md         # Bao cao benchmark search strategy
├── evaluate_llm_quality.py           # Eval chat/LLM quality cu hon
├── evaluate_phase3.py                # Eval phase 3 cu hon
├── evaluate_retrieval.py             # Eval retrieval cu hon
├── evaluate_hf_dataset.py            # Eval dataset HuggingFace cu hon
├── test_query.py                     # Script test query cu hon
└── MODULE.md                         # Tai lieu module nay
```

Cac file ngoai module nhung lien quan truc tiep:

```text
eval/golden_dataset.json              # Current policy golden dataset mac dinh
eval/RAG/ragass_evaluator.py          # RAGAS evaluator, co mode dataset_validation va full_rag
eval/RAG/outputs/ragass_dataset.jsonl # RAGAS dataset JSONL neu da generate
../clean_data/test_dataset.json       # Historical email dataset mac dinh
data/document_lineage.json            # Nguon truth cho freshness/superseded source
api/routes/metrics.py                 # Endpoint /metrics/eval
frontend/chat-companion/src/pages/EvalPage.tsx
                                      # UI dashboard /eval
```

---

## 3. Public entrypoints

### CLI chinh

Chay tu thu muc `src/RAG_v2`:

```bash
python -m evaluation.two_layer_eval current --persist
python -m evaluation.two_layer_eval current --labels evaluation/search_strategy_labels.jsonl --persist
python -m evaluation.two_layer_eval current --max-cases 120 --persist --trigger post_index
python -m evaluation.two_layer_eval historical --max-cases 50 --judge --persist
```

Mac dinh:

- Current dataset: `src/RAG_v2/eval/golden_dataset.json`
- Historical dataset: `src/clean_data/test_dataset.json`
- Output artifacts: `src/RAG_v2/evaluation/results/`
- Lineage freshness file: `src/RAG_v2/data/document_lineage.json`
- Current relevance labels: `src/RAG_v2/evaluation/search_strategy_labels.jsonl`

### Current ground truth builder

```bash
python -m evaluation.build_current_policy_ground_truth inventory
python -m evaluation.build_current_policy_ground_truth generate-cases --target-cases 200
python -m evaluation.build_current_policy_ground_truth seed-labels --cases evaluation/ground_truth_drafts/current_policy_cases_draft.json
python -m evaluation.build_current_policy_ground_truth validate --cases evaluation/ground_truth_drafts/current_policy_cases_draft.json --labels evaluation/ground_truth_drafts/search_strategy_labels_seed.jsonl
python -m evaluation.build_current_policy_ground_truth audit-export --cases eval/golden_dataset.json --labels evaluation/search_strategy_labels.jsonl
```

Builder chi ghi draft vao `evaluation/ground_truth_drafts/`; khong overwrite `eval/golden_dataset.json`. Sau khi audit moi merge vao golden chinh.

### Retrieval-only current pipeline eval

```bash
python evaluation/evaluate_current_pipeline.py --golden eval/golden_dataset.json --labels evaluation/search_strategy_labels.jsonl --k 10
```

Script nay chi danh gia retrieval stack that, khong generate final answer. Ket qua cua script duoc `two_layer_eval current` su dung de lap run production.

### RAGAS eval

```bash
python eval/RAG/ragass_evaluator.py --dataset eval/RAG/outputs/ragass_dataset.jsonl
python eval/RAG/ragass_evaluator.py --mode full_rag
```

Mode:

- `dataset_validation`: dung contexts trong dataset de kiem tra dataset quality.
- `full_rag`: goi `RAGPipeline.query_v3()` that, thay answer/contexts bang output cua pipeline.

### Dashboard API

```http
GET /metrics/eval?suite=current_policy&limit=10
GET /metrics/eval?suite=historical_email&limit=10
```

Endpoint doc MongoDB neu app co `mongo_logger`; neu khong co MongoDB logger thi fallback doc artifact JSON trong `evaluation/results/`.

### Frontend

```text
/eval
```

Dashboard hien:

- Latest run.
- Recent runs.
- Metric cards.
- Top failures.
- Breakdown theo query class va collection.
- Stale-source violations.
- Baseline warnings.

---

## 4. Schema chung

Schema nam trong `eval_schemas.py`.

### `EvalCase`

Dung de chuan hoa moi dataset thanh mot shape chung:

| Field | Y nghia |
|---|---|
| `eval_suite` | `historical_email` hoac `current_policy` |
| `case_id` | ID on dinh cua case |
| `question` | Cau hoi dua vao pipeline |
| `context` | Conversation/email context, chu yeu dung cho historical |
| `ground_truth_answer` | Cau tra loi tham chieu |
| `timestamp` | Thoi diem cua case lich su hoac metadata thoi gian |
| `expected_source_ids` | Cac chunk/doc/source ID mong doi cho current policy |
| `expected_collections` | Collection mong doi: `ctdt`, `quydinh`, `kehoach`, `stsv` |
| `valid_as_of` | Moc thoi gian case con hieu luc |
| `query_class` | Nhom cau hoi: policy, course, schedule, stsv_form, email_followup, ... |
| `difficulty` | Do kho: easy, medium, hard |
| `metadata` | Raw metadata giu lai de audit |

### `EvalCaseResult`

Luu ket qua tung case:

| Field | Y nghia |
|---|---|
| `actual_answer` | Answer sinh ra boi pipeline, neu co |
| `retrieved_source_ids` | Source IDs retrieved |
| `sources` | Compact retrieved sources voi text ngan va metadata |
| `timings_ms` | Latency theo stage hoac `pipeline_total` |
| `judge_scores` | Diem LLM judge theo rubric |
| `metrics` | Retrieval/freshness/citation metrics dang number |
| `fail_reasons` | Ly do fail de dashboard/debug |
| `passed` | Ket qua case |
| `error` | Loi runtime neu co |
| `case` | Snapshot cua EvalCase goc |

### `EvalRun`

Luu tong hop mot lan chay:

| Field | Y nghia |
|---|---|
| `run_id` | Timestamp + suffix random |
| `eval_suite` | Suite da chay |
| `status` | `passed`, `warning`, hoac `failed` |
| `started_at`, `finished_at` | ISO timestamp |
| `trigger` | `manual`, `document_indexed`, `auto_crawler_*`, ... |
| `summary` | Aggregate metrics |
| `artifacts` | Duong dan JSON/CSV artifacts |
| `config` | Dataset, max_cases, judge_enabled, trigger document/collection |
| `errors` | Loi non-fatal hoac fatal |

---

## 5. Historical Email Eval

### Muc tieu

Historical Email Eval dung de tra loi cau hoi: **assistant co xu ly dung ngu canh hoi thoai va logic tu van nhu mot can bo tu van hoc vu khong?**

Suite nay khong co muc tieu kiem tra quy dinh hien hanh. Neu answer khac ground truth chi vi quy dinh da doi, khong coi la fail factual production.

### Data dau vao

Mac dinh:

```text
src/clean_data/test_dataset.json
```

Dataset nay la ground truth email lich su. Loader `load_historical_email_cases()` doc cac field:

- `id`
- `question`
- `context`
- `ground_truth_answer`
- `thread_id`
- `metadata.timestamp`

Case co `context` duoc gan:

- `query_class = "email_followup"`
- `difficulty = "hard"`

Case khong co `context` duoc gan:

- `query_class = "email_initial"`
- `difficulty = "medium"`

### Pipeline chay

`run_historical_eval()`:

1. Load dataset tu `src/clean_data/test_dataset.json`.
2. Khoi tao `RAGPipeline(settings=settings)`.
3. Convert `context` thanh `history` bang `_build_history_from_email_context()`.
4. Goi:

```python
pipeline.query_v3(
    question=case.question,
    history=[...email context...],
    top_k=settings.top_k,
)
```

5. Neu co `--judge`, goi `GeminiJudge.judge_historical()`.
6. Ghi `EvalCaseResult`.
7. Ghi artifact JSON/CSV.
8. Neu co `--persist`, luu vao MongoDB.

### Rubric judge

Rubric trong `HISTORICAL_RUBRIC`:

| Metric | Cach hieu |
|---|---|
| `conversation_understanding` | Hieu dung noi dung thread/email truoc do |
| `followup_resolution` | Tra loi dung y cau hoi follow-up, khong reset ngu canh |
| `clarification_quality` | Biet hoi lai khi thieu thong tin quan trong |
| `personalization` | Dung thong tin ca nhan/cohort/nganh trong context neu co |
| `advisory_logic` | Tu van co logic, khong dua khuyen nghi vo ly |
| `tone` | Giong dieu phu hop voi sinh vien, ro rang, lich su |

Diem moi metric nam trong `[0.0, 1.0]`.

### Dieu gi bi phat

Fail hoac diem thap khi:

- Bo qua context email.
- Nhap nhang giua sinh vien/ho so/nam hoc.
- Khong hoi lai khi thieu du kien bat buoc.
- Hallucinate thong tin ca nhan khong co trong context.
- Tu van sai logic, ke ca neu cau tra loi nghe co ve hop ly.
- Giong dieu gay hieu nham hoac qua chung chung.

### Dieu gi khong bi phat

Khong phat neu answer khac historical ground truth do:

- Quy dinh hien hanh da thay doi.
- Lich/ke hoach nam cu khong con dung.
- Thu tuc cu da duoc thay bang thu tuc moi.

### Summary metrics

Run summary gom:

| Metric | Y nghia |
|---|---|
| `total_cases` | So case da chay |
| `passed_cases` | So case pass |
| `failed_cases` | So case fail |
| `avg_judge_score` | Trung binh diem rubric cua cac case co judge |
| `latency_p50_ms` | p50 latency theo `pipeline_total` |
| `latency_p95_ms` | p95 latency theo `pipeline_total` |

### Khi nao nen chay

Chay khi thay doi:

- Prompt hoi thoai.
- Model generation.
- Router/agent/reflection.
- Logic follow-up.
- Personalization/user context.

Khong can chay sau moi indexing job data.

---

## 6. Current Policy Eval

### Muc tieu

Current Policy Eval dung de tra loi cau hoi: **he thong production hien tai co tra loi dua tren dung tai lieu hien hanh, dung source, dung collection va khong dung stale source khong?**

Suite nay la production golden cho:

- Hoc vu.
- Quy dinh.
- Chuong trinh dao tao.
- Lich/ke hoach.
- Thu tuc sinh vien.

### Data dau vao

Mac dinh:

```text
src/RAG_v2/eval/golden_dataset.json
```

Loader `load_current_policy_cases()` chi doc cac case co:

```json
"category": "retrieval"
```

hoac cac shape tuong duong:

- `category = "current_policy"`
- `category = "rag"`
- `category = "generation"`

Field quan trong:

| Field | Bat buoc | Y nghia |
|---|---|---|
| `id` | Co | ID case on dinh |
| `category` | Co | Nen la `retrieval` cho current runner hien tai |
| `query` hoac `question` | Co | Cau hoi |
| `expected_collection` | Nen co | Collection dung |
| `expected_collections` | Nen co neu multi-source | Nhieu collection dung |
| `expected_source_ids` | Rat nen co | Source/chunk IDs dung |
| `ground_truth_answer` | Nen co neu dung judge generation | Answer tham chieu |
| `valid_as_of` | Nen co | Moc hieu luc |
| `query_class` | Nen co | policy, course, schedule, stsv_form, ... |
| `difficulty` | Nen co | easy, medium, hard |

### Collections production

| Collection | Noi dung |
|---|---|
| `quydinh` | Quy dinh hoc vu, hoc bong, tot nghiep, ngoai ngu, ky luat |
| `ctdt` | Chuong trinh dao tao, mon hoc, tin chi, tien quyet |
| `kehoach` | Lich dang ky, lich thi, ke hoach hoc ky, deadline |
| `stsv` | Bieu mau, thu tuc, ho tro sinh vien |

### Pipeline chay

`run_current_policy_eval()`:

1. Load current policy cases tu `golden_dataset.json`.
2. Goi `evaluate_current_pipeline.evaluate(...)`.
3. `evaluate_current_pipeline` khoi tao production stack:

```text
Settings
  -> RetrievalService.from_settings()
  -> QueryRouter
  -> CollectionSelector
  -> MultiCollectionSearch
  -> reranker neu duoc cau hinh
```

4. Moi case duoc route sang collection muc tieu.
5. Search raw candidates voi pool toi thieu 50 candidates.
6. Rerank top answer-facing `k=10`.
7. Tinh retrieval metrics.
8. Kiem tra freshness bang `document_lineage.json`.
9. Kiem tra citation/source hit bang `expected_source_ids`.
10. Neu co `--judge` va case co `ground_truth_answer`, goi `RAGPipeline.query_v3()` de lay answer full RAG roi judge.
11. Ghi artifact JSON/CSV.
12. Neu co `--persist`, luu MongoDB.

### Retrieval metrics

| Metric | Cap do | Cach hieu |
|---|---|---|
| `ndcg_at_10` | Post-rerank top 10 | Do chat luong ranking, relevant source cang len dau cang tot |
| `mrr_at_10` | Post-rerank top 10 | Relevant source dau tien nam o rank nao |
| `recall_at_50` | Raw candidate pool | Retrieval co lay du source dung truoc rerank khong |
| `context_precision` | Post-rerank context | Ty le context top-k co lien quan |
| `context_recall` | Post-rerank context | Ty le relevant source con nam trong context sau rerank |
| `collection_accuracy` | Routing/search | Retrieved results co dung collection mong doi khong |
| `keyword_hit_rate` | Sanity check | Retrieved text co chua keyword mong doi khong |

Cong thuc:

```text
Recall@k = (# relevant IDs trong top-k) / (# relevant IDs mong doi)

MRR@k = 1 / rank cua relevant ID dau tien trong top-k

DCG@k = sum(1 / log2(rank + 1)) voi moi relevant ID trong top-k
IDCG@k = DCG ly tuong neu relevant IDs dung dau
nDCG@k = DCG@k / IDCG@k

Context precision = (# relevant IDs trong context top-k) / k
Context recall = (# relevant IDs trong context top-k) / (# relevant IDs mong doi)
```

Luu y: `recall_at_50` la raw candidate metric truoc rerank. `ndcg_at_10`, `mrr_at_10`, `context_precision`, `context_recall` la post-rerank answer-facing metrics.

### Citation/source metrics

| Metric | Cach tinh |
|---|---|
| `citation_accuracy` | Pass neu retrieved IDs co giao voi `expected_source_ids`; neu case chua co expected source thi tam coi pass |
| `freshness_pass_rate` | Pass neu khong retrieved source nao thuoc document `superseded` trong `document_lineage.json` |

Fail reasons lien quan:

- `expected_source_not_retrieved`
- `stale_or_superseded_source`

### LLM judge metrics cho current policy

Chi chay khi co `--judge` va case co `ground_truth_answer`.

Rubric trong `CURRENT_POLICY_RUBRIC`:

| Metric | Cach hieu |
|---|---|
| `faithfulness` | Answer co duoc support boi retrieved sources khong |
| `answer_correctness` | Answer co dung voi ground truth/current policy khong |
| `answer_relevancy` | Answer co tra loi dung cau hoi khong |
| `citation_accuracy` | Citation/source co khop noi dung answer khong |

Neu judge duoc bat, runner se goi full `RAGPipeline.query_v3()` de lay `actual_answer`, sau do judge answer voi sources.

### Baseline comparison

`two_layer_eval current` doc baseline tu:

```text
src/RAG_v2/evaluation/search_strategy_results.json
```

Baseline dang duoc dung:

| Metric | Baseline source |
|---|---|
| `ndcg_at_10` | `current_hybrid_reranked.ndcg_at_10` |
| `mrr_at_10` | `current_hybrid_reranked.mrr_at_10` |
| `recall_at_50` | `current_hybrid.recall_at_50` |

Neu current run thap hon baseline, `summary.baseline_warnings` se co message va run status chuyen thanh `warning`.

### Summary metrics

Run summary gom:

- `total_cases`
- `passed_cases`
- `failed_cases`
- `collection_accuracy`
- `keyword_hit_rate`
- `ndcg_at_10`
- `mrr_at_10`
- `recall_at_50`
- `context_precision`
- `context_recall`
- `citation_accuracy`
- `freshness_pass_rate`
- `latency_p50_ms`
- `latency_p95_ms`
- `search_strategy_baseline`
- `baseline_warnings`

### Khi nao nen chay

Chay sau:

- Moi indexing job.
- Crawl/index tu dong co document moi.
- Doi chunking.
- Doi embedding model.
- Doi BM25/vector/hybrid weight.
- Doi reranker.
- Doi metadata filters.
- Doi prompt grounding/citation.

---

## 7. RAGAS Eval

RAGAS evaluator nam tai:

```text
src/RAG_v2/eval/RAG/ragass_evaluator.py
```

Dataset mac dinh:

```text
src/RAG_v2/eval/RAG/outputs/ragass_dataset.jsonl
```

### Mode 1: dataset validation

`eval_mode = "dataset_validation"`:

- Dung `ground_truth_context_texts` lam retrieved contexts.
- Dung answer trong dataset.
- Muc tieu: kiem tra dataset co du chat luong de lam eval khong.

Khong danh gia pipeline production that.

### Mode 2: full_rag

`eval_mode = "full_rag"`:

- Goi `RAGPipeline.query_v3()`.
- Thay `answer` bang answer cua pipeline.
- Thay `contexts` bang sources retrieved that.
- Sau do goi RAGAS metrics.

### Metrics RAGAS

Mac dinh dang tap trung:

| Metric | Y nghia |
|---|---|
| `context_recall` | Context retrieved co bao phu du thong tin can thiet khong |
| `context_precision` | Context retrieved co nhieu noise/irrelevant khong |

Co the bat them:

- `faithfulness`
- `answer_relevancy`

RAGAS nen dung de bo sung cho Current Policy Eval, khong thay the source-ID based golden. Ly do: production gate can source IDs va freshness deterministic hon LLM-only judge.

---

## 8. Search Strategy Benchmark

Benchmark search strategy nam trong:

```text
src/RAG_v2/evaluation/search_strategy_benchmark.py
src/RAG_v2/evaluation/search_strategy_labels.jsonl
src/RAG_v2/evaluation/search_strategy_results.json
src/RAG_v2/evaluation/search_strategy_report.md
```

Muc tieu:

- So sanh BM25, dense, hybrid, RRF, linear fusion, reranked strategy.
- Tach raw candidate Recall@50 voi post-rerank nDCG@10/MRR@10.
- Tim strategy tot nhat theo query class.

Baseline gan nhat trong report:

| Strategy | nDCG@10 | MRR@10 | Recall@50 |
|---|---:|---:|---:|
| `current_hybrid_reranked` | 0.4948 | 0.7833 | 0.4451 |
| `current_hybrid` | 0.4098 | 0.6833 | 0.7642 |

Ket luan baseline:

- `current_hybrid_reranked` tot nhat cho answer-facing top-rank quality.
- `current_hybrid` tot nhat cho raw candidate recall.
- Current Policy Eval doc hai baseline nay de canh bao regression.

---

## 9. Storage va artifacts

### MongoDB collections

Module ghi vao:

```text
eval_runs
eval_case_results
```

Indexes duoc tao trong `models/database.py` va `models/mongo_logger.py`:

```text
eval_runs:
  - (eval_suite, finished_at desc)
  - status

eval_case_results:
  - run_id
  - (eval_suite, passed)
  - case_id
```

### Artifact files

Moi run ghi:

```text
src/RAG_v2/evaluation/results/{eval_suite}_{run_id}.json
src/RAG_v2/evaluation/results/{eval_suite}_{run_id}.csv
```

JSON artifact co shape:

```json
{
  "run": {
    "run_id": "...",
    "eval_suite": "current_policy",
    "status": "warning",
    "summary": {},
    "artifacts": {}
  },
  "cases": []
}
```

CSV artifact gom cac cot:

- `case_id`
- `eval_suite`
- `passed`
- `error`
- `fail_reasons`
- `judge_scores`
- `metrics`
- `retrieved_source_ids`
- `latency_ms`

Artifacts dung cho audit/reproduce. MongoDB dung cho dashboard doc nhanh.

---

## 10. Dashboard payload

`/metrics/eval` tra ve:

| Field | Y nghia |
|---|---|
| `status` | `ok` hoac `empty` |
| `source` | `mongodb` hoac `artifacts` |
| `latest` | EvalRun moi nhat |
| `runs` | Danh sach recent runs |
| `trends` | Series metric theo run |
| `failing_cases` | Cac case fail cua latest run |
| `breakdown.by_query_class` | Pass/fail theo query class |
| `breakdown.by_collection` | Pass/fail theo collection |
| `stale_source_violations` | Case fail vi stale/superseded source |

Frontend `/eval` hien cac nhom nay thanh cards va tables.

Dashboard hien tai la **batch offline**, khong realtime production monitoring.

---

## 11. Post-index trigger va gates

### Cau hinh

Trong `Settings`:

| Setting | Mac dinh | Y nghia |
|---|---:|---|
| `post_index_eval_enabled` | `True` | Bat trigger sau indexing |
| `post_index_eval_command` | `""` | Command custom neu muon override |
| `post_index_eval_max_cases` | `120` | So current cases toi da cho post-index run |

### Trigger locations

Trigger duoc goi sau khi index thanh cong:

- `pipeline/document_pipeline.py`
- `scripts/auto_crawler.py`

Implementation nam trong:

```text
evaluation/post_index.py
```

Trigger la fail-soft:

- Chay subprocess nen khong block indexing.
- Loi start subprocess chi log warning.
- Eval failure se hien tren dashboard/artifact, khong rollback index.

### Status rules

`status = "failed"` khi:

- Eval runner crash o muc khong tao duoc result.
- Khong load duoc dataset.
- Khong co case hop le.
- Khong ket noi duoc retrieval backend den muc khong co result.

`status = "warning"` khi:

- Fail rate case qua cao.
- `citation_accuracy` thap.
- `freshness_pass_rate` thap.
- Metric current run thap hon baseline search strategy.

`status = "passed"` khi:

- Co case hop le.
- Khong co canh bao gate.
- Ty le fail nam trong nguong hien tai.

Trong giai doan dau, indexing khong rollback tu dong.

---

## 12. Cach tao va mo rong current golden dataset

Current golden production co 2 artifact chinh:

| Artifact | Vai tro |
|---|---|
| `eval/golden_dataset.json` | Danh sach case/query, expected collection/source IDs, query class, answer tham chieu |
| `evaluation/search_strategy_labels.jsonl` | Graded relevance labels theo tung `(case_id, doc_id)` voi diem `0/1/2` |

Neu chi co `golden_dataset.json` ma thieu labels/source IDs, cac metric ranking nhu `nDCG@10`, `MRR@10`, `Recall@50` khong co denominator dung va se khong phan anh chat luong retrieval.

Mot case nen co shape:

```json
{
  "id": "retrieval_quydinh_hocbong_001",
  "category": "retrieval",
  "query": "Điều kiện xét học bổng khuyến khích học tập là gì?",
  "expected_collection": "quydinh",
  "expected_collections": ["quydinh"],
  "expected_source_ids": [
    "chunk_or_doc_id_1",
    "chunk_or_doc_id_2"
  ],
  "expected_keywords": ["học bổng", "khuyến khích học tập"],
  "ground_truth_answer": "Sinh viên cần ...",
  "valid_as_of": "2026-05-16",
  "query_class": "policy",
  "difficulty": "medium",
  "description": "Scholarship policy source retrieval"
}
```

Khuyen nghi can bang:

| Collection | Ty le muc tieu |
|---|---:|
| `quydinh` | 30-35% |
| `ctdt` | 25-30% |
| `kehoach` | 20-25% |
| `stsv` | 15-20% |

Nen co du nhom query:

- Policy direct lookup.
- Course/program lookup.
- Schedule/deadline.
- Procedure/form.
- No-diacritic/typo.
- Negation.
- Comparison.
- Ambiguous query can hoi lai.

Nguyen tac gan `expected_source_ids`:

- Dung IDs on dinh sau indexing.
- Neu mot answer can nhieu source, ghi tat ca source chap nhan duoc.
- Khong chi dua vao keyword vi keyword hit khong du de gate production.
- Neu document bi superseded, update case sang source moi.

### Quy trinh tao ground truth v1

1. Tao inventory tu chunks dang index:

```bash
python -m evaluation.build_current_policy_ground_truth inventory
```

Nguon chunk mac dinh:

```text
data/quydinh/chunks/*.json
data/quydinh/admin_upload/*_chunks.json
data/ctdt/**/chunks_recursive_parent_child/*_chunks.json
data/kehoach/chunks/*.json
data/stsv/chunks/*.json
```

2. Sinh case draft theo stratified sampling:

```bash
python -m evaluation.build_current_policy_ground_truth generate-cases --target-cases 200
```

Output:

```text
evaluation/ground_truth_drafts/current_policy_cases_draft.json
```

3. Seed relevance labels tu `expected_source_ids`:

```bash
python -m evaluation.build_current_policy_ground_truth seed-labels \
  --cases evaluation/ground_truth_drafts/current_policy_cases_draft.json \
  --output evaluation/ground_truth_drafts/search_strategy_labels_seed.jsonl
```

4. Chay search strategy benchmark de lay candidate pool va LLM judge labels:

```bash
python evaluation/search_strategy_benchmark.py \
  --golden evaluation/ground_truth_drafts/current_policy_cases_draft.json \
  --labels evaluation/ground_truth_drafts/search_strategy_labels_seed.jsonl
```

5. Export CSV de audit:

```bash
python -m evaluation.build_current_policy_ground_truth audit-export \
  --cases evaluation/ground_truth_drafts/current_policy_cases_draft.json \
  --labels evaluation/ground_truth_drafts/search_strategy_labels_seed.jsonl
```

6. Audit toi thieu 30% case. Neu sua relevance, append row moi vao labels JSONL voi cung `case_id/doc_id`; loader se lay row sau cung lam truth.

7. Validate truoc khi merge:

```bash
python -m evaluation.build_current_policy_ground_truth validate \
  --cases evaluation/ground_truth_drafts/current_policy_cases_draft.json \
  --labels evaluation/ground_truth_drafts/search_strategy_labels_seed.jsonl
```

8. Sau audit, merge case da duyet vao `eval/golden_dataset.json` va merge labels vao `evaluation/search_strategy_labels.jsonl`.

### Relevance label semantics

| Relevance | Y nghia |
|---:|---|
| `0` | Khong lien quan hoac gay nhieu |
| `1` | Lien quan mot phan, co tin hieu nhung khong du de tra loi truc tiep |
| `2` | Chua evidence can thiet de tra loi truc tiep |

Current eval uu tien labels neu co:

- `nDCG@10`: graded gain tu relevance `0/1/2`.
- `MRR@10`: hit dau tien co relevance `>0`.
- `Recall@50`: so relevant docs relevance `>0` retrieve duoc trong raw candidate top 50.
- Fallback sang `expected_source_ids` chi khi case chua co relevance labels.

---

## 13. Cach mo rong historical email dataset

Historical dataset mac dinh:

```text
src/clean_data/test_dataset.json
```

Mot case nen co:

```json
{
  "id": "email_thread_001_turn_003",
  "question": "Em muốn hỏi tiếp về điều kiện này ạ",
  "context": "Nội dung email/thread trước...",
  "ground_truth_answer": "Câu trả lời lịch sử...",
  "thread_id": "email_thread_001",
  "metadata": {
    "timestamp": "2021-03-15 09:30:00",
    "sender_role": "student"
  }
}
```

Nen label them trong `metadata` neu co:

- cohort.
- major.
- intent.
- missing_fields.
- resolution_type.
- source_email_date.

Historical suite nen uu tien case:

- Follow-up can doc context.
- Case thieu thong tin phai hoi lai.
- Case co thong tin ca nhan/cohort/nganh.
- Case co tu van logic nhieu buoc.
- Case ma answer hien tai duoc phep khac answer lich su vi quy dinh da doi.

---

## 14. Latency va cost-quality Pareto

Hien tai module da ghi:

- `latency_ms` per case trong current retrieval eval.
- `timings_ms` theo stage neu pipeline tra ve.
- `latency_p50_ms`
- `latency_p95_ms`

De lam Pareto day du, can chay nhieu run voi config khac nhau va so sanh:

- Model generation.
- `top_k`.
- `vector_top_k`.
- `keyword_top_k`.
- `reranker` on/off.
- Context budget.
- Hybrid weights.
- LLM judge on/off.

Dashboard co the dung `summary` cua nhieu run de ve:

```text
x-axis: latency_p95_ms hoac cost/token
y-axis: ndcg_at_10, citation_accuracy, freshness_pass_rate, avg_judge_score
color: config/model/strategy
```

Cost/token chua duoc tinh tu dong trong runner hien tai. Neu can production Pareto that, bo sung:

- input tokens.
- output tokens.
- embedding calls.
- reranker calls.
- LLM judge calls.
- estimated USD/VND cost theo model.

---

## 15. Test coverage

Tests lien quan:

```text
src/RAG_v2/tests/test_two_layer_eval.py
```

Dang cover:

- Load historical email cases.
- Load current policy cases tu shape `golden_dataset.json`.
- Parse judge JSON co markdown fence.
- Fallback khi judge output khong phai JSON.
- Freshness checker fail voi superseded source.
- Relevance label JSONL last-row-wins de manual audit override LLM judge.
- Graded retrieval metrics dung relevance `0/1/2`.
- Ground truth builder sinh draft case, seed label va validate schema.
- Artifact dashboard doc latest run, breakdown va stale violations.

Lenh chay:

```bash
cd src/RAG_v2
./.venv/bin/python -m pytest tests/test_two_layer_eval.py -q
```

Nen bo sung tiep:

- Mock `evaluate_current_pipeline.evaluate()` de test `run_current_policy_eval()`.
- Mock `RAGPipeline.query_v3()` de test historical runner.
- API test cho `/metrics/eval`.
- Integration test voi Qdrant/Elasticsearch test containers neu co.

---

## 16. Operational playbook

### Sau moi indexing job

1. `DocumentPipeline` hoac `AutoCrawlPipeline` index thanh cong.
2. `trigger_post_index_eval()` start subprocess:

```bash
python -m evaluation.two_layer_eval current --max-cases 120 --persist --trigger ...
```

3. Run ghi MongoDB va artifacts.
4. Dashboard `/eval` hien latest status.
5. Neu `warning`, mo top failures va stale-source violations.
6. Neu source sai, sua data/index/metadata/filter.
7. Neu metric thap hon baseline, doc `baseline_warnings`.

### Khi doi prompt/model/router/agent

Chay:

```bash
python -m evaluation.two_layer_eval historical --max-cases 200 --judge --persist
python -m evaluation.two_layer_eval current --judge --persist
```

So sanh:

- Historical `avg_judge_score`.
- Current `faithfulness`, `answer_correctness`, `citation_accuracy`.
- Latency p95.

### Khi nghi ngo retrieval regression

Chay:

```bash
python evaluation/evaluate_current_pipeline.py --golden eval/golden_dataset.json --k 10
python evaluation/search_strategy_benchmark.py
```

So sanh:

- raw `Recall@50`.
- post-rerank `nDCG@10`.
- post-rerank `MRR@10`.
- breakdown theo `query_class`.

---

## 17. Known limitations

- `golden_dataset.json` hien tai van can mo rong them `expected_source_ids` va relevance labels de lam gate production manh hon.
- Current runner retrieval-only co metric deterministic; generation judge chi chay khi bat `--judge` va co `ground_truth_answer`.
- LLM judge co the dao dong, nen khong nen la gate duy nhat.
- `citation_accuracy` hien tai la source-hit level; chua verify tung claim trong answer map ve citation nao.
- `freshness_pass_rate` phu thuoc chat luong `document_lineage.json`.
- Dashboard la batch offline, chua co realtime user feedback/session abandonment/follow-up tracking trong cung view.
- Cost-quality Pareto chua tinh cost/token that.

---

## 18. Quy tac khi sua module nay

- Khong tron Historical Email Eval vao Current Policy production gate.
- Khong dung email historical lam factual source hien hanh.
- Khi them current policy case moi, uu tien `expected_source_ids` hon keyword-only checks.
- Khi doi retrieval pipeline, chay current policy eval va search strategy benchmark.
- Khi doi prompt/model/agent, chay historical eval va current eval co `--judge`.
- Moi artifact phai du de reproduce: dataset path, max_cases, trigger, config, run_id.
- Loi post-index eval khong duoc lam fail indexing job trong giai doan hien tai.
