"""
Simple Search/Retrieval Script
Sử dụng để tìm kiếm trong vector store đã được tạo

Features:
- Post-retrieval deduplication (remove parent-child duplicates)
- Cross-encoder reranking using BGE-reranker-v2-m3
"""

from typing import Optional
from .embedding import create_pipeline
from .reranker import RerankerPipeline, RerankerConfig, create_reranker


def search(
    query: str,
    top_k: int = 5,
    source_file: str = None,
    use_reranker: bool = True,
    initial_top_k: int = 20,
):
    """
    Tìm kiếm trong vector store với deduplication và reranking

    Args:
        query: Câu hỏi/query cần tìm
        top_k: Số lượng kết quả trả về cuối cùng
        source_file: Lọc theo file cụ thể (optional)
        use_reranker: Sử dụng cross-encoder reranking (default: True)
        initial_top_k: Số lượng kết quả lấy ban đầu để rerank (default: 20)

    Example:
        search("điều kiện tốt nghiệp", top_k=5)
        search("quy định học phí", source_file="QCDT_2025")
        search("học bổng KKHT", use_reranker=False)  # Disable reranking
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

    # Determine how many results to retrieve initially
    retrieve_k = initial_top_k if use_reranker else top_k
    print(f"📊 Initial retrieval: {retrieve_k}, Final top_k: {top_k}")
    print(f"🔄 Reranker: {'enabled' if use_reranker else 'disabled'}\n")

    # Search (retrieve more if using reranker)
    results = pipeline.search(query, top_k=retrieve_k, filters=filters)

    if not results:
        print("❌ No results found")
        return []

    print(f"✅ Initial retrieval: {len(results)} results")

    # Apply reranker (deduplication + cross-encoder)
    if use_reranker:
        reranker = create_reranker(
            model_name="BAAI/bge-reranker-v2-m3",
            device="cpu",  # Change to "cuda" if you have GPU
            enable_deduplication=True,
            enable_reranking=True,
        )
        results = reranker.process(query, results, top_k=top_k)
        print(f"✅ After reranking: {len(results)} results\n")
    else:
        results = results[:top_k]
        print(f"✅ Final: {len(results)} results\n")

    # Display results
    print(f"{'='*70}")
    print(f"📊 FINAL RESULTS ({len(results)} items)")
    print(f"{'='*70}\n")

    for i, result in enumerate(results, 1):
        print("=" * 70)
        print(f"Result #{i} - Score: {result.score:.4f}")

        # Show original score if reranked
        original_score = result.metadata.get("original_score")
        if original_score is not None:
            print(
                f"         (Original: {original_score:.4f}, CE: {result.metadata.get('ce_score', 'N/A'):.4f})"
            )

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


def interactive_search(use_reranker: bool = True):
    """
    Chế độ tìm kiếm tương tác với deduplication và reranking

    Args:
        use_reranker: Sử dụng cross-encoder reranking (default: True)
    """
    print("\n" + "=" * 70)
    print("🔍 INTERACTIVE SEARCH MODE")
    print("=" * 70)
    print("Commands:")
    print("  - Type your question to search")
    print("  - Type 'exit' or 'quit' to stop")
    print("  - Type 'filter:SOURCE_NAME' to filter by source")
    print("  - Type 'rerank:on' or 'rerank:off' to toggle reranking")
    print("=" * 70 + "\n")

    # Load vector store once
    pipeline = create_pipeline()
    try:
        pipeline.load_vector_store()
        stats = pipeline.vector_store.get_statistics()
        print(f"✅ Loaded vector store")
        print(f"   Total documents: {stats['total_documents']}")
        print(f"   Source files: {list(stats['source_files'].keys())}")
    except FileNotFoundError:
        print("❌ Vector store not found! Please run embedding first.")
        return

    # Initialize reranker if enabled
    reranker = None
    if use_reranker:
        print(f"\n🔄 Loading reranker...")
        reranker = create_reranker(
            model_name="BAAI/bge-reranker-v2-m3",
            device="cpu",
            enable_deduplication=True,
            enable_reranking=True,
        )

    print(f"\n✅ Ready! Reranker: {'enabled' if reranker else 'disabled'}\n")

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

        if user_input.lower().startswith("rerank:"):
            # Toggle reranker
            value = user_input.split(":", 1)[1].strip().lower()
            if value in ["on", "true", "1", "yes"]:
                if reranker is None:
                    print(f"🔄 Loading reranker...")
                    reranker = create_reranker()
                print(f"✅ Reranker enabled\n")
            else:
                reranker = None
                print(f"✅ Reranker disabled\n")
            continue

        # Search
        filters = {"source_file": current_filter} if current_filter else None

        if filters:
            print(f"📋 Active filter: {current_filter}")

        # Retrieve more if using reranker
        retrieve_k = 15 if reranker else 5
        results = pipeline.search(user_input, top_k=retrieve_k, filters=filters)

        if not results:
            print("❌ No results found\n")
            continue

        # Apply reranker if enabled
        if reranker:
            results = reranker.process(user_input, results, top_k=5)

        # Display results
        print(f"\n{'='*70}")
        for i, result in enumerate(results, 1):
            score_str = f"Score: {result.score:.4f}"
            original = result.metadata.get("original_score")
            if original is not None:
                score_str = f"CE: {result.score:.4f} (orig: {original:.4f})"

            print(
                f"\n[{i}] {score_str} | Source: {result.metadata.get('source_file', 'N/A')}"
            )

            level = result.metadata.get("level", "")
            if level:
                print(f"    🏷️ Level: {level}")

            article = result.metadata.get("article_full", "")
            if article:
                print(f"    📋 {article}")

            print(f"    📝 {result.content[:300]}...")

        print(f"\n{'='*70}\n")


if __name__ == "__main__":
    """
    Usage:

    1. Simple search with reranking:
       python -m embedding.search

    2. Search without reranking:
       Modify use_reranker=False below

    3. Interactive mode:
       Uncomment interactive_search()
    """

    # ============================================
    # Option 1: Simple search with reranking
    # ============================================

    # Thay đổi query ở đây
    query = "Sinh viên nào không được xét cấp học bổng KKHT?"

    # With reranking (default) - slower but more accurate
    search(query, top_k=5, use_reranker=True, initial_top_k=20)

    # Without reranking - faster
    # search(query, top_k=5, use_reranker=False)

    # Search với filter
    # search("quy định học phí", top_k=3, source_file="QCDT_2025")

    # ============================================
    # Option 2: Interactive mode (uncomment để dùng)
    # ============================================

    # interactive_search(use_reranker=True)
