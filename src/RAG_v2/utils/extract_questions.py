#!/usr/bin/env python3
"""Extract `question` values from a JSONL file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def normalize_question(text: str) -> str:
    """Convert internal newlines/spaces to a single-line string."""
    return " ".join(text.split())


def extract_questions(
    input_path: Path,
    output_path: Path,
    unique: bool,
    keep_jsonl: bool,
) -> tuple[int, int, int]:
    total = 0
    written = 0
    skipped = 0
    seen: set[str] = set()

    with input_path.open("r", encoding="utf-8") as f_in, output_path.open(
        "w", encoding="utf-8"
    ) as f_out:
        for line_no, line in enumerate(f_in, start=1):
            if not line.strip():
                continue

            total += 1

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                skipped += 1
                print(
                    f"[WARN] Invalid JSON at line {line_no}: {exc}",
                    file=sys.stderr,
                )
                continue

            question = obj.get("question")
            if not isinstance(question, str) or not question.strip():
                skipped += 1
                continue

            if unique and question in seen:
                continue
            seen.add(question)

            if keep_jsonl:
                record = {"question": question}
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
            else:
                f_out.write(normalize_question(question) + "\n")

            written += 1

    return total, written, skipped


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract `question` field from a JSONL dataset."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="training_data/train_qa_pairs.jsonl",
        help="Input JSONL path (default: training_data/train_qa_pairs.jsonl)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="training_data/questions.txt",
        help="Output path (default: training_data/questions.txt)",
    )
    parser.add_argument(
        "--unique",
        action="store_true",
        help="Only keep unique question strings.",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help=(
            "Write output as JSONL with {'question': ...}. "
            "Use this to preserve internal newlines."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total, written, skipped = extract_questions(
        input_path=input_path,
        output_path=output_path,
        unique=args.unique,
        keep_jsonl=args.jsonl,
    )

    print(f"Input records: {total}")
    print(f"Questions written: {written}")
    print(f"Skipped records: {skipped}")
    print(f"Output file: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
