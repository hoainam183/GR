# llm_megallm.py - RAG System with MegaLLM

import sys
from pathlib import Path

# Add RAG/embedding to path
embedding_path = Path(__file__).parent.parent / "embedding"
sys.path.insert(0, str(embedding_path))

from embedding import create_pipeline
from typing import List, Dict
import json
from openai import OpenAI


class MegaLLMRAG:
    """
    RAG System với MegaLLM API
    """

    def __init__(
        self,
        api_key: str = None,
        model_name: str = None,
        api_url: str = None,
        pipeline=None,
    ):
        """
        Initialize MegaLLM RAG

        Args:
            api_key: MegaLLM API key
            model_name: Model name (optional)
            api_url: API endpoint URL (optional)
            pipeline: EmbeddingPipeline instance (optional)
        """
        print("🔄 Initializing MegaLLM RAG System...")

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

        # Setup LLM
        self.llm_provider = "megallm"
        self.api_key = api_key

        # MegaLLM API configuration (theo docs)
        self.base_url = api_url or "https://ai.megallm.io/v1"
        self.model_name = model_name or "gpt-3.5-turbo"
        
        # Initialize OpenAI client với base_url custom
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )
        
        print(f"   ✅ MegaLLM configured")
        print(f"   Model: {self.model_name}")
        print(f"   Base URL: {self.base_url}")
        question: str,
        top_k: int = 3,
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

        results = self.pipeline.search(
            query=question,
            top_k=top_k,
            filters=filters,
        )

        if verbose:
            print(f"   Retrieved {len(results)} chunks\n")

        # Step 2: Build context
        context = self._build_context(results)

        # Step 3: Build prompt
        prompt = self._build_prompt(question, context)

        # Step 4: Get response
        if verbose:
            print("🤖 Generating answer...\n")

        answer = self._get_megallm_response(prompt, stream=stream)

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
            part = f"[Nguồn {i}]\n"

            metadata = result.metadata

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
2. Trích dẫn điều khoản cụ thể nếu có
3. Nếu không tìm thấy thông tin, nói "Không tìm thấy thông tin trong quy chế"
4. Giải thích rõ ràng, dễ hiểu
5. Liệt kê đầy đủ nếu có điều kiện/yêu cầu

Trả lời bằng tiếng Việt:"""

        return prompt

    def _get_megallm_response(self, prompt: str, stream: bool) -> str:
        """Get response from MegaLLM API using OpenAI SDK"""

        try:
            if stream:
                # Streaming response
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=2048,
                    stream=True,
                )

                answer = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        print(content, end="", flush=True)
                        answer += content

                print("\n")
                return answer
            else:
                # Non-streaming response
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=2048,
                )

                answer = response.choices[0].message.content
                print(answer)
                print()
                return answer

        except Exception as e:
            print(f"❌ API Error: {e}")
            raise


def test_megallm():
    """Test với MegaLLM"""
    print("=" * 70)
    print("🧪 TESTING MEGALLM RAG SYSTEM")
    print("=" * 70)
    print()

    import os
    from dotenv import load_dotenv

    # Load API key from .env
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("MEGALLM_API_KEY")

    if not api_key:
        print("❌ MEGALLM_API_KEY not found in .env")
        api_key = input("Enter MegaLLM API key: ")

    # Optional: custom API URL and model
    api_url = os.getenv("MEGALLM_API_URL")  # Optional
    model_name = os.getenv("MEGALLM_MODEL")  # Optional

    # Initialize RAG
    rag = MegaLLMRAG(
        api_key=api_key,
        api_url=api_url,
        model_name=model_name,
    )

    # Test question
    question = "khi nào thì sinh viên bị cảnh báo mức 2"

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


if __name__ == "__main__":
    test_megallm()
