Files chính (Core):
config.py - Quản lý cấu hình:

EmbeddingModelConfig: config model embedding (multilingual-e5-large, batch size, device)
ChunkProcessingConfig: config xử lý chunks (input/output paths, context strategy)
VectorStoreConfig: config vector database (FAISS, dimension, search settings)
PipelineConfig: tổng hợp tất cả configs
vector_store.py - Abstract interface:

Định nghĩa interface chuẩn cho vector database
Classes: Document, SearchResult, VectorStore (abstract)
Cho phép dễ dàng chuyển đổi giữa FAISS, PostgreSQL, ChromaDB
faiss_store.py - Triển khai FAISS:

Implement VectorStore với FAISS (Facebook AI Similarity Search)
Quản lý FAISS index + metadata storage
Hỗ trợ: add documents, search, delete by metadata, save/load
embedding.py - Pipeline chính:

Class EmbeddingPipeline: xử lý toàn bộ workflow
Load chunks → Build context → Embed → Save to vector store
Hỗ trợ single file và batch processing
Track source file trong metadata
Files thực thi (Execution):
main.py - CLI script:

Command-line interface với argparse
3 modes: single (1 file), batch (nhiều files), search
Usage: python [main.py](http://_vscodecontentref_/16) --mode batch --dir ../chunks_by_articles
run_embedding.py ⭐ - Python script đơn giản:

Functions: process_single_file(), process_batch_files(), search_basic()
Dễ sử dụng hơn main.py (không cần args)
Hiện đang mở trong editor của bạn
search.py - Tìm kiếm:

Function search(): tìm kiếm trong vector store
interactive_search(): chế độ tìm kiếm tương tác
Hỗ trợ filter theo source file