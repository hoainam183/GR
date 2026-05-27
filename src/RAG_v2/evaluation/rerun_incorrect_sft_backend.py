"""Rerun only SFT backend samples previously judged incorrect.

The input is the JSON/JSONL file produced from ``results.jsonl`` after filtering
``judge_match == "incorrect"``. This runner intentionally reuses
``evaluate_sft_backend`` for request payload construction, metrics, judging,
resume handling, and output formatting so the rerun stays aligned with the
main backend evaluation script and the frontend ``/chat/v3`` request shape.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import evaluate_sft_backend as backend_eval

logger = logging.getLogger(__name__)


CONFIG: Dict[str, Any] = {
    **backend_eval.CONFIG,
    "incorrect_results_path": "evaluation/results/sft_backend_eval/incorrect_results.json",
    "output_dir": "evaluation/results/sft_backend_eval/rerun_incorrect",
    "identity_mode": "anonymous",
    "role": "user",
    "history": [],
    "session_id": "",
    "user_context": None,
    "user_id": "",
    "run_dir": None,
    "timestamped_run_dir": True,
    "merge_child_run_dirs": False,
    "resume_dir": None,
    "batch_size": 1,
    "batch_index": 0,
    "batch_concurrency": 1,
    "limit": 0,
    "start_index": 0,
    "resume_from_index": 0,
    "retry_failed": True,
    "include_judge_match": "incorrect",
    "continue_from_latest": True,
    "latest_run_dir": None,
}


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _read_input_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Incorrect results file not found: {path}")

    if path.suffix.lower() == ".jsonl":
        rows: List[Dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSONL row {path}:{line_no}: {exc}") from exc
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("records", "results", "incorrect", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"Unsupported incorrect results shape in {path}")


def _record_to_sample(record: Dict[str, Any], fallback_index: int) -> backend_eval.SFTSample:
    legacy_input = str(record.get("input") or "")
    parsed_metadata = (
        backend_eval._parse_legacy_input(legacy_input)
        if legacy_input
        else {}
    )
    question = _clean_text(record.get("question") or record.get("instruction"))
    reference = _clean_text(record.get("reference_answer") or record.get("output"))
    doc_type = _clean_text(
        record.get("doc_type")
        or record.get("document_title")
        or parsed_metadata.get("document_title")
    )
    if not question:
        raise ValueError(f"Incorrect record is missing question: {record!r}")

    try:
        index = int(record.get("index") or fallback_index)
    except (TypeError, ValueError):
        index = fallback_index

    sample_id = _clean_text(record.get("sample_id"))
    if not sample_id:
        sample_id = backend_eval._sample_id(index, question, reference, doc_type)

    metadata = {
        "document_title": _clean_text(
            record.get("document_title")
            or parsed_metadata.get("document_title")
            or doc_type
        ),
        "chapter": _clean_text(record.get("chapter") or parsed_metadata.get("chapter")),
        "article": _clean_text(record.get("article") or parsed_metadata.get("article")),
        "clause": _clean_text(record.get("clause") or parsed_metadata.get("clause")),
        "effective_date": _clean_text(
            record.get("effective_date")
            or parsed_metadata.get("effective_date")
        ),
        "ground_truth_context_text": _clean_text(
            record.get("ground_truth_context_text")
            or parsed_metadata.get("ground_truth_context_text")
        ),
    }
    return backend_eval.SFTSample(
        index=index,
        sample_id=sample_id,
        instruction=question,
        input=legacy_input,
        reference_answer=reference,
        doc_type=doc_type,
        metadata=metadata,
    )


def _record_matches_sample(record: Dict[str, Any], sample: backend_eval.SFTSample) -> bool:
    question = _clean_text(record.get("question") or record.get("instruction"))
    reference = _clean_text(record.get("reference_answer") or record.get("output"))
    doc_type = _clean_text(record.get("doc_type") or record.get("document_title"))

    if question:
        if question != sample.instruction:
            return False
        return not doc_type or doc_type == sample.doc_type

    if reference and reference != sample.reference_answer:
        return False
    if doc_type and doc_type != sample.doc_type:
        return False
    return bool(reference or doc_type)


def _canonical_sample_for_record(
    record: Dict[str, Any],
    *,
    samples_by_id: Dict[str, backend_eval.SFTSample],
    samples_by_index: Dict[int, backend_eval.SFTSample],
) -> Optional[backend_eval.SFTSample]:
    sample_id = _clean_text(record.get("sample_id"))
    if sample_id:
        sample = samples_by_id.get(sample_id)
        if sample is not None:
            return sample
        return None

    try:
        index = int(record.get("index") or 0)
    except (TypeError, ValueError):
        index = 0
    sample = samples_by_index.get(index)
    if sample is not None and _record_matches_sample(record, sample):
        return sample

    return None


def _load_canonical_sample_maps(
    dataset_path: str | Path | None,
) -> tuple[Dict[str, backend_eval.SFTSample], Dict[int, backend_eval.SFTSample]]:
    if not dataset_path:
        return {}, {}

    path = _resolve_project_path(dataset_path)
    if not path.exists():
        logger.warning(
            "Canonical SFT dataset not found, using incorrect records only: %s",
            path,
        )
        return {}, {}

    canonical_samples = backend_eval.load_sft_dataset(path)
    return (
        {sample.sample_id: sample for sample in canonical_samples},
        {sample.index: sample for sample in canonical_samples},
    )


def load_incorrect_samples(
    incorrect_results_path: str | Path,
    *,
    include_judge_match: Optional[str] = "incorrect",
    dataset_path: str | Path | None = None,
) -> List[backend_eval.SFTSample]:
    path = _resolve_project_path(incorrect_results_path)
    records = _read_input_records(path)
    samples: List[backend_eval.SFTSample] = []
    samples_by_id, samples_by_index = _load_canonical_sample_maps(dataset_path)
    canonical_hits = 0

    for fallback_index, record in enumerate(records, start=1):
        if include_judge_match:
            judge_match = _clean_text(record.get("judge_match")).lower()
            if judge_match != include_judge_match.lower():
                continue
        canonical_sample = _canonical_sample_for_record(
            record,
            samples_by_id=samples_by_id,
            samples_by_index=samples_by_index,
        )
        if canonical_sample is not None:
            samples.append(canonical_sample)
            canonical_hits += 1
        else:
            samples.append(_record_to_sample(record, fallback_index))

    if samples_by_id:
        logger.info(
            "Resolved %d/%d rerun sample(s) from canonical SFT dataset",
            canonical_hits,
            len(samples),
        )

    return samples


def _is_timestamp_run_dir(path: Path) -> bool:
    return path.is_dir() and re.fullmatch(r"\d{8}_\d{6}", path.name) is not None


def _find_latest_timestamp_run_dir(output_dir: str | Path) -> Optional[Path]:
    root = _resolve_project_path(output_dir)
    if not root.exists():
        return None

    run_dirs = [
        child
        for child in root.iterdir()
        if _is_timestamp_run_dir(child)
    ]
    if not run_dirs:
        return None
    return max(run_dirs, key=lambda path: path.name)


def _latest_rerun_source_dir(config: Dict[str, Any]) -> Optional[Path]:
    latest_run_dir = config.get("latest_run_dir")
    if latest_run_dir:
        path = _resolve_project_path(str(latest_run_dir))
        if not path.exists():
            raise FileNotFoundError(f"Latest rerun directory not found: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Latest rerun path is not a directory: {path}")
        return path

    return _find_latest_timestamp_run_dir(str(config["output_dir"]))


def _load_progress_statuses(run_dir: Path) -> Dict[str, str]:
    progress_path = run_dir / "progress.json"
    if not progress_path.exists():
        return {}

    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    statuses = payload.get("sample_statuses") if isinstance(payload, dict) else None
    if not isinstance(statuses, dict):
        return {}
    return {
        str(sample_id): str(status)
        for sample_id, status in statuses.items()
        if str(sample_id)
    }


def _dedupe_samples(samples: Iterable[backend_eval.SFTSample]) -> List[backend_eval.SFTSample]:
    selected: List[backend_eval.SFTSample] = []
    seen: set[str] = set()
    for sample in samples:
        if sample.sample_id in seen:
            continue
        seen.add(sample.sample_id)
        selected.append(sample)
    return selected


def _select_continue_samples(
    samples: List[backend_eval.SFTSample],
    latest_run_dir: Path,
) -> tuple[List[backend_eval.SFTSample], Dict[str, Any]]:
    records = backend_eval.load_existing_records(
        latest_run_dir,
        include_child_run_dirs=False,
    )
    progress_statuses = _load_progress_statuses(latest_run_dir)
    touched_ids = set(records) | set(progress_statuses)
    if not touched_ids:
        return samples, {
            "mode": "empty_previous",
            "source_dir": str(latest_run_dir),
            "selected_count": len(samples),
        }

    failed_ids = {
        sample_id
        for sample_id, status in progress_statuses.items()
        if status.lower() == "failed"
    }
    failed_ids.update(
        sample_id
        for sample_id, record in records.items()
        if _clean_text(record.get("status")).lower() == "failed"
    )
    still_incorrect_ids = {
        sample_id
        for sample_id, record in records.items()
        if _clean_text(record.get("judge_match")).lower() == "incorrect"
    }
    sample_ids = {sample.sample_id for sample in samples}
    failed_ids &= sample_ids
    still_incorrect_ids &= sample_ids
    unresolved_ids = failed_ids | still_incorrect_ids

    anchor_position = -1
    anchor_sample: Optional[backend_eval.SFTSample] = None
    for position, sample in enumerate(samples):
        if sample.sample_id in touched_ids:
            anchor_position = position
            anchor_sample = sample

    if anchor_position < 0 or anchor_sample is None:
        raise ValueError(
            "Latest rerun source has no overlapping sample_id with incorrect input: "
            f"{latest_run_dir}"
        )

    unresolved_samples = [
        sample
        for sample in samples[:anchor_position + 1]
        if sample.sample_id in unresolved_ids
    ]
    tail_samples = samples[anchor_position + 1:]
    selected = _dedupe_samples([*unresolved_samples, *tail_samples])
    return selected, {
        "mode": "continue",
        "source_dir": str(latest_run_dir),
        "anchor_position": anchor_position + 1,
        "anchor_index": anchor_sample.index,
        "anchor_sample_id": anchor_sample.sample_id,
        "input_count": len(samples),
        "failed_count": len(failed_ids),
        "still_incorrect_count": len(still_incorrect_ids),
        "unresolved_count": len(unresolved_ids),
        "tail_count": len(tail_samples),
        "selected_count": len(selected),
        "deduped_count": len(unresolved_samples) + len(tail_samples) - len(selected),
    }


def _select_continue_samples_from_config(
    samples: List[backend_eval.SFTSample],
    config: Dict[str, Any],
) -> tuple[List[backend_eval.SFTSample], Dict[str, Any]]:
    if not backend_eval._config_bool(config, "continue_from_latest", True):
        return samples, {"mode": "from_start", "selected_count": len(samples)}
    if config.get("resume_dir"):
        return samples, {"mode": "resume_dir", "selected_count": len(samples)}

    latest_run_dir = _latest_rerun_source_dir(config)
    if latest_run_dir is None:
        return samples, {"mode": "no_previous", "selected_count": len(samples)}

    return _select_continue_samples(samples, latest_run_dir)


def _config_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    config = dict(CONFIG)
    for key in (
        "incorrect_results_path",
        "dataset_path",
        "backend_url",
        "output_dir",
        "run_dir",
        "resume_dir",
        "batch_size",
        "batch_index",
        "batch_concurrency",
        "limit",
        "start_index",
        "top_k",
        "mode",
        "timeout_s",
        "delay_s",
        "judge_backend",
        "identity_mode",
        "auth_token",
        "latest_run_dir",
    ):
        value = getattr(args, key)
        if value is not None:
            config[key] = value

    if args.include_all:
        config["include_judge_match"] = None
    elif args.include_judge_match is not None:
        config["include_judge_match"] = args.include_judge_match

    if args.no_timestamp:
        config["timestamped_run_dir"] = False
    if args.from_start:
        config["continue_from_latest"] = False
    if args.send_null_optional_fields:
        config["send_null_optional_fields"] = True
    return config


def _write_latest(run_id: str, run_dir: Path, summary: Dict[str, Any], config: Dict[str, Any]) -> None:
    output_root = _resolve_project_path(str(config["output_dir"]))
    output_root.mkdir(parents=True, exist_ok=True)
    backend_eval._atomic_write_json(
        output_root / "latest.json",
        {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "incorrect_results_path": str(_resolve_project_path(str(config["incorrect_results_path"]))),
            "summary": summary,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


def run(config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    config = dict(CONFIG, **config)
    all_samples = load_incorrect_samples(
        str(config["incorrect_results_path"]),
        include_judge_match=config.get("include_judge_match"),
        dataset_path=config.get("dataset_path"),
    )
    base_samples, continue_info = _select_continue_samples_from_config(
        all_samples,
        config,
    )
    samples = backend_eval._select_samples(
        base_samples,
        config,
    )
    run_id, run_dir = backend_eval._prepare_run_dir(config)
    batches = backend_eval._select_batches(samples, config)
    records = backend_eval.load_existing_records(
        run_dir,
        include_child_run_dirs=backend_eval._config_bool(config, "merge_child_run_dirs", False),
    )

    logger.info("Rerun directory: %s", run_dir)
    logger.info("Incorrect input: %s", _resolve_project_path(str(config["incorrect_results_path"])))
    if continue_info.get("mode") == "continue":
        logger.info("Continue source run: %s", continue_info["source_dir"])
        logger.info(
            "Continue anchor: position=%d/%d index=%s sample=%s",
            continue_info["anchor_position"],
            continue_info["input_count"],
            continue_info["anchor_index"],
            continue_info["anchor_sample_id"],
        )
        logger.info(
            "Continue selected: failed=%d still_incorrect=%d tail=%d total=%d deduped=%d",
            continue_info["failed_count"],
            continue_info["still_incorrect_count"],
            continue_info["tail_count"],
            continue_info["selected_count"],
            continue_info["deduped_count"],
        )
    elif continue_info.get("mode") == "no_previous":
        logger.info("No previous rerun source found; starting from incorrect input.")
    elif continue_info.get("mode") == "empty_previous":
        logger.info(
            "Latest rerun source has no records; starting from incorrect input: %s",
            continue_info["source_dir"],
        )
    elif continue_info.get("mode") == "from_start":
        logger.info("Continue-from-latest disabled; starting from incorrect input.")
    elif continue_info.get("mode") == "resume_dir":
        logger.info("resume_dir is set; using existing in-place resume behavior.")
    logger.info("Loaded %d selected sample(s)", len(samples))
    logger.info("Selected %d batch(es)", len(batches))
    logger.info("Existing records: %d", len(records))
    inter_test_delay_s = backend_eval._inter_test_delay_s(config)
    logger.info(
        "Inter-test delay: %.1fs (llm_rpm=%s, llm_calls_per_test=%s)",
        inter_test_delay_s,
        config.get("llm_rpm"),
        config.get("llm_calls_per_test"),
    )
    if (
        inter_test_delay_s > 0
        and int(config.get("batch_size") or 1) != 1
    ):
        logger.warning(
            "delay_s is applied between batches; set batch_size=1 for true inter-test pacing."
        )
    if (
        inter_test_delay_s > 0
        and int(config.get("batch_concurrency") or 1) != 1
    ):
        logger.warning(
            "batch_concurrency > 1 can exceed RPM even with delay_s; use 1 for rate-limited runs."
        )

    if not batches:
        logger.warning("No batches selected. Check incorrect input, start_index, limit, and batch_index.")
        backend_eval._write_progress(
            run_dir=run_dir,
            run_id=run_id,
            samples_total=len(samples),
            records=records,
            config=config,
        )

    for batch_position, (batch_no, batch_samples) in enumerate(batches, start=1):
        written = backend_eval._evaluate_batch(
            batch_no=batch_no,
            batch_samples=batch_samples,
            records=records,
            run_dir=run_dir,
            run_id=run_id,
            samples_total=len(samples),
            config=config,
        )
        backend_eval._atomic_write_json(
            run_dir / "summary_partial.json",
            backend_eval.build_summary(records.values()),
        )

        if written > 0 and inter_test_delay_s > 0 and batch_position < len(batches):
            logger.info("Sleeping %.1fs for RPM pacing", inter_test_delay_s)
            time.sleep(inter_test_delay_s)

    summary = backend_eval._write_final_outputs(run_dir, records)
    _write_latest(run_id, run_dir, summary, config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rerun /chat/v3 evaluation for records judged incorrect.",
    )
    parser.add_argument(
        "--incorrect-results-path",
        default=None,
        help="JSON/JSONL path containing previous incorrect records.",
    )
    parser.add_argument(
        "--dataset-path",
        default=None,
        help="Canonical SFT JSONL dataset used to rebuild samples exactly like evaluate_sft_backend.py.",
    )
    parser.add_argument("--backend-url", default=None, help="Backend chat URL, defaults to VITE_API_URL/chat/v3.")
    parser.add_argument("--output-dir", default=None, help="Directory for rerun outputs.")
    parser.add_argument("--run-dir", default=None, help="Use a specific run directory.")
    parser.add_argument("--resume-dir", default=None, help="Resume an existing run directory.")
    parser.add_argument(
        "--latest-run-dir",
        default=None,
        help="Previous rerun directory to continue from. Defaults to newest timestamped output_dir child.",
    )
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--batch-index", type=int, default=None, help="1-based batch number; 0 means all.")
    parser.add_argument("--batch-concurrency", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-index", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--mode", choices=("auto", "rag", "agent"), default=None)
    parser.add_argument("--timeout-s", type=float, default=None)
    parser.add_argument("--delay-s", type=float, default=None)
    parser.add_argument("--judge-backend", choices=("none", "lmstudio", "gemini"), default=None)
    parser.add_argument(
        "--identity-mode",
        choices=("anonymous", "frontend_env"),
        default=None,
        help='Request identity mode. Default: "anonymous"; use "frontend_env" for EVAL_* identity.',
    )
    parser.add_argument("--auth-token", default=None)
    parser.add_argument(
        "--include-judge-match",
        default=None,
        help='Only rerun records with this judge_match value. Default: "incorrect".',
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Rerun every record in the input file regardless of judge_match.",
    )
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="Write directly into output_dir instead of output_dir/YYYYMMDD_HHMMSS.",
    )
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="Disable continue-from-latest selection and rerun from the beginning of the input.",
    )
    parser.add_argument(
        "--send-null-optional-fields",
        action="store_true",
        help="Send null session/user fields instead of omitting them.",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return run(_config_from_args(args))


if __name__ == "__main__":
    main()
