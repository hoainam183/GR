import csv
import json
import logging
import sys
import time
from pathlib import Path

# Add PROJECT_ROOT to sys.path to resolve imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.evaluate import (
    load_dataset,
    build_runtime,
    evaluate_item,
    aggregate,
    save_outputs
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("retry_failed")


def is_failed(row: dict) -> bool:
    ans = str(row.get("generated_answer", ""))
    reason = str(row.get("self_eval_reason", ""))
    ref_reason = str(row.get("ref_match_reason", ""))
    mode = str(row.get("mode", ""))

    if "ERROR:" in ans: return True
    if mode == "error": return True
    if "Self-eval crashed" in reason: return True
    if "Judge call error" in ref_reason: return True
    if "Pipeline error" in ref_reason: return True
    if "429" in reason or "429" in ref_reason or "429" in ans: return True
    if "Resource has been exhausted" in reason or "Resource has been exhausted" in ref_reason or "Resource has been exhausted" in ans: return True

    return False


def coerce_record(row: dict) -> dict:
    new_row = dict(row)
    # Ints
    for k in ["num_sources", "hallucination_count"]:
        if k in new_row and new_row[k]:
            try:
                new_row[k] = int(new_row[k])
            except ValueError:
                new_row[k] = 0
                
    # Floats
    for k in [
        "latency_ms", "hit@3", "precision@3", "recall@3", "mrr@3", "ndcg@3",
        "hit@5", "precision@5", "recall@5", "mrr@5", "ndcg@5",
        "hit@7", "precision@7", "recall@7", "mrr@7", "ndcg@7"
    ]:
        if k in new_row and new_row[k]:
            try:
                new_row[k] = float(new_row[k])
            except ValueError:
                new_row[k] = 0.0
                
    # Bools
    if "self_eval_pass" in new_row:
        new_row["self_eval_pass"] = (str(new_row["self_eval_pass"]).lower() == "true")
        
    return new_row


def process_directory(base_dir: Path, fusion_mode: str, data_dir: Path):
    if not base_dir.exists():
        logger.warning(f"Directory {base_dir} does not exist.")
        return

    logger.info(f"=== Processing directory: {base_dir} with fusion_mode={fusion_mode} ===")
    
    # Build runtime once per fusion mode
    settings, pipeline, self_evaluator, judge_client = build_runtime(fusion_mode=fusion_mode, vector_model="dual")
    judge_model = settings.chat_model

    for sub_dir in sorted(base_dir.iterdir()):
        if not sub_dir.is_dir():
            continue
            
        csv_path = sub_dir / "query_results.csv"
        if not csv_path.exists():
            continue

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            records = [coerce_record(row) for row in reader]

        failed_indices = [i for i, r in enumerate(records) if is_failed(r)]
        if not failed_indices:
            logger.info(f"No failed queries in {sub_dir.name}")
            continue

        logger.info(f"Found {len(failed_indices)} failed queries in {sub_dir.name}")

        dataset_path = data_dir / f"{sub_dir.name}.json"
        if not dataset_path.exists():
            logger.error(f"Dataset not found for {sub_dir.name} at {dataset_path}")
            continue

        items = load_dataset(dataset_path)
        item_by_id = {str(item.get("id")): item for item in items}

        for idx in failed_indices:
            row = records[idx]
            q_id = str(row.get("id"))
            item = item_by_id.get(q_id)
            if not item:
                logger.error(f"Item ID {q_id} not found in dataset {dataset_path.name}")
                continue

            logger.info(f"Retrying query {q_id}...")
            new_record = evaluate_item(
                item=item,
                pipeline=pipeline,
                self_evaluator=self_evaluator,
                judge_client=judge_client,
                judge_model=judge_model
            )
            records[idx] = new_record
            time.sleep(16.0) # sleep to avoid rate limit

        logger.info(f"Re-aggregating and saving {sub_dir.name}")
        summary = aggregate(records)
        summary["dataset"] = f"{sub_dir.name}.json"
        save_outputs(records, summary, sub_dir)


if __name__ == "__main__":
    base = PROJECT_ROOT
    data_dir = base / "evaluation" / "data"

    # process_directory(base / "evaluation" / "result_RRF", "rrf", data_dir)
    # process_directory(base / "evaluation" / "results", "linear", data_dir)
    
    logger.info("Processing result_RRF...")
    process_directory(base / "evaluation" / "result_RRF", "rrf", data_dir)
    
    logger.info("Processing results...")
    process_directory(base / "evaluation" / "results", "linear", data_dir)
