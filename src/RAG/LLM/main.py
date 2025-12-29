"""
Main script để chạy RAG với Gemini
"""

import sys
from pathlib import Path

# Add paths
current_dir = Path(__file__).parent
embedding_path = current_dir.parent / "embedding"
sys.path.insert(0, str(embedding_path))

from llm import GeminiRAG
import os
from dotenv import load_dotenv


def main():
    """Main function"""
    print("=" * 70)
    print("🤖 GEMINI RAG SYSTEM")
    print("=" * 70)
    print()

    # Load API key
    env_path = current_dir.parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("❌ GEMINI_API_KEY not found in .env")
        api_key = input("Enter Gemini API key: ")

    # Initialize RAG
    try:
        rag = GeminiRAG(api_key=api_key)
    except FileNotFoundError:
        print("\n❌ Vector store not found!")
        print(
            "   Please run embedding first: cd ../embedding && python run_embedding.py"
        )
        return

    # Interactive mode
    print("\n" + "=" * 70)
    print("💬 INTERACTIVE MODE")
    print("=" * 70)
    print("\nCommands:")
    print("  - Type your question to get answer")
    print("  - 'quit' or 'exit' to exit")
    print("  - 'source:filename' to filter by source file")
    print("=" * 70)
    print()

    source_filter = None

    while True:
        try:
            # Get user input
            user_input = input("\n❓ Your question: ").strip()

            if not user_input:
                continue

            # Check for commands
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            # Check for source filter
            if user_input.lower().startswith("source:"):
                source_filter = user_input.split(":", 1)[1].strip()
                print(f"✅ Filter set: source_file = {source_filter}")
                continue

            if user_input.lower() == "clear filter":
                source_filter = None
                print("✅ Filter cleared")
                continue

            # Build filters
            filters = None
            if source_filter:
                filters = {"source_file": source_filter}

            # Get answer
            print()
            result = rag.answer(
                question=user_input,
                top_k=5,
                filters=filters,
                stream=True,
                verbose=True,
            )

            # Show sources
            print("\n" + "-" * 70)
            print(f"📚 {result['num_sources']} sources used:")
            for i, source in enumerate(result["sources"], 1):
                meta = source.metadata
                print(
                    f"  [{i}] {meta.get('source_file', 'Unknown')} - Score: {source.score:.3f}"
                )
                if meta.get("article_full"):
                    print(f"      {meta['article_full']}")
            print("-" * 70)

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
