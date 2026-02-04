"""
Run Embedding Pipeline - Python Script
Sử dụng trực tiếp trong Python, không cần bash
"""

from pathlib import Path
from embedding import create_pipeline


def process_single_file():
    """Xử lý 1 file chunks.json"""
    print("=" * 60)
    print("Processing single file...")
    print("=" * 60)

    # Tạo pipeline
    pipeline = create_pipeline()

    # Đường dẫn file chunks
    chunks_file = (
        "../chunks_by_articles/QD_ngoai_ngu_tu_K68_CQ_final_chunks.json"
    )

    # Tự động extract source_file từ tên file (loại bỏ _final_chunks hoặc _chunks)
    source_file = Path(chunks_file).stem
    if source_file.endswith("_final_chunks"):
        source_file = source_file.replace("_final_chunks", "")
    elif source_file.endswith("_chunks"):
        source_file = source_file.replace("_chunks", "")

    print(f"📄 File: {Path(chunks_file).name}")
    print(f"🏷️  Source: {source_file}")

    # Xử lý file
    documents = pipeline.process_single_file(
        chunks_file=chunks_file,
        source_file=source_file,
        add_to_store=True,
    )

    print(f"\n✅ Processed {len(documents)} chunks")

    # Save vector store
    pipeline.save_vector_store()
    print("\n✅ Vector store saved!")


def process_batch_files():
    """Xử lý tất cả files trong thư mục"""
    print("=" * 60)
    print("Batch processing files...")
    print("=" * 60)

    pipeline = create_pipeline()

    # Tìm tất cả files chunks
    # chunks_dir = Path("../chunks_by_articles")
    chunks_dir = Path("./olmocr_chunks")
    chunk_files = list(chunks_dir.glob("*_chunks.json"))

    if not chunk_files:
        chunk_files = list(chunks_dir.glob("chunks.json"))

    if not chunk_files:
        print(f"❌ No chunk files found in {chunks_dir}")
        return

    print(f"\nFound {len(chunk_files)} files:")
    for f in chunk_files:
        print(f"  - {f.name}")

    # Prepare for processing
    files_to_process = [
        (str(f), f.stem.replace("_chunks", "")) for f in chunk_files
    ]

    # Process all
    all_docs = pipeline.process_multiple_files(files_to_process)

    print(f"\n✅ Processed {len(all_docs)} source files:")
    for source, docs in all_docs.items():
        print(f"   - {source}: {len(docs)} chunks")

    # Save
    pipeline.save_vector_store()
    print("\n✅ Vector store saved!")


def search_basic():
    """Search cơ bản"""
    print("=" * 60)
    print("Basic Search")
    print("=" * 60)

    # Load vector store
    pipeline = create_pipeline()

    try:
        pipeline.load_vector_store()
    except FileNotFoundError:
        print(
            "❌ Vector store not found. Please run process_single_file() or process_batch_files() first!"
        )
        return

    # Search
    query = "điều kiện tốt nghiệp"
    print(f"\n🔍 Query: {query}")

    results = pipeline.search(query, top_k=5)

    print(f"\nTop {len(results)} results:")
    print("=" * 60)

    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result.score:.4f}")
        print(f"   Chunk ID: {result.chunk_id}")
        print(f"   Source: {result.metadata.get('source_file', 'N/A')}")

        chapter = result.metadata.get("chapter_full", "")
        if chapter:
            print(f"   Chapter: {chapter}")

        article = result.metadata.get("article_full", "")
        if article:
            print(f"   Article: {article}")

        print(f"\n   Content:")
        print(f"   {result.content[:300]}...")


def search_with_filter():
    """Search với metadata filter"""
    print("=" * 60)
    print("Search with Filter")
    print("=" * 60)

    pipeline = create_pipeline()

    try:
        pipeline.load_vector_store()
    except FileNotFoundError:
        print("❌ Vector store not found. Please run embedding first!")
        return

    query = "quy định về học phí"
    filter_source = "QCDT_2025"  # Chỉ tìm trong file này

    print(f"\n🔍 Query: {query}")
    print(f"📋 Filter: source_file = {filter_source}")

    results = pipeline.search(
        query, top_k=5, filters={"source_file": filter_source}
    )

    print(f"\nTop {len(results)} results:")
    print("=" * 60)

    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result.score:.4f}")
        print(f"   Source: {result.metadata['source_file']}")
        print(f"   Content: {result.content[:250]}...")


