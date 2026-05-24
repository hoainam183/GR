from __future__ import annotations

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
