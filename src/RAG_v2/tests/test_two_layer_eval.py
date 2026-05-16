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
