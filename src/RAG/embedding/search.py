"""
Simple Search/Retrieval Script
Sử dụng để tìm kiếm trong vector store đã được tạo
"""

from embedding import create_pipeline


def search(query: str, top_k: int = 10, source_file: str = None):
    """
    Tìm kiếm trong vector store

    Args:
        query: Câu hỏi/query cần tìm
        top_k: Số lượng kết quả trả về
        source_file: Lọc theo file cụ thể (optional)

    Example:
        search("điều kiện tốt nghiệp", top_k=5)
        search("quy định học phí", source_file="QCDT_2025")
    """
    print("=" * 70)
    print(f"🔍 SEARCH: {query}")
    print("=" * 70)

    # Load vector store
    pipeline = create_pipeline()

    try:
        pipeline.load_vector_store()
    except FileNotFoundError:
        print("\n❌ Vector store not found!")
        print("   Please run: python run_embedding.py first")
        return []

    # Build filters
    filters = None
    if source_file:
        filters = {"source_file": source_file}
        print(f"📋 Filter: source_file = {source_file}")

    print(f"📊 Top K: {top_k}\n")

    # Search
    results = pipeline.search(query, top_k=top_k, filters=filters)

    if not results:
        print("❌ No results found")
        return []

    print(f"✅ Found {len(results)} results:\n")

    # Display results
    for i, result in enumerate(results, 1):
        print("=" * 70)
        print(f"Result #{i} - Score: {result.score:.4f}")
        print("=" * 70)

        # Metadata
        print(f"📄 Source: {result.metadata.get('source_file', 'N/A')}")
        print(f"🆔 Chunk ID: {result.chunk_id}")

        chapter = result.metadata.get("chapter_full")
        if chapter:
            print(f"📖 Chapter: {chapter}")

        article = result.metadata.get("article_full")
        if article:
            print(f"📋 Article: {article}")

        level = result.metadata.get("level")
        if level:
            print(f"🏷️  Level: {level}")

        # Content
        print(f"\n📝 Content:")
        print(f"{result.content}\n")

    return results


def interactive_search():
    """
    Chế độ tìm kiếm tương tác
    """
    print("\n" + "=" * 70)
    print("🔍 INTERACTIVE SEARCH MODE")
    print("=" * 70)
    print("Commands:")
    print("  - Type your question to search")
    print("  - Type 'exit' or 'quit' to stop")
    print("  - Type 'filter:SOURCE_NAME' to filter by source")
    print("=" * 70 + "\n")

    # Load vector store once
    pipeline = create_pipeline()
    try:
        pipeline.load_vector_store()
        stats = pipeline.vector_store.get_statistics()
        print(f"✅ Loaded vector store")
        print(f"   Total documents: {stats['total_documents']}")
        print(f"   Source files: {list(stats['source_files'].keys())}\n")
    except FileNotFoundError:
        print("❌ Vector store not found! Please run embedding first.")
        return

    current_filter = None

    while True:
        # Get input
        try:
            user_input = input("🔍 Query: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Bye!")
            break

        if not user_input:
            continue

        # Check commands
        if user_input.lower() in ["exit", "quit", "q"]:
            print("\n👋 Bye!")
            break

        if user_input.lower().startswith("filter:"):
            # Set filter
            filter_value = user_input.split(":", 1)[1].strip()
            if filter_value.lower() == "none":
                current_filter = None
                print(f"✅ Filter removed\n")
            else:
                current_filter = filter_value
                print(f"✅ Filter set to: {current_filter}\n")
            continue

        # Search
        filters = {"source_file": current_filter} if current_filter else None

        if filters:
            print(f"📋 Active filter: {current_filter}")

        results = pipeline.search(user_input, top_k=3, filters=filters)

        if not results:
            print("❌ No results found\n")
            continue

        # Display results
        print(f"\n{'='*70}")
        for i, result in enumerate(results, 1):
            print(
                f"\n[{i}] Score: {result.score:.4f} | Source: {result.metadata.get('source_file', 'N/A')}"
            )

            article = result.metadata.get("article_full", "")
            if article:
                print(f"    📋 {article}")

            print(f"    📝 {result.content[:200]}...")

        print(f"\n{'='*70}\n")


if __name__ == "__main__":
    """
    Usage:

    1. Simple search:
       python search.py
       (then edit the query below)

    2. Interactive mode:
       Uncomment interactive_search()
    """

    # ============================================
    # Option 1: Simple search
    # ============================================

    # Thay đổi query ở đây
    query = "một năm học bao gồm bao nhiêu kì"

    search(query, top_k=5)

    # Search với filter
    # search("quy định học phí", top_k=3, source_file="QCDT_2025")

    # ============================================
    # Option 2: Interactive mode (uncomment để dùng)
    # ============================================

    # interactive_search()
