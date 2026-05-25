from __future__ import annotations

import hashlib
import json


def test_load_sft_dataset_reads_instruction_output_doc_type(tmp_path):
    from evaluation.evaluate_sft_backend import load_sft_dataset

    dataset = tmp_path / "sft.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "instruction": "Một tín chỉ tương đương bao nhiêu giờ học tập?",
                "input": (
                    "CONTEXT:\n---\n"
                    "Văn bản: Quy chế đào tạo năm 2025\n"
                    "Chương: CHƯƠNG I\n"
                    "Điều: Điều 4. Tín chỉ và học phần\n"
                    "Khoản: 1\n"
                    "Ngày hiệu lực: 2025-05-28\n\n"
                    "Nội dung:\nMột TC được tính tương đương 50 giờ học tập.\n"
                    "---"
                ),
                "output": "Một tín chỉ tương đương 50 giờ học tập.",
                "doc_type": "Quy chế đào tạo năm 2025",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    samples = load_sft_dataset(dataset)

    assert len(samples) == 1
    assert samples[0].index == 1
    assert samples[0].instruction == "Một tín chỉ tương đương bao nhiêu giờ học tập?"
    assert samples[0].reference_answer == "Một tín chỉ tương đương 50 giờ học tập."
    assert samples[0].doc_type == "Quy chế đào tạo năm 2025"
    assert samples[0].metadata["document_title"] == "Quy chế đào tạo năm 2025"
    assert samples[0].metadata["article"] == "Điều 4. Tín chỉ và học phần"
    assert samples[0].metadata["clause"] == "1"
    assert samples[0].metadata["effective_date"] == "2025-05-28"
    assert samples[0].metadata["ground_truth_context_text"] == (
        "Một TC được tính tương đương 50 giờ học tập."
    )
    assert samples[0].sample_id


def test_parse_legacy_input_extracts_metadata_and_context():
    from evaluation.evaluate_sft_backend import _parse_legacy_input

    parsed = _parse_legacy_input(
        "Bạn là chatbot.\n"
        "CONTEXT:\n---\n"
        "Văn bản: Quy chế đào tạo năm 2025\n"
        "Chương: CHƯƠNG I NHỮNG QUY ĐỊNH CHUNG\n"
        "Điều: Điều 2. Ngành đào tạo, chương trình đào tạo\n"
        "Khoản: 6\n"
        "Ngày hiệu lực: 2025-05-28\n\n"
        "Nội dung:\n| Cử nhân | 4 năm |\n---"
    )

    assert parsed["document_title"] == "Quy chế đào tạo năm 2025"
    assert parsed["chapter"] == "CHƯƠNG I NHỮNG QUY ĐỊNH CHUNG"
    assert parsed["article"] == "Điều 2. Ngành đào tạo, chương trình đào tạo"
    assert parsed["clause"] == "6"
    assert parsed["effective_date"] == "2025-05-28"
    assert parsed["ground_truth_context_text"] == "| Cử nhân | 4 năm |"


