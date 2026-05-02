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
    reranker = retrieval_service.reranker

    queries = [
        "Tôi muốn tìm hiểu về chương trình đào tạo ngành IT1",
        "Tôi muốn tìm hiểu về chương trình đào tạo ngành IT1 (Khoa học máy tính)"
    ]
    
    docs = [
        {
            "id": "1",
            "text": "## CỬ NHÂN KHOA HỌC MÁY TÍNH\n### Trường Đại học Bách Khoa Hà Nội – Viện Công nghệ Thông tin và Truyền thông\n\n---\n\n| Thông tin | Chi tiết |\n|---|---|\n| Tên chương trình | Khoa học máy tính |\n| Trình độ đào tạo | Cử nhân |\n| Ngành đào tạo | Khoa học máy tính |\n| Mã ngành | 7480101 |\n| Thời gian đào tạo | 4 năm |\n| Bằng tốt nghiệp | Cử nhân Khoa học máy tính |\n| Khối lượng kiến thức toàn khóa | 131 tín chỉ |\n\n---"
        }
    ]
    
    for q in queries:
        reranked = reranker.rerank(query=q, documents=docs, top_k=5, score_threshold=-10.0) # no threshold
        score = reranked[0]["rerank_score"] if reranked else "N/A"
        print(f"Query: '{q}'\nScore: {score}\n{'-'*40}")

if __name__ == "__main__":
    asyncio.run(main())
