from __future__ import annotations

import json


def test_load_historical_email_cases(tmp_path):
    from evaluation.eval_schemas import load_historical_email_cases

    path = tmp_path / "emails.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "email_1",
                    "question": "Em muốn hỏi tiếp về học phần này ạ",
                    "context": "Thư trước: em thuộc K61 ATTT",
                    "ground_truth_answer": "Em cần bổ sung đơn...",
                    "thread_id": "t1",
                    "metadata": {"timestamp": "2020-01-01 10:00:00"},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_historical_email_cases(path)
    assert len(cases) == 1
    assert cases[0].eval_suite == "historical_email"
    assert cases[0].query_class == "email_followup"
    assert cases[0].metadata["thread_id"] == "t1"


def test_load_current_policy_cases_from_golden_shape(tmp_path):
    from evaluation.eval_schemas import load_current_policy_cases

    path = tmp_path / "golden.json"
    path.write_text(
        json.dumps(
            {
                "test_cases": [
                    {"id": "route_1", "category": "routing", "query": "Xin chào"},
                    {
                        "id": "retrieval_1",
                        "category": "retrieval",
                        "query": "Điều kiện tốt nghiệp",
                        "expected_collection": "quydinh",
                        "expected_source_ids": ["quydinh/abc", "def"],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_current_policy_cases(path)
    assert len(cases) == 1
    assert cases[0].eval_suite == "current_policy"
    assert cases[0].expected_collections == ["quydinh"]
    assert cases[0].expected_source_ids == ["abc", "def"]


def test_load_current_policy_cases_from_schema_v1_jsonl_and_legacy_sft(tmp_path):
    from evaluation.eval_schemas import load_current_policy_cases

    path = tmp_path / "schema_v1.jsonl"
    rows = [
        {
            "id": "qcdt_2025_dieu2_khoan6_001",
            "question": "Chương trình Cử nhân có thời gian đào tạo chuẩn là bao lâu?",
            "ground_truth": "Thời gian đào tạo chuẩn đối với chương trình Cử nhân là 4 năm.",
            "ground_truth_contexts": ["chunk-1"],
            "ground_truth_context_texts": ["Cử nhân | 4 năm"],
            "source": "quydinh",
            "question_type": "single",
            "answerable": True,
            "expected_behavior": "answer_with_citation",
            "atomic_facts": ["Cử nhân", "4 năm"],
        },
        {
            "instruction": "Điều kiện tốt nghiệp là gì?",
            "input": "legacy prompt context",
            "output": "Sinh viên cần đủ tín chỉ và các điều kiện theo quy chế.",
            "doc_type": "legacy_sft",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    cases = load_current_policy_cases(path)
    assert len(cases) == 2
    assert cases[0].case_id == "qcdt_2025_dieu2_khoan6_001"
    assert cases[0].expected_collections == ["quydinh"]
    assert cases[0].expected_source_ids == ["chunk-1"]
    assert cases[0].metadata["ground_truth_contexts"] == ["quydinh/chunk-1"]
    assert cases[0].metadata["answerable"] is True
    assert cases[1].question == "Điều kiện tốt nghiệp là gì?"
    assert cases[1].ground_truth_answer == "Sinh viên cần đủ tín chỉ và các điều kiện theo quy chế."
    assert cases[1].metadata["legacy_input"] == "legacy prompt context"


def test_parse_judge_scores_accepts_markdown_fence():
    from evaluation.eval_schemas import parse_judge_scores

    raw = """```json
{"scores":{"tone":0.8,"advisory_logic":1.2},"fail_reasons":["missing clarification"]}
```"""
    scores, reasons = parse_judge_scores(raw, ["tone", "advisory_logic"])
    assert scores["tone"] == 0.8
    assert scores["advisory_logic"] == 1.0
    assert reasons == ["missing clarification"]


def test_parse_judge_scores_falls_back_on_invalid_json():
    from evaluation.eval_schemas import parse_judge_scores

    scores, reasons = parse_judge_scores("not-json", ["tone"])
    assert scores == {"tone": 0.0}
    assert reasons == ["judge_parse_error"]


def test_freshness_checker_flags_superseded_source(tmp_path):
    from evaluation.eval_schemas import freshness_pass_for_sources

    lineage = tmp_path / "document_lineage.json"
    lineage.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "doc_id": "old-doc",
                        "status": "superseded",
                        "source_file": "QD_NN_DHCQ-2020-2021-1501_converted_chunks.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    sources = [
        {
            "id": "quydinh/123",
            "metadata": {"source": "data/quydinh/QD_NN_DHCQ-2020-2021-1501_converted_chunks.json"},
        }
    ]
    assert freshness_pass_for_sources(sources, lineage) is False


def test_relevance_labels_last_row_wins(tmp_path):
    from evaluation.eval_schemas import load_relevance_labels

    labels = tmp_path / "labels.jsonl"
    labels.write_text(
        "\n".join(
            [
                json.dumps({"case_id": "c1", "doc_id": "quydinh/abc", "relevance": 1}),
                json.dumps({"case_id": "c1", "doc_id": "quydinh/abc", "relevance": 2, "source": "human_audit"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_relevance_labels(labels)
    assert loaded["c1"]["abc"] == 2


def test_graded_retrieval_metrics_use_relevance_labels():
    from evaluation.evaluate_current_pipeline import (
        _graded_mrr_at_k,
        _graded_ndcg_at_k,
        _graded_recall_at_k,
    )

    labels = {"a": 2, "b": 1, "c": 0}
    assert _graded_ndcg_at_k(["a", "b"], labels, 10) == 1.0
    assert _graded_mrr_at_k(["x", "b", "a"], labels, 10) == 0.5
    assert _graded_recall_at_k(["x", "b", "a"], labels, 50) == 1.0


def test_current_pipeline_loader_accepts_schema_v1_jsonl(tmp_path):
    from evaluation.evaluate_current_pipeline import _expected_ids, _load_retrieval_cases

    path = tmp_path / "rag_eval.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "case_1",
                "question": "Cử nhân học bao lâu?",
                "ground_truth": "4 năm.",
                "ground_truth_contexts": ["chunk-1"],
                "source": "quydinh",
                "expected_keywords": ["Cử nhân", "4 năm"],
                "question_type": "single",
                "answerable": True,
                "expected_behavior": "answer_with_citation",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    cases = _load_retrieval_cases(path)
    assert len(cases) == 1
    assert cases[0]["query"] == "Cử nhân học bao lâu?"
    assert cases[0]["expected_collection"] == "quydinh"
    assert cases[0]["expected_source_ids"] == ["quydinh/chunk-1"]
    assert _expected_ids(cases[0]) == {"chunk-1"}


def test_deterministic_answer_checks_generation_and_refusal():
    from evaluation.eval_schemas import EvalCase
    from evaluation.two_layer_eval import _deterministic_answer_checks

    answerable_case = EvalCase(
        eval_suite="current_policy",
        case_id="c1",
        question="Cử nhân học bao lâu?",
        metadata={
            "answerable": True,
            "atomic_facts": ["Cử nhân", "4 năm"],
            "expected_citations": ["Quy chế đào tạo năm 2025 - Điều 2 - Khoản 6"],
        },
    )
    metrics, reasons = _deterministic_answer_checks(
        answerable_case,
        "Theo Quy chế đào tạo năm 2025 - Điều 2 - Khoản 6, Cử nhân học 4 năm.",
    )
    assert reasons == []
    assert metrics["atomic_fact_coverage"] == 1.0
    assert metrics["citation_text_accuracy"] == 1.0

    refusal_case = EvalCase(
        eval_suite="current_policy",
        case_id="c2",
        question="Thông tin không có trong context?",
        metadata={
            "answerable": False,
            "expected_behavior": "refuse_insufficient_context",
        },
    )
    metrics, reasons = _deterministic_answer_checks(
        refusal_case,
        "Không có đủ thông tin trong ngữ cảnh được cung cấp để trả lời câu hỏi này.",
    )
    assert reasons == []
    assert metrics["refusal_accuracy"] == 1.0


def test_ragass_loader_accepts_schema_v1(tmp_path):
    from eval.RAG.ragass_evaluator import load_dataset

    path = tmp_path / "ragass.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "q1",
                "question": "Cử nhân học bao lâu?",
                "ground_truth": "4 năm.",
                "ground_truth_contexts": ["quydinh/chunk-1"],
                "ground_truth_context_texts": ["Cử nhân | 4 năm"],
                "source": "quydinh",
                "expected_collection": "quydinh",
                "question_type": "single",
                "answerable": True,
                "expected_behavior": "answer_with_citation",
                "atomic_facts": ["4 năm"],
                "expected_citations": ["Quy chế - Điều 2"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    samples = load_dataset(path)
    assert len(samples) == 1
    assert samples[0].id == "q1"
    assert samples[0].expected_collection == "quydinh"
    assert samples[0].ground_truth_contexts == ["quydinh/chunk-1"]
    assert samples[0].atomic_facts == ["4 năm"]


def test_ground_truth_builder_generates_valid_draft(tmp_path):
    from evaluation.build_current_policy_ground_truth import (
        build_cases,
        load_chunk_inventory,
        seed_labels,
        validate_cases,
    )

    chunk_dir = tmp_path / "data" / "quydinh" / "chunks"
    chunk_dir.mkdir(parents=True)
    (chunk_dir / "quydinh_all_chunks.json").write_text(
        json.dumps(
            [
                {
                    "chunk_id": "chunk-1",
                    "content": (
                        "Quy định học bổng khuyến khích học tập quy định GPA, "
                        "điểm rèn luyện và các trường hợp không được xét học bổng. "
                        "Sinh viên cần đăng ký đủ số tín chỉ theo quy định."
                    ),
                    "metadata": {
                        "title": "Quy định học bổng khuyến khích học tập",
                        "source": "quydinh",
                        "date_str": "2026-01-01",
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    records = load_chunk_inventory(tmp_path / "data")
    payload = build_cases(records, target_cases=1, include_variants=False)
    cases_path = tmp_path / "cases.json"
    labels_path = tmp_path / "labels.jsonl"
    cases_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert payload["test_cases"][0]["expected_source_ids"] == ["quydinh/chunk-1"]

    assert seed_labels(cases_path, labels_path) == 1
    validation = validate_cases(cases_path, labels_path)
    assert validation["valid"] is True


def test_ground_truth_builder_query_class_follows_collection():
    from evaluation.build_current_policy_ground_truth import ChunkRecord, build_cases

    record = ChunkRecord(
        doc_id="quydinh/chunk-1",
        collection="quydinh",
        content="Lịch đăng ký học tập được nêu trong quy chế đào tạo.",
        title="Lịch đăng ký học tập",
        source_path="data/quydinh/chunks/example.json",
    )

    payload = build_cases([record], target_cases=1, include_variants=False)
    assert payload["test_cases"][0]["query_class"] == "policy"


def test_search_strategy_benchmark_uses_case_metadata_for_query_class(tmp_path):
    from evaluation.search_strategy_benchmark import load_cases, load_feedback_cases

    golden = tmp_path / "golden.json"
    golden.write_text(
        json.dumps(
            {
                "test_cases": [
                    {
                        "id": "case_policy",
                        "category": "retrieval",
                        "query": "Lịch đăng ký học tập được quy định thế nào?",
                        "expected_collection": "quydinh",
                    },
                    {
                        "id": "case_explicit",
                        "category": "retrieval",
                        "query": "hoc bong khuyen khich hoc tap",
                        "expected_collection": "quydinh",
                        "query_class": "typo_no_diacritic",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_cases(golden, include_diagnostics=False)
    assert [case.query_class for case in cases] == ["policy", "typo_no_diacritic"]

    feedback = tmp_path / "feedback.jsonl"
    feedback.write_text(
        json.dumps(
            {
                "id": "fb1",
                "rating": "down",
                "query": "đăng ký gửi xe ở đâu?",
                "expected_collection": "stsv",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    assert load_feedback_cases(feedback)[0].query_class == "stsv_form"


def test_artifact_dashboard_returns_latest_breakdown_and_failures(tmp_path):
    from evaluation.eval_schemas import EvalCaseResult, EvalRun
    from evaluation.eval_store import load_latest_artifact_dashboard, write_eval_artifacts

    run = EvalRun(
        run_id="run_1",
        eval_suite="current_policy",
        status="warning",
        started_at="2026-05-16T00:00:00+00:00",
        finished_at="2026-05-16T00:01:00+00:00",
        summary={"total_cases": 1, "failed_cases": 1},
    )
    results = [
        EvalCaseResult(
            eval_suite="current_policy",
            case_id="case_1",
            question="Điều kiện tốt nghiệp?",
            passed=False,
            fail_reasons=["stale_or_superseded_source"],
            case={
                "query_class": "policy",
                "expected_collections": ["quydinh"],
            },
        )
    ]

    write_eval_artifacts(tmp_path, run, results)
    dashboard = load_latest_artifact_dashboard(tmp_path, suite="current_policy")

    assert dashboard["status"] == "ok"
    assert dashboard["latest"]["run_id"] == "run_1"
    assert dashboard["failing_cases"][0]["case_id"] == "case_1"
    assert dashboard["breakdown"]["by_query_class"][0]["key"] == "policy"
    assert dashboard["stale_source_violations"][0]["case_id"] == "case_1"
