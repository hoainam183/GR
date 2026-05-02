import sys
from pathlib import Path
import asyncio

# Add src/RAG_v2 to path
sys.path.insert(0, str(Path("/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2")))

from config.settings import Settings
from retrieval.service import RetrievalService
from query.reflection import _extract_entities

async def main():
    settings = Settings()
    retrieval_service = RetrievalService.from_settings(settings)
    searcher = retrieval_service.searcher
    bge = retrieval_service.bge_embedder
    e5 = retrieval_service.e5_embedder

    query = "tôi muốn tìm hiểu về"
    bge_vec = bge.embed_query(query)
    e5_vec = e5.embed_query(query)

    print("Searching...")
    results = searcher.search(
        query=query,
        bge_m3_query=bge_vec,
        e5_query=e5_vec,
        top_k=20,
        vector_top_k=20,
        keyword_top_k=20,
        vector_pool_k=15,
        keyword_pool_k=15,
        active_collections=["ctdt"],
        resolved_major="IT1",
    )
    print(f"Got {len(results)} results")
    if results:
        print("Top result score:", results[0].get("score"))
        print("Top result text:", results[0].get("text")[:100])

if __name__ == "__main__":
    asyncio.run(main())
