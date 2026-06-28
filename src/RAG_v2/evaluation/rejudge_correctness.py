"""Script to re-judge the correctness of generated answers against gold answers using a different LLM.
Only re-evaluates `ref_match` and `ref_match_reason` in existing CSV files without needing the original context.
"""
import argparse
import csv
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from config.settings import Settings
from evaluation.evaluate import _build_judge_client, _compare_with_reference, aggregate, save_outputs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluation.rejudge")

def run_rejudge(
    input_dir: Path,
    output_dir: Path,
    judge_provider: str,
    judge_model: str,
    inter_question_sleep_s: float = 0.0,
):
    settings = Settings()
    settings.llm_provider = judge_provider
    if judge_model:
        settings.chat_model = judge_model
    else:
        if judge_provider == "deepseek":
            settings.chat_model = "deepseek-v4-flash"
        elif judge_provider == "gemini":
            settings.chat_model = "gemini-3.1-flash-lite"
        elif judge_provider == "openai":
            settings.chat_model = "gpt-4o-mini"
        elif judge_provider == "lm_studio":
            settings.chat_model = "local-model"

    judge_client = _build_judge_client(settings)
    model_name = settings.chat_model

    # Process all query_results.csv in input_dir
    csv_files = list(input_dir.glob("*/query_results.csv"))
    if not csv_files:
        logger.error(f"No query_results.csv found in {input_dir} subdirectories.")
        return

    logger.info(f"Found {len(csv_files)} datasets to re-judge.")
    
    for csv_file in csv_files:
        dataset_name = csv_file.parent.name
        logger.info(f"=== Re-judging {dataset_name} ===")
        
        # Read records
        records: List[Dict[str, Any]] = []
        with csv_file.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
        
        # Re-judge
        for idx, record in enumerate(records, start=1):
            question = record.get("question", "")
            gold_answer = record.get("gold_answer", "")
            generated_answer = record.get("generated_answer", "")
            
            logger.info(f"[{idx}/{len(records)}] {question[:60]}")
            
            if gold_answer:
                ref = _compare_with_reference(
                    judge_client, model_name, question, gold_answer, generated_answer
                )
                record["ref_match"] = ref.get("match", "incorrect")
                record["ref_match_reason"] = ref.get("reason", "")
            else:
                record["ref_match"] = "n/a"
                record["ref_match_reason"] = "No gold_answer provided."
                
            # Sleep if configured
            if inter_question_sleep_s > 0 and idx < len(records):
                time.sleep(inter_question_sleep_s)
        
        # Fix types for metrics so aggregate() doesn't fail
        # The CSV reader reads everything as strings. aggregate() expects latency_ms as float, hit@k as float etc.
        for record in records:
            try:
                record["latency_ms"] = float(record.get("latency_ms", 0.0))
            except ValueError:
                record["latency_ms"] = 0.0
                
            for k in record:
                if "@" in k:
                    try:
                        record[k] = float(record[k])
                    except ValueError:
                        pass
        
        # Aggregate
        summary = aggregate(records)
        summary["dataset"] = dataset_name
        
        # Save
        out_sub_dir = output_dir / dataset_name
        save_outputs(records, summary, out_sub_dir)

def main():
    parser = argparse.ArgumentParser(description="Re-judge correctness of CSV evaluation results.")
    parser.add_argument("--input-dir", type=Path, required=True, help="Input directory containing subdirectories with query_results.csv (e.g. evaluation/result_dual_RRF).")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory to save re-judged results.")
    parser.add_argument("--judge-provider", type=str, default="gemini", help="LLM provider for the judge (e.g., gemini).")
    parser.add_argument("--judge-model", type=str, default=None, help="Chat model for the judge.")
    parser.add_argument("--inter-question-sleep-s", type=float, default=0.0, help="Seconds to sleep between questions.")
    
    args = parser.parse_args()
    
    run_rejudge(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        inter_question_sleep_s=args.inter_question_sleep_s,
    )

if __name__ == "__main__":
    main()
