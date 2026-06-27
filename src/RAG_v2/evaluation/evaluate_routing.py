"""
Evaluate routing logic (reflection, tier decision, and collection selection)
without running full retrieval and generation.
"""

import csv
import json
import os
import re
from pathlib import Path

# Fix imports
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.evaluate import build_runtime
from unittest.mock import patch, MagicMock

class FakeRetrievalService:
    def __init__(self, *args, **kwargs):
        import torch
        from embedding.bge_m3 import BGEm3Embedder
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"Using device: {device} for BGE-M3 Embedder")
        self.bge_embedder = BGEm3Embedder("BAAI/bge-m3", device=device)
        self.e5_embedder = None
        self.reranker = None
        self.tavily_tool = None
        self.searcher = MagicMock()

def main():
    print("Building pipeline...")
    with patch("retrieval.service.RetrievalService.from_settings", side_effect=FakeRetrievalService):
        settings, pipeline, _, _ = build_runtime(disable_rerank=True)
    
    data_dir = PROJECT_ROOT / "evaluation" / "data"
    out_dir = PROJECT_ROOT / "evaluation" / "results_routing"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    datasets = sorted([p for p in data_dir.glob("*.json") if p.is_file()])
    
    tier_counts = {"chitchat": 0, "simple": 0, "complex": 0}
    collection_counts = {}
    total_queries = 0
    
    for dataset_path in datasets:
        dataset_name = dataset_path.stem
        out_csv = out_dir / f"{dataset_name}.csv"
        print(f"Processing {dataset_name}...")
        
        if dataset_name.startswith("_") or dataset_name.startswith("routing_cases") or dataset_name.startswith("ab_test"):
            continue
            
        with open(dataset_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
        elif isinstance(data, list):
            items = data
        else:
            continue
            
        with open(out_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "question", "reflection_query", "tier", "target_collections"])
            
            for item in items:
                q_id = item.get("id", "")
                question = item.get("question", "")
                
                # 1. Reflection
                reflected_question, _, _ = pipeline._run_reflection(
                    question, 
                    history=None, 
                    user_context=None, 
                    runtime=pipeline._llm_runtime_snapshot()
                )
                
                # 2. Tier routing
                route_tier, _ = pipeline._decide_complexity(reflected_question, history=None)
                
                # 3. Collection routing
                routing = pipeline._router.route(reflected_question)
                target_collections = routing.get("domains", [])
                if not target_collections and routing.get("domain"):
                    target_collections = [routing["domain"]]
                    
                target_collections_str = ",".join(target_collections)
                
                writer.writerow([q_id, question, reflected_question, route_tier, target_collections_str])
                
                # Update stats
                total_queries += 1
                tier_counts[route_tier] = tier_counts.get(route_tier, 0) + 1
                for coll in target_collections:
                    collection_counts[coll] = collection_counts.get(coll, 0) + 1
                    
    print("\n=== ROUTING EVALUATION SUMMARY ===")
    print(f"Total queries evaluated: {total_queries}")
    print("\n--- Tier Distribution ---")
    for tier, count in tier_counts.items():
        print(f"  - {tier}: {count} ({(count/total_queries)*100:.2f}%)")
        
    print("\n--- Collection Distribution ---")
    sorted_collections = sorted(collection_counts.items(), key=lambda x: x[1], reverse=True)
    for coll, count in sorted_collections:
        print(f"  - {coll}: {count} ({(count/total_queries)*100:.2f}%)")
        
    print(f"\nAll results saved to {out_dir}")

if __name__ == "__main__":
    main()
