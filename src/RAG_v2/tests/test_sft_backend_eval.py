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
    batches = run_dir / "batches"
    batches.mkdir(parents=True)
    completed = SFTSample(1, "done-id", "q1", "", "a1", "doc")
    failed = SFTSample(2, "fail-id", "q2", "", "a2", "doc")
    (batches / "batch_0001.jsonl").write_text(
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