def test_resume_skips_completed_and_controls_failed_retry(tmp_path):
    from evaluation.evaluate_sft_backend import (
        SFTSample,
        load_existing_records,
        should_skip_sample,
    )

    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    completed = SFTSample(1, "done-id", "q1", "", "a1", "doc")
    failed = SFTSample(2, "fail-id", "q2", "", "a2", "doc")
    (run_dir / "results.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"sample_id": "done-id", "status": "completed"}),
                json.dumps({"sample_id": "fail-id", "status": "failed"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = load_existing_records(run_dir)

    assert should_skip_sample(completed, records, retry_failed=False) is True
    assert should_skip_sample(failed, records, retry_failed=False) is True
    assert should_skip_sample(failed, records, retry_failed=True) is False


def test_resume_can_read_legacy_batch_files(tmp_path):
    from evaluation.evaluate_sft_backend import load_existing_records

    run_dir = tmp_path / "run"
    batches = run_dir / "batches"
    batches.mkdir(parents=True)
    (batches / "batch_0001.jsonl").write_text(
        json.dumps({"sample_id": "legacy-id", "status": "completed"}) + "\n",
        encoding="utf-8",
    )

    records = load_existing_records(run_dir)

    assert records["legacy-id"]["status"] == "completed"


def test_resume_can_merge_child_run_dirs(tmp_path):
    from evaluation.evaluate_sft_backend import load_existing_records

    run_dir = tmp_path / "sft_backend_eval"
    child_run = run_dir / "20260524_010505"
    child_run.mkdir(parents=True)
    run_dir.mkdir(exist_ok=True)
    (child_run / "results.jsonl").write_text(
        json.dumps({"sample_id": "child-id", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "results.jsonl").write_text(
        json.dumps({"sample_id": "root-id", "status": "completed"}) + "\n",
        encoding="utf-8",
    )

    records = load_existing_records(run_dir, include_child_run_dirs=True)

    assert records["child-id"]["status"] == "completed"
    assert records["root-id"]["status"] == "completed"


def test_prepare_run_dir_uses_output_dir_by_default(tmp_path):
    from evaluation.evaluate_sft_backend import _prepare_run_dir

    output_dir = tmp_path / "sft_backend_eval"

    run_id, run_dir = _prepare_run_dir(
        {
            "output_dir": str(output_dir),
            "resume_dir": None,
            "run_dir": None,
            "timestamped_run_dir": False,
        }
    )

    assert run_id == "sft_backend_eval"
    assert run_dir == output_dir
    assert output_dir.exists()


def test_select_batches_supports_specific_batch_index():
    from evaluation.evaluate_sft_backend import SFTSample, _select_batches

    samples = [
        SFTSample(index=i, sample_id=f"id-{i}", instruction=f"q{i}", input="", reference_answer="a", doc_type="doc")
        for i in range(1, 6)
    ]

    all_batches = _select_batches(samples, {"batch_size": 2, "batch_index": 0})
    selected_batch = _select_batches(samples, {"batch_size": 2, "batch_index": 2})

    assert [batch_no for batch_no, _ in all_batches] == [1, 2, 3]
    assert [sample.index for sample in all_batches[0][1]] == [1, 2]
    assert selected_batch[0][0] == 2
    assert [sample.index for sample in selected_batch[0][1]] == [3, 4]


def test_anonymous_identity_mode_ignores_eval_env_and_identity_config(monkeypatch):
    from evaluation.evaluate_sft_backend import (
        _build_frontend_chat_payload,
        _frontend_chat_headers,
    )

    monkeypatch.setenv("EVAL_SESSION_ID", "env-session")
    monkeypatch.setenv("EVAL_USER_CONTEXT_JSON", json.dumps({"cohort": "K70"}))
    monkeypatch.setenv("EVAL_USER_ID", "env-user")
    monkeypatch.setenv("EVAL_AUTH_TOKEN", "env-token")

    config = {
        "identity_mode": "anonymous",
        "mode": "manual",
        "top_k": 99,
        "history": [{"role": "user", "content": "previous turn"}],
        "session_id": "configured-session",
        "user_context": {"cohort": "K69", "full_name": "Configured User"},
        "user_id": "configured-user",
        "send_null_optional_fields": True,
        "auth_token": "configured-token",
        "session_id_env": "EVAL_SESSION_ID",
        "user_context_env": "EVAL_USER_CONTEXT_JSON",
        "user_id_env": "EVAL_USER_ID",
        "auth_token_env": "EVAL_AUTH_TOKEN",
    }

    payload = _build_frontend_chat_payload(question="hello", config=config)
    headers = _frontend_chat_headers(config)

    assert payload == {
        "question": "hello",
        "role": "user",
        "mode": "auto",
        "top_k": 5,
        "history": [],
        "session_id": "",
        "user_context": None,
        "user_id": "",
    }
    assert headers == {"Content-Type": "application/json"}


def test_frontend_env_identity_mode_keeps_env_driven_identity(monkeypatch):
    from evaluation.evaluate_sft_backend import (
        _build_frontend_chat_payload,
        _frontend_chat_headers,
    )

    monkeypatch.setenv("EVAL_SESSION_ID", "env-session")
    monkeypatch.setenv(
        "EVAL_USER_CONTEXT_JSON",
        json.dumps(
            {
                "student_id": "20260001",
                "cohort": "K70",
                "major": "Computer Science",
                "ignored": "drop-me",
            }
        ),
    )
    monkeypatch.setenv("EVAL_USER_ID", "env-user")
    monkeypatch.setenv("EVAL_AUTH_TOKEN", "env-token")

    config = {
        "identity_mode": "frontend_env",
        "mode": "auto",
        "top_k": 7,
        "history": [{"role": "assistant", "content": "previous answer"}],
        "session_id": None,
        "user_context": None,
        "user_id": None,
        "send_null_optional_fields": False,
        "auth_token": "",
        "session_id_env": "EVAL_SESSION_ID",
        "user_context_env": "EVAL_USER_CONTEXT_JSON",
        "user_id_env": "EVAL_USER_ID",
        "auth_token_env": "EVAL_AUTH_TOKEN",
    }

    payload = _build_frontend_chat_payload(question="hello", config=config)
    headers = _frontend_chat_headers(config)

    assert payload["mode"] == "auto"
    assert payload["top_k"] == 7
    assert payload["history"] == [{"role": "assistant", "content": "previous answer"}]
    assert payload["session_id"] == "env-session"
    assert payload["user_id"] == "env-user"
    assert payload["user_context"] == {
        "student_id": "20260001",
        "cohort": "K70",
        "major": "Computer Science",
    }
    assert headers["Authorization"] == "Bearer env-token"


def test_evaluate_sample_records_identity_and_request_payload_hash(monkeypatch):
    from evaluation import evaluate_sft_backend as runner

    request_payload = {
        "question": "hello",
        "mode": "auto",
        "top_k": 5,
        "history": [],
    }
    request_headers = {"Content-Type": "application/json"}

    def fake_post_backend(*, backend_url, question, config, timeout_s):
        assert backend_url == "http://backend.test/chat/v3"
        assert question == "hello"
        assert timeout_s == 1.0
        return (
            {
                "answer": "answer",
                "session_id": "backend-session",
                "sources": [],
            },
            request_payload,
            request_headers,
        )

    monkeypatch.setattr(runner, "_post_backend", fake_post_backend)

    sample = runner.SFTSample(
        index=1,
        sample_id="id-1",
        instruction="hello",
        input="",
        reference_answer="answer",
        doc_type="doc",
    )

    record = runner.evaluate_sample(
        sample,
        {
            "backend_url": "http://backend.test/chat/v3",
            "timeout_s": 1.0,
            "judge_backend": "none",
            "identity_mode": "anonymous",
            "record_request_payload": True,
            "record_response_trace": True,
        },
    )

    expected_hash = hashlib.sha256(
        json.dumps(
            request_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=runner._json_default,
        ).encode("utf-8")
    ).hexdigest()

    assert record["identity_mode"] == "anonymous"
    assert record["auth_header_sent"] is False
    assert record["optional_fields_sent"] == []
    assert record["request_payload_hash"] == expected_hash
    assert record["backend_url"] == "http://backend.test/chat/v3"
    assert record["response_session_id"] == "backend-session"
    assert record["request_payload"] == request_payload
    assert record["response_trace"]["rerank_trace"] is None
    assert record["response_trace"]["answer_quality_gate"] is None
    assert record["response_trace"]["context_trace"] is None
    assert record["response_trace"]["fusion_weights"] is None
    assert record["response_trace"]["tools_used"] is None
    assert record["response_trace"]["tool_calls"] is None


def test_evaluate_batch_writes_each_independent_request_result(tmp_path, monkeypatch):
    from evaluation import evaluate_sft_backend as runner

    samples = [
        runner.SFTSample(index=i, sample_id=f"id-{i}", instruction=f"q{i}", input="", reference_answer="a", doc_type="doc")
        for i in range(1, 4)
    ]
    records = {"id-1": {"sample_id": "id-1", "status": "completed"}}
    run_dir = tmp_path / "run"
    seen: list[str] = []

    def fake_evaluate_sample(sample, config):
        seen.append(sample.sample_id)
        return {
            "sample_id": sample.sample_id,
            "index": sample.index,
            "status": "completed",
            "question": sample.instruction,
            "reference_answer": sample.reference_answer,
            "generated_answer": f"answer {sample.index}",
            "metrics": {"answer_nonempty": True},
        }

    monkeypatch.setattr(runner, "evaluate_sample", fake_evaluate_sample)

    written = runner._evaluate_batch(
        batch_no=3,
        batch_samples=samples,
        records=records,
        run_dir=run_dir,
        run_id="run",
        samples_total=len(samples),
        config={"retry_failed": False, "batch_concurrency": 2},
    )

    assert written == 2
    assert sorted(seen) == ["id-2", "id-3"]
    assert records["id-1"]["status"] == "completed"
    assert records["id-2"]["batch_index"] == 3
    assert records["id-3"]["batch_index"] == 3

    lines = (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert len(rows) == 2
    assert {row["sample_id"] for row in rows} == {"id-2", "id-3"}
    assert {row["batch_index"] for row in rows} == {3}
    assert (run_dir / "progress.json").exists()
    assert not (run_dir / "batches" / "batch_0003.jsonl").exists()


def test_calculate_metrics_with_fake_backend_sources():
    from evaluation.evaluate_sft_backend import SFTSample, calculate_metrics

    sample = SFTSample(
        index=1,
        sample_id="id1",
        instruction="Chương trình Cử nhân học bao lâu?",
        input="",
        reference_answer=(
            "Theo Điều 2, Khoản 6, từ Quy chế đào tạo năm 2025, "
            "thời gian đào tạo chuẩn đối với chương trình Cử nhân là 4 năm."
        ),
        doc_type="Quy chế đào tạo năm 2025",
        metadata={
            "document_title": "Quy chế đào tạo năm 2025",
            "article": "Điều 2",
            "clause": "6",
        },
    )
    generated = (
        "Theo Điều 2, Khoản 6, từ Quy chế đào tạo năm 2025, "
        "chương trình Cử nhân có thời gian chuẩn 4 năm."
    )
    sources = [
        {
            "content": "Điều 2 Khoản 6: Cử nhân có thời gian 4 năm.",
            "metadata": {
                "title": "Quy chế đào tạo năm 2025",
                "article": "Điều 2",
                "clause": "6",
            },
            "collection": "quydinh",
        }
    ]

    metrics = calculate_metrics(sample, generated, sources)

    assert metrics["answer_nonempty"] is True
    assert metrics["num_sources"] == 1
    assert metrics["reference_keyword_coverage"] > 0.5
    assert metrics["atomic_fact_coverage"] == 1.0
    assert metrics["citation_text_hit"] is True
    assert metrics["expected_doc_hit"] is True
    assert metrics["expected_article_hit"] is True
    assert metrics["expected_clause_hit"] is True


def test_load_incorrect_samples_reads_filtered_json_records(tmp_path):
    from evaluation.rerun_incorrect_sft_backend import load_incorrect_samples

    incorrect_path = tmp_path / "incorrect_results.json"
    incorrect_path.write_text(
        json.dumps(
            [
                {
                    "sample_id": "incorrect-id",
                    "index": 201,
                    "question": "K70: Nếu tôi đạt Bậc 2.3 thì tôi thuộc nhóm mấy?",
                    "reference_answer": "Bậc 2.3 thuộc Nhóm 5.",
                    "doc_type": "Quyết định ngoại ngữ từ K70",
                    "document_title": "Quyết định ngoại ngữ từ K70",
                    "article": "Phụ lục III, Bảng 3.1",
                    "clause": "Ghi chú",
                    "judge_match": "incorrect",
                },
                {
                    "sample_id": "partial-id",
                    "index": 202,
                    "question": "Đã đúng một phần?",
                    "reference_answer": "ref",
                    "doc_type": "doc",
                    "judge_match": "partial",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    samples = load_incorrect_samples(incorrect_path)

    assert len(samples) == 1
    assert samples[0].sample_id == "incorrect-id"
    assert samples[0].index == 201
    assert samples[0].instruction == "K70: Nếu tôi đạt Bậc 2.3 thì tôi thuộc nhóm mấy?"
    assert samples[0].reference_answer == "Bậc 2.3 thuộc Nhóm 5."
    assert samples[0].metadata["article"] == "Phụ lục III, Bảng 3.1"
    assert samples[0].metadata["clause"] == "Ghi chú"


def test_rerun_incorrect_config_from_args_supports_identity_mode():
    from evaluation import rerun_incorrect_sft_backend as runner

    args = runner.build_parser().parse_args(
        ["--identity-mode", "frontend_env", "--auth-token", "token"]
    )

    config = runner._config_from_args(args)

    assert config["identity_mode"] == "frontend_env"
    assert config["auth_token"] == "token"


def test_rerun_incorrect_runner_writes_results(tmp_path, monkeypatch):
    from evaluation import evaluate_sft_backend as backend_eval
    from evaluation import rerun_incorrect_sft_backend as runner

    incorrect_path = tmp_path / "incorrect_results.json"
    incorrect_path.write_text(
        json.dumps(
            [
                {
                    "sample_id": "incorrect-id",
                    "index": 201,
                    "question": "K70: Nếu tôi đạt Bậc 2.3 thì tôi thuộc nhóm mấy?",
                    "reference_answer": "Bậc 2.3 thuộc Nhóm 5.",
                    "doc_type": "Quyết định ngoại ngữ từ K70",
                    "document_title": "Quyết định ngoại ngữ từ K70",
                    "article": "Phụ lục III, Bảng 3.1",
                    "clause": "Ghi chú",
                    "judge_match": "incorrect",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_evaluate_sample(sample, config):
        assert config["identity_mode"] == "anonymous"
        return {
            "sample_id": sample.sample_id,
            "index": sample.index,
            "status": "completed",
            "question": sample.instruction,
            "reference_answer": sample.reference_answer,
            "generated_answer": "Theo Bảng 3.1, Bậc 2.3 thuộc Nhóm 5.",
            "doc_type": sample.doc_type,
            "document_title": sample.metadata["document_title"],
            "article": sample.metadata["article"],
            "clause": sample.metadata["clause"],
            "backend_mode": "rag_v2",
            "route": "simple",
            "num_sources": 1,
            "metrics": {"answer_nonempty": True},
            "latency_ms": 1.0,
            "error": "",
            "judge_match": "correct",
            "judge_reason": "",
        }

    monkeypatch.setattr(backend_eval, "evaluate_sample", fake_evaluate_sample)

    summary = runner.run(
        {
            "incorrect_results_path": str(incorrect_path),
            "output_dir": str(tmp_path / "rerun"),
            "timestamped_run_dir": False,
            "batch_size": 1,
            "batch_concurrency": 1,
            "delay_s": 0,
            "judge_backend": "none",
        }
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "rerun" / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert summary["total_records"] == 1
    assert rows[0]["sample_id"] == "incorrect-id"
    assert rows[0]["batch_index"] == 1
    assert rows[0]["judge_match"] == "correct"
