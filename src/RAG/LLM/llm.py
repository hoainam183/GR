# llm.py - RAG System with Gemini LLM

import sys
from pathlib import Path
from typing import List, Dict
import json

from src.RAG.embedding.embedding import create_pipeline
from src.RAG.embedding.reranker import create_reranker
from src.RAG.embedding.hybrid_search import create_hybrid_searcher


class GeminiRAG:
    """
    RAG System với Gemini LLM
    """

    def __init__(
        self,
        api_key: str = None,
        model_name: str = None,
        pipeline=None,
        use_hybrid: bool = True,
        use_reranker: bool = True,
    ):
        """
        Initialize Gemini RAG

        Args:
            api_key: Gemini API key
            model_name: Model name (optional)
            pipeline: EmbeddingPipeline instance (optional)
            use_hybrid: Enable hybrid search (BM25 + Semantic) (default: True)
            use_reranker: Enable reranking with cross-encoder (default: True)
        """
        print("🔄 Initializing Gemini RAG System...")

        # Load pipeline (retriever)
        if pipeline is None:
            print("   Creating embedding pipeline...")

            # Change to embedding directory để load vector store
            import os

            current_dir = os.getcwd()
            embedding_dir = Path(__file__).parent.parent / "embedding"
            os.chdir(embedding_dir)

            try:
                self.pipeline = create_pipeline()
                self.pipeline.load_vector_store()
                print("   ✅ Vector store loaded")
            except FileNotFoundError:
                print("   ❌ Vector store not found! Run embedding first.")
                raise
            finally:
                # Restore original directory
                os.chdir(current_dir)
        else:
            self.pipeline = pipeline

        # Setup hybrid search
        self.use_hybrid = use_hybrid
        self.hybrid_searcher = None
        if use_hybrid:
            print("   Creating hybrid searcher...")
            self.hybrid_searcher = create_hybrid_searcher(
                semantic_weight=0.5, fusion_method="rrf"
            )
            print("   ✅ Hybrid search enabled")

        # Setup reranker
        self.use_reranker = use_reranker
        self.reranker = None
        if use_reranker:
            print("   Loading reranker model...")
            self.reranker = create_reranker(
                model_name="BAAI/bge-reranker-v2-m3",
                device="cpu",
                enable_deduplication=True,
                enable_reranking=True,
            )
            print("   ✅ Reranker loaded")

        # Setup LLM
        self.llm_provider = "gemini"

        print("   Setting up Gemini LLM...")
        self._setup_gemini(api_key, model_name)
        print("✅ Gemini RAG System ready!\n")

    def _setup_gemini(self, api_key: str, model_name: str = None):
        """Setup Google Gemini"""
        try:
            import google.generativeai as genai
        except ImportError:
            print("❌ Please install: pip install google-generativeai")
            raise

        genai.configure(api_key=api_key)

        self.model_name = model_name or "models/gemini-2.5-flash"
        self.llm_client = genai.GenerativeModel(self.model_name)

        print(f"   ✅ Gemini model: {self.model_name}")

    def answer(
        self,
        question: str,
        top_k: int = 5,
        filters: Dict = None,
        stream: bool = False,
        verbose: bool = True,
    ) -> Dict:
        """
        Trả lời câu hỏi với RAG
        """
        if verbose:
            print(f"❓ Question: {question}\n")

        # Step 1: Retrieve
        if verbose:
            print("📚 Retrieving relevant chunks...")

        # Retrieve more results if using hybrid or reranker
        initial_top_k = (
            top_k * 4 if (self.use_hybrid or self.use_reranker) else top_k
        )

        # Use pipeline to search
        results = self.pipeline.search(
            query=question,
            top_k=initial_top_k,
            filters=filters,
        )

        if verbose:
            print(f"   Retrieved {len(results)} initial chunks")

        # Step 1.5: Apply Hybrid Search (BM25 + Semantic)
        if self.use_hybrid and self.hybrid_searcher and results:
            if verbose:
                print("   Applying hybrid search (BM25 + Semantic)...")
            hybrid_top_k = top_k * 2 if self.use_reranker else top_k
            results = self.hybrid_searcher.hybrid_search(
                question, results, top_k=hybrid_top_k
            )
            if verbose:
                print(f"   → {len(results)} chunks after hybrid search")

        # Step 1.6: Apply Reranking (Cross-encoder + Deduplication)
        if self.use_reranker and self.reranker and results:
            if verbose:
                print("   Applying reranker (Cross-encoder + Deduplication)...")
            results = self.reranker.process(question, results, top_k=top_k)
            if verbose:
                print(f"   → {len(results)} chunks after reranking")

        if verbose:
            print(f"   ✅ Final: {len(results)} chunks\n")

        # Step 2: Build context
        context = self._build_context(results)

        # Step 3: Build prompt
        prompt = self._build_prompt(question, context)

        # Step 4: Get response
        if verbose:
            print("🤖 Generating answer...\n")

        answer = self._get_gemini_response(prompt, stream=stream)

        # Step 5: Format result
        result = {
            "question": question,
            "answer": answer,
            "sources": results,
            "context": context,
            "num_sources": len(results),
            "llm_provider": self.llm_provider,
            "model_name": self.model_name,
        }

        return result

    def _build_context(self, results: List) -> str:
        """Build context từ chunks"""
        context_parts = []

        for i, result in enumerate(results, 1):
            # result is SearchResult object
            part = f"[Nguồn {i}]\n"

            # Access metadata
            metadata = result.metadata

            # Add document info
            if metadata.get("source_file"):
                part += f"File: {metadata['source_file']}\n"

            if metadata.get("article_full"):
                part += f"Điều khoản: {metadata['article_full']}\n"
            elif metadata.get("article"):
                part += f"Điều: {metadata['article']}\n"

            if metadata.get("chapter_full"):
                part += f"Chương: {metadata['chapter_full']}\n"

            part += f"\nNội dung:\n{result.content}\n"

            context_parts.append(part)

        return "\n" + "=" * 70 + "\n\n".join(context_parts)

    def _build_prompt(self, question: str, context: str) -> str:
        """Build prompt"""
        prompt = f"""Bạn là trợ lý AI chuyên về Quy chế đào tạo của Đại học Bách khoa Hà Nội.

Nhiệm vụ: Trả lời câu hỏi của sinh viên/học viên dựa trên ngữ cảnh từ quy chế.

Ngữ cảnh từ Quy chế:
{context}

Câu hỏi: {question}

Hướng dẫn:
1. Trả lời CHÍNH XÁC dựa trên ngữ cảnh
2. Nếu không tìm thấy thông tin, nói "Không tìm thấy thông tin trong quy chế"
3. Giải thích rõ ràng, dễ hiểu
4. Liệt kê đầy đủ nếu có điều kiện/yêu cầu

Trả lời bằng tiếng Việt:"""

        return prompt

    def _get_gemini_response(self, prompt: str, stream: bool) -> str:
        """Gemini response"""

        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }

        if stream:
            response = self.llm_client.generate_content(
                prompt, generation_config=generation_config, stream=True
            )

            answer = ""
            for chunk in response:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    answer += chunk.text

            print("\n")
            return answer
        else:
            response = self.llm_client.generate_content(
                prompt, generation_config=generation_config
            )

            answer = response.text
            print(answer)
            print()
            return answer


# Test Functions


def test_gemini():
    """Test với Gemini"""
    print("=" * 70)
    print("🧪 TESTING GEMINI RAG SYSTEM")
    print("=" * 70)
    print()

    import os
    from dotenv import load_dotenv

    # Load API key from .env
    # Look for .env in project root (GR folder)
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("❌ GEMINI_API_KEY not found in .env")
        api_key = input("Enter Gemini API key: ")

    # Initialize RAG
    rag = GeminiRAG(api_key=api_key)

    # Test questions
    questions = [
        "khi nào thì sinh viên bị cảnh báo mức 2",
    ]

    # Ask first question with streaming
    question = questions[0]

    print(f"\n{'='*70}")
    print(f"❓ Question: {question}")
    print(f"{'='*70}\n")

    result = rag.answer(question, top_k=5, stream=True, verbose=True)

    print("\n" + "=" * 70)
    print("📊 RESULT SUMMARY")
    print("=" * 70)
    print(f"Provider: {result['llm_provider']}")
    print(f"Model: {result['model_name']}")
    print(f"Sources used: {result['num_sources']}")
    print("=" * 70)

    return rag


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    test_gemini()
