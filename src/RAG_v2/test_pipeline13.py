import sys
from pathlib import Path
import asyncio

# Add src/RAG_v2 to path
sys.path.insert(0, str(Path("/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2")))

from config.settings import Settings
from pipeline.rag_pipeline import RAGPipeline
from query.reflection import QueryReflector

async def main():
    settings = Settings()
    pipeline = RAGPipeline.from_settings(settings)
    
    question = "Tôi muốn tìm hiểu về chương trình đào tạo ngành IT1"
    
    print(f"Testing RAG pipeline with question: {question}")
    
    generator, sources, metadata = pipeline.query_stream(
        question=question,
        history=[],
    )
    
    # We only care about sources right now
    found = False
    print(f"Got {len(sources)} sources")
    for i, s in enumerate(sources):
        if "Mã ngành | 7480101" in s.get("text", "") or "CỬ NHÂN KHOA HỌC MÁY TÍNH" in s.get("text", ""):
            print(f"Found target chunk at rank {i}, score {s.get('rerank_score', 'N/A')}")
            found = True
            break
            
    if not found:
        print("Target chunk NOT FOUND in sources")
        for i, s in enumerate(sources[:3]):
            print(f"Top {i}: {s.get('rerank_score')} - {s.get('text')[:100]}")

if __name__ == "__main__":
    asyncio.run(main())
