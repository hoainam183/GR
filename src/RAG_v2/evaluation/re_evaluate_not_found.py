"""Script to re-evaluate "not found" queries from a CSV and update their respective dataset results."""
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

from evaluation.evaluate import build_runtime, evaluate_item, aggregate, save_outputs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluation.re_evaluate")


def run(not_found_csv: Path, base_result_dir: Path, provider: str, judge_provider: str):
    if not not_found_csv.exists():
        logger.error(f"File not found: {not_found_csv}")
        return

    # Read the not_found queries
    not_found_queries = []
    with not_found_csv.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            not_found_queries.append(row)

    # Group by dataset
    queries_by_dataset = {}
    for q in not_found_queries:
        dataset = q.get("dataset")
        if not dataset:
            continue
        queries_by_dataset.setdefault(dataset, []).append(q)

    if not queries_by_dataset:
        logger.info("No queries found or missing 'dataset' column.")
        return

    # Build pipeline once
    logger.info("Building RAG pipeline...")
    settings, pipeline, self_evaluator, judge_client, judge_model = build_runtime(
        fusion_mode="rrf",
        vector_model="dual",
        provider=provider,
        judge_provider=judge_provider,
    )

    for dataset, queries in queries_by_dataset.items():
        dataset_dir = base_result_dir / dataset
        query_csv = dataset_dir / "query_results.csv"
        
        if not query_csv.exists():
            logger.warning(f"Could not find query_results.csv for {dataset} at {query_csv}. Skipping.")
            continue

        logger.info(f"=== Re-evaluating {len(queries)} queries for dataset {dataset} ===")

        # Load existing records
        records = []
        with query_csv.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)

        # Map id to index for fast replacement
        id_to_idx = {r["id"]: idx for idx, r in enumerate(records)}

        for q in queries:
            qid = q["id"]
            if qid not in id_to_idx:
                logger.warning(f"Query {qid} not found in {query_csv}. Skipping.")
                continue

            # Build item compatible with evaluate_item
            item = {
                "id": qid,
                "question": q["question"],
                "question_type": q.get("question_type", "simple"),
                "difficulty": q.get("difficulty", "medium"),
                "gold_answer": q.get("gold_answer", ""),
                "evidence_chunk_ids": [x.strip() for x in q.get("relevant_chunk_ids", "").split(",") if x.strip()],
            }

            logger.info(f"Re-evaluating {qid}: {item['question'][:60]}")
            new_record = evaluate_item(
                item=item,
                pipeline=pipeline,
                self_evaluator=self_evaluator,
                judge_client=judge_client,
                judge_model=judge_model,
                top_k=7,
            )
            
            # Replace in records
            idx = id_to_idx[qid]
            records[idx] = new_record
            
            # Sleep to respect rate limits if using free tier LLM API
            time.sleep(2)

        # Fix types for older records so aggregate() works correctly
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
            
            for k in ["self_eval_faithfulness", "self_eval_relevance", "self_eval_completeness", "ref_match"]:
                if k not in record or not isinstance(record[k], str):
                    record[k] = str(record.get(k, ""))

        # Aggregate metrics and save new report + csv
        summary = aggregate(records)
        summary["dataset"] = dataset
        save_outputs(records, summary, dataset_dir)
        logger.info(f"Updated {dataset_dir}")


def main():
    parser = argparse.ArgumentParser(description="Re-evaluate not found queries and update datasets")
    parser.add_argument(
        "--not-found-csv", 
        type=Path, 
        default=PROJECT_ROOT / "evaluation" / "results" / "not_found_queries.csv",
        help="Path to the CSV file containing 'not found' queries."
    )
    parser.add_argument(
        "--base-result-dir", 
        type=Path, 
        default=PROJECT_ROOT / "evaluation" / "results",
        help="Base directory where the dataset results (query_results.csv, report.md) are stored."
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="deepseek",
        help="LLM provider to generate the answers (e.g. deepseek, gemini)"
    )
    parser.add_argument(
        "--judge-provider",
        type=str,
        default="gemini",
        help="LLM provider for the judge (e.g. gemini, openai)"
    )
    args = parser.parse_args()
    
    run(args.not_found_csv, args.base_result_dir, args.provider, args.judge_provider)


if __name__ == "__main__":
    main()