def add_new_file():
    """Thêm file mới vào vector store đã có"""
    print("=" * 60)
    print("Adding new file to existing vector store")
    print("=" * 60)

    pipeline = create_pipeline()

    # Load vector store đã có
    try:
        pipeline.load_vector_store()
        print("✅ Loaded existing vector store")
    except FileNotFoundError:
        print("⚠️  No existing vector store found. Creating new one...")

    # Show statistics before
    try:
        stats = pipeline.vector_store.get_statistics()
        print(f"\n📊 Before adding:")
        print(f"   Total documents: {stats['total_documents']}")
        print(f"   Source files: {list(stats['source_files'].keys())}")
    except:
        pass

    # Thêm file mới
    print("\n➕ Adding new file...")
    documents = pipeline.process_single_file(
        chunks_file="../chunks_by_articles/QuyDinh_NN_chunks.json",
        source_file="QuyDinh_NgoaiNgu",
        add_to_store=True,
    )

    print(f"   Added {len(documents)} chunks")

    # Save
    pipeline.save_vector_store()

    # Show statistics after
    stats = pipeline.vector_store.get_statistics()
    print(f"\n📊 After adding:")
    print(f"   Total documents: {stats['total_documents']}")
    print(f"   Source files: {list(stats['source_files'].keys())}")
    print("\n✅ Done!")


def update_existing_file():
    """Update (xóa và thêm lại) một file trong vector store"""
    print("=" * 60)
    print("Updating existing file")
    print("=" * 60)

    pipeline = create_pipeline()
    pipeline.load_vector_store()

    source_to_update = "QCDT_2025"

    print(f"\n🗑️  Deleting old documents from {source_to_update}...")
    deleted = pipeline.vector_store.delete_by_metadata(
        {"source_file": source_to_update}
    )
    print(f"   Deleted {deleted} documents")

    print(f"\n➕ Adding updated documents...")
    documents = pipeline.process_single_file(
        chunks_file="../chunks_by_articles/chunks.json",  # File updated
        source_file=source_to_update,
        add_to_store=True,
    )
    print(f"   Added {len(documents)} documents")

    # Save
    pipeline.save_vector_store()
    print("\n✅ Update completed!")


def view_statistics():
    """Xem thống kê vector store"""
    print("=" * 60)
    print("Vector Store Statistics")
    print("=" * 60)

    pipeline = create_pipeline()

    try:
        pipeline.load_vector_store()
    except FileNotFoundError:
        print("❌ Vector store not found!")
        return

    stats = pipeline.vector_store.get_statistics()

    print(f"\n📊 Statistics:")
    print(f"   Total documents: {stats['total_documents']}")
    print(f"   Embedding dimension: {stats['dimension']}")
    print(f"   Index type: {stats['index_type']}")

    print(f"\n📁 Source Files:")
    for source, count in stats["source_files"].items():
        print(f"   - {source}: {count} chunks")

    print(f"\n📑 Levels:")
    for level, count in stats["levels"].items():
        print(f"   - {level}: {count} chunks")

    if stats.get("chapters"):
        print(f"\n📖 Chapters:")
        for chapter, count in stats["chapters"].items():
            print(f"   - Chapter {chapter}: {count} chunks")


if __name__ == "__main__":
    """
    Chạy các functions bằng cách uncomment dòng muốn thực thi
    """

    print("\n" + "=" * 60)
    print("RAG EMBEDDING PIPELINE - PYTHON API")
    print("=" * 60 + "\n")

    # ==========================================
    # BƯỚC 1: XỬ LÝ CHUNKS (chọn 1 trong 2)
    # ==========================================

    # Option 1: Xử lý 1 file
    # process_single_file()

    # Option 2: Xử lý tất cả files trong thư mục
    process_batch_files()

    # ==========================================
    # BƯỚC 2: SEARCH
    # ==========================================

    # Search cơ bản
    # search_basic()

    # Search với filter
    # search_with_filter()

    # ==========================================
    # THÊM/UPDATE FILES
    # ==========================================

    # Thêm file mới
    # add_new_file()

    # Update file đã có
    # update_existing_file()

    # ==========================================
    # XEM THỐNG KÊ
    # ==========================================

    # view_statistics()

    print("\n" + "=" * 60)
    print("✅ Done!")
    print("=" * 60)
