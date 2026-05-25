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
    "retry_failed": True,
    "include_judge_match": "incorrect",
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
    question = _clean_text(record.get("question") or record.get("instruction"))
    reference = _clean_text(record.get("reference_answer") or record.get("output"))
    doc_type = _clean_text(record.get("doc_type") or record.get("document_title"))
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
        "document_title": _clean_text(record.get("document_title") or doc_type),
        "chapter": _clean_text(record.get("chapter")),
        "article": _clean_text(record.get("article")),
        "clause": _clean_text(record.get("clause")),
        "effective_date": _clean_text(record.get("effective_date")),
        "ground_truth_context_text": _clean_text(record.get("ground_truth_context_text")),
    }
    return backend_eval.SFTSample(
        index=index,
        sample_id=sample_id,
        instruction=question,
        input="",
        reference_answer=reference,
        doc_type=doc_type,
        metadata=metadata,
    )


def load_incorrect_samples(
    incorrect_results_path: str | Path,
    *,
    include_judge_match: Optional[str] = "incorrect",
) -> List[backend_eval.SFTSample]:
    path = _resolve_project_path(incorrect_results_path)
    records = _read_input_records(path)
    samples: List[backend_eval.SFTSample] = []

    for fallback_index, record in enumerate(records, start=1):
        if include_judge_match:
            judge_match = _clean_text(record.get("judge_match")).lower()
            if judge_match != include_judge_match.lower():
                continue
        samples.append(_record_to_sample(record, fallback_index))

    return samples


def _config_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    config = dict(CONFIG)
    for key in (
        "incorrect_results_path",
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
    run_id, run_dir = backend_eval._prepare_run_dir(config)
    samples = backend_eval._select_samples(
        load_incorrect_samples(
            str(config["incorrect_results_path"]),
            include_judge_match=config.get("include_judge_match"),
        ),
        config,
    )
    batches = backend_eval._select_batches(samples, config)
    records = backend_eval.load_existing_records(
        run_dir,
        include_child_run_dirs=backend_eval._config_bool(config, "merge_child_run_dirs", False),
    )

    logger.info("Rerun directory: %s", run_dir)
    logger.info("Incorrect input: %s", _resolve_project_path(str(config["incorrect_results_path"])))
    logger.info("Loaded %d selected sample(s)", len(samples))
    logger.info("Selected %d batch(es)", len(batches))
    logger.info("Existing records: %d", len(records))

    if not batches:
        logger.warning("No batches selected. Check incorrect input, start_index, limit, and batch_index.")
        backend_eval._write_progress(
            run_dir=run_dir,
            run_id=run_id,
            samples_total=len(samples),
            records=records,
            config=config,
        )

    for batch_no, batch_samples in batches:
        backend_eval._evaluate_batch(
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

        delay = float(config.get("delay_s") or 0.0)
        if delay > 0:
            time.sleep(delay)

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
    parser.add_argument("--backend-url", default=None, help="Backend chat URL, defaults to VITE_API_URL/chat/v3.")
    parser.add_argument("--output-dir", default=None, help="Directory for rerun outputs.")
    parser.add_argument("--run-dir", default=None, help="Use a specific run directory.")
    parser.add_argument("--resume-dir", default=None, help="Resume an existing run directory.")
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
