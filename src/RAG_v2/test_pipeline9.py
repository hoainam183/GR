import sys
from pathlib import Path
import asyncio

# Add src/RAG_v2 to path
sys.path.insert(0, str(Path("/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2")))

from config.settings import Settings
from retrieval.service import RetrievalService

async def main():
    settings = Settings()
    retrieval_service = RetrievalService.from_settings(settings)
    searcher = retrieval_service.searcher
    bge = retrieval_service.bge_embedder
    e5 = retrieval_service.e5_embedder
    reranker = retrieval_service.reranker

    query = "Tôi muốn tìm hiểu về chương trình đào tạo ngành IT1"
    bge_vec = bge.embed_query(query)
    e5_vec = e5.embed_query(query)

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
    
    reranked = reranker.rerank(query=query, documents=results, top_k=5)
    print("TOP 5 AFTER RERANKING:")
    for i, r in enumerate(reranked):
        print(f"Rank {i} | Score: {r.get('score')}")
        print(f"Text: {r.get('text')[:200]}...")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
