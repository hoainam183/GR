import asyncio
import sys
import io
import json
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from config.settings import Settings
from pipeline.rag_pipeline import RAGPipeline
from query.signals import analyze_query_signals

async def main():
    print("Initializing pipeline services...")
    settings = Settings()
    # Initialize pipeline just to load the services
    pipeline = RAGPipeline(settings=settings, mongo_logger=None, llm_cache=None)
    
    rs = pipeline.retrieval_service
    searcher = rs.searcher
    bge = rs.bge_embedder
    e5 = rs.e5_embedder

    try:
        with open("eval_dataset.json", "r", encoding="utf-8") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print("eval_dataset.json not found! Please run create_eval_dataset.py first.")
        return

    strategies = [
        {
            "name": "LINEAR_BASELINE (Pool 15)",
            "cfg": {
                "fusion_mode": "linear",
                "vector_pool_k": 15,
                "keyword_pool_k": 15,
            }
        },
        {
            "name": "LINEAR_BASELINE (Pool 30)",
            "cfg": {
                "fusion_mode": "linear",
                "vector_pool_k": 30,
                "keyword_pool_k": 30,
            }
        },
        {
            "name": "RRF_PROPOSED (Pool 15)",
            "cfg": {
                "fusion_mode": "rrf",
                "vector_pool_k": 15,
                "keyword_pool_k": 15,
            }
        },
        {
            "name": "RRF_PROPOSED (Pool 30)",
            "cfg": {
                "fusion_mode": "rrf",
                "vector_pool_k": 30,
                "keyword_pool_k": 30,
            }
        }
    ]

    results_stats = {s["name"]: {"top1": 0, "top3": 0, "mrr": 0.0} for s in strategies}

    for item in dataset:
        q = item["query"]
        target_id = item["target_id"]
        
        # embed queries manually for search
        bge_vec = bge.embed_query(q)
        e5_vec = e5.embed_query(q)
        
        for strat in strategies:
            cfg = strat['cfg']
            trace_out = {}
            
            results = searcher.search(
                query=q,
                bge_m3_query=bge_vec,
                e5_query=e5_vec,
                top_k=10,
                vector_top_k=cfg.get("vector_top_k", 20),
                keyword_top_k=cfg.get("keyword_top_k", 20),
                vector_pool_k=cfg.get("vector_pool_k", 15),
                keyword_pool_k=cfg.get("keyword_pool_k", 15),
                fusion_mode=cfg["fusion_mode"],
                trace_out=trace_out
            )
            
            # Find rank of target_id
            rank = -1
            for idx, r in enumerate(results):
                chunk_uuid = r["id"].split("/")[-1] if "/" in r["id"] else r["id"]
                if chunk_uuid == target_id:
                    rank = idx + 1
                    break
            
            strat_stats = results_stats[strat["name"]]
            if rank == 1:
                strat_stats["top1"] += 1
            if 1 <= rank <= 3:
                strat_stats["top3"] += 1
            if rank > 0:
                strat_stats["mrr"] += 1.0 / rank

    print("\n=======================================================")
    print("EVALUATION RESULTS")
    print("=======================================================")
    n = len(dataset)
    for s_name, stats in results_stats.items():
        print(f"\nStrategy: {s_name}")
        print(f"  Accuracy@1: {stats['top1']}/{n} ({stats['top1']/n*100:.2f}%)")
        print(f"  Accuracy@3: {stats['top3']}/{n} ({stats['top3']/n*100:.2f}%)")
        print(f"  MRR:        {stats['mrr']/n:.4f}")

if __name__ == "__main__":
    asyncio.run(main())
