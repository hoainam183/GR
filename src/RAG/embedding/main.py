"""
Main script để chạy embedding pipeline
Usage:
    python main.py --mode single --file chunks.json --source QCDT_2025
    python main.py --mode batch --dir ../chunks_by_articles
    python main.py --mode search --query "điều kiện tốt nghiệp"
"""

import argparse
from pathlib import Path
from embedding import create_pipeline


def main():
    parser = argparse.ArgumentParser(description="RAG Embedding Pipeline")
    parser.add_argument(
        "--mode",
        choices=["single", "batch", "search"],
        required=True,
        help="Mode: single file, batch files, hoặc search",
    )
    parser.add_argument(
        "--file", type=str, help="Path to chunks.json file (for single mode)"
    )
    parser.add_argument(
        "--source", type=str, help="Source file name (for single mode)"
    )
    parser.add_argument(
        "--dir",
        type=str,
        help="Directory containing chunk files (for batch mode)",
    )
    parser.add_argument(
        "--query", type=str, help="Search query (for search mode)"
    )
    parser.add_argument(
        "--filter-source",
        type=str,
        help="Filter by source file (for search mode)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results (for search mode)",
    )

    args = parser.parse_args()

    pipeline = create_pipeline()

    if args.mode == "single":
        if not args.file or not args.source:
            print("❌ --file and --source are required for single mode")
            return

        print(f"\n{'='*60}")
        print(f"Processing single file: {args.file}")
        print(f"Source: {args.source}")
        print(f"{'='*60}\n")

        documents = pipeline.process_single_file(
            chunks_file=args.file, source_file=args.source, add_to_store=True
        )

        print(f"\n✅ Processed {len(documents)} chunks")
        pipeline.save_vector_store()

    elif args.mode == "batch":
        if not args.dir:
            print("❌ --dir is required for batch mode")
            return

        chunks_dir = Path(args.dir)
        if not chunks_dir.exists():
            print(f"❌ Directory not found: {chunks_dir}")
            return

        print(f"\n{'='*60}")
        print(f"Batch processing from: {chunks_dir}")
        print(f"{'='*60}\n")

        # Find all chunk files
        chunk_files = list(chunks_dir.glob("*_chunks.json"))
        if not chunk_files:
            chunk_files = list(chunks_dir.glob("chunks.json"))

        if not chunk_files:
            print(f"❌ No chunk files found in {chunks_dir}")
            return

        print(f"Found {len(chunk_files)} files:")
        for f in chunk_files:
            print(f"  - {f.name}")

        # Prepare for processing
        files_to_process = []
        for chunk_file in chunk_files:
            source_name = chunk_file.stem.replace("_chunks", "")
            files_to_process.append((str(chunk_file), source_name))

        # Process
        all_docs = pipeline.process_multiple_files(files_to_process)

        print(f"\n✅ Processed {len(all_docs)} source files")
        for source, docs in all_docs.items():
            print(f"   - {source}: {len(docs)} chunks")

        pipeline.save_vector_store()

    elif args.mode == "search":
        if not args.query:
            print("❌ --query is required for search mode")
            return

        print(f"\n{'='*60}")
        print(f"Loading vector store...")
        print(f"{'='*60}\n")

        try:
            pipeline.load_vector_store()
        except FileNotFoundError:
            print("❌ Vector store not found. Please run embedding first.")
            return

        # Build filters
        filters = {}
        if args.filter_source:
            filters["source_file"] = args.filter_source

        # Search
        print(f"🔍 Query: {args.query}")
        if filters:
            print(f"📋 Filters: {filters}")
        print(f"📊 Top K: {args.top_k}\n")

        results = pipeline.search(
            args.query, top_k=args.top_k, filters=filters or None
        )

        if not results:
            print("❌ No results found")
            return

        print(f"Found {len(results)} results:\n")
        for i, result in enumerate(results, 1):
            print(f"{'='*60}")
            print(f"Result {i} - Score: {result.score:.4f}")
            print(f"{'='*60}")
            print(f"Chunk ID: {result.chunk_id}")
            print(f"Source: {result.metadata.get('source_file', 'N/A')}")

            chapter = result.metadata.get("chapter_full", "")
            article = result.metadata.get("article_full", "")
            if chapter:
                print(f"Chapter: {chapter}")
            if article:
                print(f"Article: {article}")

            print(f"\nContent:")
            print(result.content)
            print()


if __name__ == "__main__":
    main()
