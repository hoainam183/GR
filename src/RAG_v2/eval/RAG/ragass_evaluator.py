"""
ragass_evaluator.py — RAGAS evaluation trên dataset đã tạo bởi ragass_generator.py.

Tập trung vào 2 metrics chính:
  - context_recall    : RAG system có retrieve đủ các chunks cần thiết không?
  - context_precision : RAG system có retrieve chunks không liên quan không?

Hỗ trợ 2 mode:
  Mode 1 — Dataset Validation (không cần RAG system thật):
    Dùng ground_truth_context_texts làm "retrieved contexts".
    Giúp validate dataset quality: LLM judge có đồng ý answer được support bởi contexts không?

  Mode 2 — Full RAG Evaluation (kết nối RAG system thật):
    Thay thế retrieved_contexts bằng kết quả thật từ RAG system.
    (TODO: implement kết nối với RAG pipeline)

Chạy:
    python eval/RAG/ragass_evaluator.py                           # Mode 1 (default)
    python eval/RAG/ragass_evaluator.py --dataset outputs/ragass_dataset.jsonl
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Tải file .env từ thư mục gốc RAG_v2
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — Sửa tại đây
# ─────────────────────────────────────────────────────────────────────────────

CONFIG = {
    # ── Input / Output ────────────────────────────────────────────────────────
    "dataset_path": Path(__file__).parent / "outputs" / "ragass_dataset.jsonl",
    "output_dir":   Path(__file__).parent / "outputs",
    "output_file":  "ragass_eval_result.json",

    # ── RAGAS LLM (Gemini) ────────────────────────────────────────────────────
    "gemini_api_key": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "",
    "gemini_model":   "gemini-3.1-flash-lite-preview",

    # ── RAGAS metrics ─────────────────────────────────────────────────────────
    # Focus: context_recall + context_precision
    # Nếu muốn thêm: "faithfulness", "answer_relevancy"
    "ragas_metrics": ["context_recall", "context_precision"],

    # ── Filter ────────────────────────────────────────────────────────────────
    # Chỉ evaluate subset loại câu hỏi. None = evaluate tất cả.
    "filter_question_types": None,   # hoặc ["single", "multi"], ["adversarial"], v.v.

    # ── Mode ──────────────────────────────────────────────────────────────────
    # "dataset_validation": dùng ground_truth_contexts làm retrieved_contexts
    # "full_rag": gọi RAG system thật (chưa implement)
    "eval_mode": "dataset_validation",
}

# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EvalSample:
    """Một sample cho RAGAS evaluate."""
    question: str
    answer: str                          # câu trả lời (ground_truth trong Mode 1)
    contexts: List[str]                  # retrieved contexts (text)
    ground_truth: str                    # đáp án chuẩn
    ground_truth_contexts: List[str]     # chunk IDs chuẩn
    question_type: str
    source: str


@dataclass
class RAGASSEvalResult:
    """Kết quả evaluation tổng hợp."""
    eval_mode: str
    total_samples: int
    metrics: Dict[str, float] = field(default_factory=dict)
    per_type_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    per_sample_scores: List[Dict] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"\n{'='*60}",
            f" RAGAS Evaluation Results (mode={self.eval_mode})",
            f"{'='*60}",
            f" Tổng số mẫu: {self.total_samples}",
            "",
            " 📊 Overall Metrics:",
        ]
        for key, val in self.metrics.items():
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            lines.append(f"   {key:<25}: {val:.3f} |{bar}|")

        if self.per_type_metrics:
            lines.append("")
            lines.append(" 📋 Breakdown by Question Type:")
            for qtype, m in self.per_type_metrics.items():
                lines.append(f"   [{qtype}]")
                for key, val in m.items():
                    lines.append(f"     {key:<23}: {val:.3f}")

        lines.append(f"{'='*60}\n")
        return "\n".join(lines)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "eval_mode": self.eval_mode,
            "total_samples": self.total_samples,
            "metrics": self.metrics,
            "per_type_metrics": self.per_type_metrics,
            "per_sample_scores": self.per_sample_scores,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("✅ Eval results saved → %s", path)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset loader
# ─────────────────────────────────────────────────────────────────────────────


def load_dataset(
    dataset_path: Path,
    filter_types: Optional[List[str]] = None,
) -> List[EvalSample]:
    """
    Load JSONL dataset từ ragass_generator.py output.

    Args:
        dataset_path: Path tới .jsonl file
        filter_types: Optional list question types để filter (None = tất cả)

    Returns:
        List[EvalSample]
    """
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset không tìm thấy: {dataset_path}")

    samples = []
    with open(dataset_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning("Line %d: JSON parse error: %s", lineno, e)
                continue

            qtype = item.get("question_type", "unknown")
            if filter_types and qtype not in filter_types:
                continue

            samples.append(EvalSample(
                question=item.get("question", ""),
                answer=item.get("ground_truth", ""),      # Mode 1: answer = ground_truth
                contexts=item.get("ground_truth_context_texts", []),
                ground_truth=item.get("ground_truth", ""),
                ground_truth_contexts=item.get("ground_truth_contexts", []),
                question_type=qtype,
                source=item.get("source", "unknown"),
            ))

    logger.info(
        "Loaded %d samples từ %s (filter_types=%s)",
        len(samples), dataset_path.name, filter_types,
    )
    return samples


# ─────────────────────────────────────────────────────────────────────────────
# RAGAS wrapper
# ─────────────────────────────────────────────────────────────────────────────


def _build_ragas_llm_and_emb(api_key: str, model: str):
    """Tạo RAGAS-compatible LLM + Embeddings từ Gemini."""
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    lc_llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=0.0,
    )
    lc_emb = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=api_key,  # type: ignore
    )
    return LangchainLLMWrapper(lc_llm), LangchainEmbeddingsWrapper(lc_emb)


def _load_ragas_metrics(metric_names: List[str], ragas_llm, ragas_emb):
    """Load và configure RAGAS metrics."""
    from ragas.metrics import context_recall, context_precision, faithfulness, answer_relevancy

    metric_map = {
        "context_recall":    context_recall,
        "context_precision": context_precision,
        "faithfulness":      faithfulness,
        "answer_relevancy":  answer_relevancy,
    }

    metrics = []
    for name in metric_names:
        if name not in metric_map:
            logger.warning("Metric '%s' không được hỗ trợ — bỏ qua.", name)
            continue
        m = metric_map[name]
        m.llm = ragas_llm
        if hasattr(m, "embeddings"):
            m.embeddings = ragas_emb
        metrics.append(m)

    return metrics


def run_ragas_eval(
    samples: List[EvalSample],
    metric_names: List[str],
    ragas_llm,
    ragas_emb,
) -> tuple[Dict[str, float], List[Dict]]:
    """
    Chạy RAGAS evaluate.

    Returns:
        (aggregate_metrics, per_sample_scores)
    """
    from datasets import Dataset
    from ragas import evaluate

    data = {
        "question":     [s.question for s in samples],
        "answer":       [s.answer for s in samples],
        "contexts":     [s.contexts for s in samples],
        "ground_truth": [s.ground_truth for s in samples],
    }
    dataset = Dataset.from_dict(data)

    metrics = _load_ragas_metrics(metric_names, ragas_llm, ragas_emb)
    if not metrics:
        raise ValueError("Không có metric hợp lệ nào để evaluate.")

    logger.info("Chạy RAGAS evaluate với %d samples, metrics=%s...", len(samples), metric_names)
    result = evaluate(dataset=dataset, metrics=metrics, raise_exceptions=False)

    # Đảm bảo kiểu dữ liệu trả về cho Pyright / Linter static analysis
    from ragas.dataset_schema import EvaluationResult  # type: ignore
    if not isinstance(result, EvaluationResult):
        raise RuntimeError(f"RAGAS evaluate() returned unexpected object of type {type(result)} instead of EvaluationResult.")

    # Aggregate scores
    result_df = result.to_pandas()
    aggregate = {}
    for name in metric_names:
        if name in result_df.columns:
            aggregate[name] = result_df[name].mean()

    # Per-sample
    per_sample = result_df.to_dict(orient="records")
    # Thêm metadata từ samples
    for i, row in enumerate(per_sample):
        if i < len(samples):
            row["question_type"] = samples[i].question_type
            row["source"] = samples[i].source

    return aggregate, per_sample


# ─────────────────────────────────────────────────────────────────────────────
# Breakdown by question type
# ─────────────────────────────────────────────────────────────────────────────


def compute_per_type_metrics(
    per_sample: List[Dict],
    metric_names: List[str],
) -> Dict[str, Dict[str, float]]:
    """Tính trung bình metrics cho mỗi question_type."""
    from collections import defaultdict
    import statistics

    by_type: Dict[str, List[Dict]] = defaultdict(list)
    for row in per_sample:
        qtype = row.get("question_type", "unknown")
        by_type[qtype].append(row)

    result = {}
    for qtype, rows in by_type.items():
        result[qtype] = {}
        for metric in metric_names:
            vals = [row[metric] for row in rows if metric in row and row[metric] is not None]
            if vals:
                result[qtype][metric] = round(statistics.mean(vals), 4)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def run(config: Dict = CONFIG) -> RAGASSEvalResult:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # 1. Load dataset
    samples = load_dataset(
        dataset_path=Path(config["dataset_path"]),
        filter_types=config.get("filter_question_types"),
    )
    if not samples:
        raise ValueError("Dataset rỗng hoặc filter quá chặt — không có sample nào để evaluate.")

    logger.info("\n📂 Loaded %d samples", len(samples))

    # 2. Init RAGAS LLM + Embeddings
    logger.info("Init Gemini LLM + Embeddings cho RAGAS...")
    ragas_llm, ragas_emb = _build_ragas_llm_and_emb(
        api_key=config["gemini_api_key"],
        model=config["gemini_model"],
    )

    # 3. Run RAGAS
    aggregate, per_sample = run_ragas_eval(
        samples=samples,
        metric_names=config["ragas_metrics"],
        ragas_llm=ragas_llm,
        ragas_emb=ragas_emb,
    )

    # 4. Per-type breakdown
    per_type = compute_per_type_metrics(per_sample, config["ragas_metrics"])

    # 5. Build result
    eval_result = RAGASSEvalResult(
        eval_mode=config["eval_mode"],
        total_samples=len(samples),
        metrics=aggregate,
        per_type_metrics=per_type,
        per_sample_scores=per_sample,
    )

    print(eval_result.summary())

    # 6. Save
    output_path = Path(config["output_dir"]) / config["output_file"]
    eval_result.save(output_path)

    return eval_result


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chạy RAGAS evaluation trên RAGASS dataset")
    parser.add_argument(
        "--dataset",
        default=None,
        help="Path tới .jsonl dataset (override CONFIG['dataset_path'])",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=None,
        choices=["single", "multi", "adversarial"],
        help="Chỉ evaluate các loại câu hỏi này",
    )
    args = parser.parse_args()

    cfg = dict(CONFIG)
    if args.dataset:
        cfg["dataset_path"] = Path(args.dataset)
    if args.types:
        cfg["filter_question_types"] = args.types

    run(cfg)
