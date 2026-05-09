"""
run_ragass.py — Entry point chạy toàn bộ RAGASS pipeline.

Pipeline:
  Step 1: Generate dataset  (ragass_generator.py)
    - Load chunks từ stsv + quydinh
    - Embed + cluster
    - LLM (Gemini) sinh 3 loại câu hỏi: single / multi / adversarial
    - Output: outputs/ragass_dataset.jsonl

  Step 2: Evaluate dataset  (ragass_evaluator.py)
    - Load dataset
    - RAGAS evaluate: context_recall + context_precision
    - Output: outputs/ragass_eval_result.json

CONFIG nằm trong từng module (ragass_generator.CONFIG, ragass_evaluator.CONFIG).
Sửa trực tiếp trong file đó, không dùng CLI args.

Chạy:
    # Full pipeline (generate + evaluate)
    python eval/RAG/run_ragass.py

    # Chỉ generate dataset
    python eval/RAG/run_ragass.py --step generate

    # Chỉ evaluate (dùng dataset đã có)
    python eval/RAG/run_ragass.py --step eval

    # Evaluate một file dataset cụ thể
    python eval/RAG/run_ragass.py --step eval --dataset outputs/ragass_dataset.jsonl
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Đảm bảo import được các module trong cùng thư mục
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def step_generate() -> Path:
    """Chạy generation pipeline."""
    logger.info("=" * 60)
    logger.info("  STEP 1: Generate RAGASS Dataset")
    logger.info("=" * 60)

    from .ragass_generator import run as gen_run, CONFIG as GEN_CONFIG
    output_path = gen_run(GEN_CONFIG)
    logger.info("✅ Dataset saved: %s", output_path)
    return output_path


def step_evaluate(dataset_path: Path | None = None) -> None:
    """Chạy RAGAS evaluation."""
    logger.info("=" * 60)
    logger.info("  STEP 2: RAGAS Evaluate")
    logger.info("=" * 60)

    from .ragass_evaluator import run as eval_run, CONFIG as EVAL_CONFIG

    cfg = dict(EVAL_CONFIG)
    if dataset_path is not None:
        cfg["dataset_path"] = dataset_path

    result = eval_run(cfg)
    logger.info("✅ Eval complete. Metrics: %s", result.metrics)


def main():
    parser = argparse.ArgumentParser(
        description="RAGASS Pipeline — Generate + Evaluate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python run_ragass.py                  # Chạy cả hai bước
  python run_ragass.py --step generate  # Chỉ tạo dataset
  python run_ragass.py --step eval      # Chỉ evaluate (dùng dataset mặc định)
  python run_ragass.py --step eval --dataset outputs/ragass_dataset.jsonl
        """,
    )
    parser.add_argument(
        "--step",
        choices=["generate", "eval", "all"],
        default="all",
        help="Bước muốn chạy: 'generate', 'eval', hoặc 'all' (default: all)",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Override dataset path cho bước eval (default: lấy từ EVAL_CONFIG)",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset) if args.dataset else None

    start = time.time()

    try:
        if args.step in ("generate", "all"):
            generated_path = step_generate()
            # Nếu chạy all, dùng path vừa generate cho eval
            if args.step == "all" and dataset_path is None:
                dataset_path = generated_path

        if args.step in ("eval", "all"):
            step_evaluate(dataset_path=dataset_path)

    except KeyboardInterrupt:
        logger.info("\n⚠️  Bị ngắt bởi người dùng.")
        sys.exit(1)
    except Exception as e:
        logger.error("❌ Pipeline thất bại: %s", e, exc_info=True)
        sys.exit(1)

    elapsed = time.time() - start
    logger.info("\n🎉 Pipeline hoàn thành trong %.1f giây (%.1f phút)", elapsed, elapsed / 60)


if __name__ == "__main__":
    main()
