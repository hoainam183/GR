from __future__ import annotations

import json


def test_dataset_adapter_maps_items_and_duplicate_safe_ids(tmp_path):
    from evaluation.evaluate_rag_datasets import build_chunk_index, load_dataset_file

    data_root = tmp_path / "data"
    chunks_dir = data_root / "quydinh" / "chunks"
    chunks_dir.mkdir(parents=True)
    (chunks_dir / "sample_chunks.json").write_text(
        json.dumps(
            [
                {"id": "doc-1", "chunk_id": "chunk_0001", "content": "ctx"},
                {"id": "doc-2", "chunk_id": "chunk_0002", "content": "ctx"},
            ]
        ),
        encoding="utf-8",
    )
    dataset = tmp_path / "eval_dataset.json"
    dataset.write_text(
        json.dumps(
            {
                "dataset_name": "unit",
                "source_file": "source_chunks.json",
                "total_questions": 2,
                "items": [
                    {
                        "id": "same",
                        "question_type": "multi-hop",
                        "question": "What is supported?",
                        "gold_answer": "Answer 42.",
                        "evidence_chunk_ids": ["doc-1", "doc-2"],
                        "ground_truth_context": ["ctx 1", "ctx 2"],
                        "is_answerable": True,
                        "reasoning_required": "multi_chunk",
                        "difficulty": "medium",
                    },
                    {
                        "id": "same",
                        "question_type": "adversarial",
                        "question": "Unknown?",
                        "gold_answer": "No information.",
                        "evidence_chunk_ids": [],
                        "ground_truth_context": [],
                        "is_answerable": False,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    chunk_index = build_chunk_index(data_root)
    cases = load_dataset_file(dataset, chunk_index=chunk_index)

    assert len(cases) == 2
    assert cases[0].case_uid == "eval_dataset::same"
    assert cases[1].case_uid == "eval_dataset::same"
    assert cases[0].question_type == "multi_hop"
    assert cases[0].reference_answer == "Answer 42."
    assert cases[0].expected_source_ids == ["doc-1", "doc-2"]
    assert cases[0].ground_truth_context_texts == ["ctx 1", "ctx 2"]
    assert cases[0].expected_collection == "quydinh"
    assert cases[1].expected_behavior == "refuse_insufficient_context"


def test_validate_cases_reports_duplicates_and_evidence_coverage(tmp_path):
    from evaluation.evaluate_rag_datasets import build_chunk_index, load_dataset_file, validate_cases

    data_root = tmp_path / "data"
    chunks_dir = data_root / "quydinh" / "chunks"
    chunks_dir.mkdir(parents=True)
    (chunks_dir / "sample_chunks.json").write_text(
        json.dumps([{"id": "doc-1", "content": "ctx"}]),
        encoding="utf-8",
    )
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "dup",
                        "question_type": "simple",
                        "question": "Q1",
                        "gold_answer": "A1",
                        "evidence_chunk_ids": ["doc-1"],
                        "ground_truth_context": ["ctx"],
                        "is_answerable": True,
                    },
                    {
                        "id": "dup",
                        "question_type": "simple",
                        "question": "Q2",
                        "gold_answer": "A2",
                        "evidence_chunk_ids": ["missing"],
                        "ground_truth_context": ["ctx"],
                        "is_answerable": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    index = build_chunk_index(data_root)
    cases = load_dataset_file(dataset, chunk_index=index)
    summary = validate_cases(cases, chunk_index=index)

    assert summary["duplicate_original_id_count"] == 1
    assert summary["evidence_ref_count"] == 2
    assert summary["evidence_ref_missing_in_chunks"] == 1
    assert summary["evidence_ref_coverage"] == 0.5


def test_ranking_metrics_cover_cutoffs_and_all_evidence():
    from evaluation.evaluate_rag_datasets import compute_context_text_metrics, compute_ranking_metrics

    metrics = compute_ranking_metrics(["doc-a", "x", "doc-b"], ["doc-a", "doc-b"], cutoffs=(1, 3, 5))
    text_metrics = compute_context_text_metrics(
        ["The disability student policy includes tuition support."],
        ["Disability student policy includes tuition support."],
        cutoffs=(1, 3),
    )

    assert metrics["hit@1"] == 1.0
    assert metrics["recall@1"] == 0.5
    assert metrics["precision@3"] == 0.6667
    assert metrics["recall@3"] == 1.0
    assert metrics["mrr@3"] == 1.0
    assert metrics["all_evidence_recalled"] == 1.0
    assert text_metrics["context_text_hit@1"] == 1.0
    assert text_metrics["context_text_recall@1"] == 1.0


def test_source_id_extractor_uses_doc_and_metadata_fallbacks():
    from evaluation.evaluate_rag_datasets import _source_id

    assert _source_id({"id": "collection/doc-1"}) == "doc-1"
    assert _source_id({"chunk_id": "chunk-2"}) == "chunk-2"
    assert _source_id({"source_id": "source-3"}) == "source-3"
    assert _source_id({"metadata": {"chunk_id": "chunk-4"}}) == "chunk-4"
    assert _source_id({"metadata": {"id": "doc-5"}}) == "doc-5"
    assert _source_id({"metadata": {"doc_id": "doc-6"}}) == "doc-6"
    assert _source_id({"metadata": {"document_id": "doc-7"}}) == "doc-7"


def test_retrieval_variant_metrics_include_collection_and_multi_hop():
    from evaluation.evaluate_rag_datasets import (
        RAGDatasetCase,
        compute_retrieval_variant_metrics,
    )

    case = RAGDatasetCase(
        case_uid="dataset::1",
        dataset_file="dataset.json",
        dataset_name="dataset",
        source_file="source.json",
        original_id="1",
        item_index=1,
        question_type="multi_hop",
        question="Q",
        reference_answer="A",
        expected_source_ids=["doc-a", "doc-b"],
        expected_collection="quydinh",
    )

    metrics = compute_retrieval_variant_metrics(
        retrieved_ids=["doc-b", "x", "doc-a"],
        retrieved_collections=["quydinh"],
        case=case,
        top_k=5,
    )

    assert metrics["hit@1"] == 1.0
    assert metrics["recall@5"] == 1.0
    assert metrics["collection_hit"] == 1.0
    assert metrics["all_evidence_recalled"] == 1.0
    assert metrics["multi_hop_all_evidence_recalled"] == 1.0


def test_retrieval_results_payload_aggregates_variants_by_dataset_and_type(tmp_path):
    from evaluation.evaluate_rag_datasets import (
        RAGDatasetCase,
        build_retrieval_results_payload,
        write_retrieval_results_csv,
        write_retrieval_results_json,
    )

    case = RAGDatasetCase(
        case_uid="dataset::1",
        dataset_file="dataset.json",
        dataset_name="dataset",
        source_file="source.json",
        original_id="1",
        item_index=1,
        question_type="simple",
        question="Q",
        reference_answer="A",
        expected_source_ids=["doc-a"],
        expected_collection="quydinh",
    )
    record = {
        "case_uid": case.case_uid,
        "dataset_file": case.dataset_file,
        "dataset_name": case.dataset_name,
        "source_file": case.source_file,
        "original_id": case.original_id,
        "question": case.question,
        "question_type": case.question_type,
        "difficulty": case.difficulty,
        "reasoning_required": case.reasoning_required,
        "answerable": case.answerable,
        "expected_source_ids": case.expected_source_ids,
        "expected_collection": case.expected_collection,
        "target_collections": ["quydinh"],
        "status": "completed",
        "error": None,
        "variants": {
            "no_rerank": {
                "status": "completed",
                "error": None,
                "retrieved_ids": ["x"],
                "retrieved_collections": ["quydinh"],
                "source_count": 1,
                "latency_ms": 10.0,
                "metrics": {
                    "hit@1": 0.0,
                    "hit@3": 0.0,
                    "hit@5": 0.0,
                    "recall@5": 0.0,
                    "mrr@5": 0.0,
                    "collection_hit": 1.0,
                    "all_evidence_recalled": 0.0,
                    "latency_ms": 10.0,
                    "error": 0.0,
                },
            },
            "rerank": {
                "status": "completed",
                "error": None,
                "retrieved_ids": ["doc-a"],
                "retrieved_collections": ["quydinh"],
                "source_count": 1,
                "latency_ms": 12.0,
                "metrics": {
                    "hit@1": 1.0,
                    "hit@3": 1.0,
                    "hit@5": 1.0,
                    "recall@5": 1.0,
                    "mrr@5": 1.0,
                    "collection_hit": 1.0,
                    "all_evidence_recalled": 1.0,
                    "latency_ms": 12.0,
                    "error": 0.0,
                },
            },
        },
    }

    payload = build_retrieval_results_payload(
        cases=[case],
        records=[record],
        validation={"schema_valid_rate": 1.0},
        top_k=5,
        run_config={"mode": "offline_retrieval"},
    )
    json_path = tmp_path / "results.json"
    csv_path = tmp_path / "results.csv"
    write_retrieval_results_json(json_path, payload)
    write_retrieval_results_csv(csv_path, payload["cases"])

    assert payload["summary"]["overall"]["no_rerank"]["hit@1"] == 0.0
    assert payload["summary"]["overall"]["rerank"]["hit@1"] == 1.0
    assert payload["summary"]["delta"]["recall@5"] == 1.0
    assert payload["summary"]["by_dataset"]["dataset.json"]["rerank"]["hit@5"] == 1.0
    assert payload["summary"]["by_question_type"]["simple"]["delta"]["mrr@5"] == 1.0
    assert json.loads(json_path.read_text(encoding="utf-8"))["run_config"]["top_k"] == 5
    csv_text = csv_path.read_text(encoding="utf-8-sig")
    assert "no_rerank_retrieved_ids" in csv_text
    assert "rerank_retrieved_ids" in csv_text
    assert "delta_recall@5" in csv_text


def test_answer_metrics_refusal_and_token_scores():
    from evaluation.evaluate_rag_datasets import RAGDatasetCase, compute_answer_metrics

    case = RAGDatasetCase(
        case_uid="dataset::1",
        dataset_file="dataset.json",
        dataset_name="dataset",
        source_file="source.json",
        original_id="1",
        item_index=1,
        question_type="adversarial",
        question="Unknown?",
        reference_answer="No information is available.",
        answerable=False,
        expected_behavior="refuse_insufficient_context",
    )

    metrics = compute_answer_metrics(case, "Khong co du thong tin trong tai lieu.")

    assert metrics["answer_nonempty"] is True
    assert metrics["refused"] is True
    assert metrics["refusal_accuracy"] == 1.0
    assert metrics["over_answer"] == 0.0


def test_summary_aggregates_live_records():
    from evaluation.evaluate_rag_datasets import RAGDatasetCase, build_eval_summary

    cases = [
        RAGDatasetCase(
            case_uid="dataset::1",
            dataset_file="dataset.json",
            dataset_name="dataset",
            source_file="source.json",
            original_id="1",
            item_index=1,
            question_type="simple",
            question="Q",
            reference_answer="A",
            difficulty="easy",
        )
    ]
    records = [
        {
            "status": "completed",
            "latency_ms": 100.0,
            "setup_invalid": False,
            "metrics": {
                "answer_nonempty": True,
                "token_f1": 0.5,
                "source_hit@5": 1.0,
                "citation_source_hit": 1.0,
            },
        }
    ]

    summary = build_eval_summary(
        cases,
        validation={"schema_valid_rate": 1.0},
        live_records=records,
    )

    assert summary["live"]["completed"] == 1
    assert summary["live"]["failed"] == 0
    assert summary["live"]["metrics"]["answer_nonempty"] == 1.0
    assert summary["live"]["metrics"]["token_f1"] == 0.5
    assert summary["breakdowns"]["by_question_type"] == {"simple": 1}
