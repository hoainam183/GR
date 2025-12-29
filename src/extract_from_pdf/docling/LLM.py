# rag_system_free.py

from retriever import FAISSRetriever
from hybrid_retriever import HybridRetriever
from typing import List, Dict
import json


class FreeRAG:
    """
    RAG System với Free LLMs
    """

    def __init__(
        self,
        retriever: FAISSRetriever = None,
        llm_provider: str = "gemini",  # "gemini", "groq", "ollama"
        api_key: str = None,
        model_name: str = None,
    ):
        """
        Initialize Free RAG

        Args:
            llm_provider: "gemini", "groq", hoặc "ollama"
            api_key: API key (for gemini/groq)
            model_name: Model name (optional)
        """
        print("🔄 Initializing Free RAG System...")

        # Load retriever
        if retriever is None:
            print("   Creating retriever...")
            self.retriever = FAISSRetriever()
        else:
            self.retriever = retriever

        # Setup LLM
        self.llm_provider = llm_provider

        print("✅ Free RAG System ready!\n")
        self._setup_gemini(api_key, model_name)

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

        results = self.retriever.search(
            query=question,
            top_k=top_k,
            filters=filters,
            include_footnotes=True,
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

    def _build_context(self, results: List[Dict]) -> str:
        """Build context từ chunks"""
        context_parts = []

        for i, result in enumerate(results, 1):
            part = f"[Nguồn {i}]\n"

            if result["metadata"].get("article"):
                part += f"Điều khoản: {result['metadata']['article']}\n"

            part += f"Nội dung: {result['content']}\n"

            if result.get("footnotes"):
                part += "\nChú thích:\n"
                for fn in result["footnotes"]:
                    part += f"  {fn['content']}\n"

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
                    3. Nếu không tìm thấy, nói "Không tìm thấy thông tin"
                    4. Giải thích rõ ràng, dễ hiểu
                    5. Liệt kê đầy đủ nếu có điều kiện/yêu cầu

                    Trả lời bằng tiếng Việt:"""

        return prompt

    def _get_gemini_response(self, prompt: str, stream: bool) -> str:
        """Gemini response"""

        generation_config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
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
    print("🧪 TESTING WITH GOOGLE GEMINI (FREE)")
    print("=" * 70)
    print()

    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    print(api_key)
    if not api_key:
        api_key = input("Enter Gemini API key: ")

    rag = FreeRAG(llm_provider="gemini", api_key=api_key)

    question = "khi nào thì sinh viên bị cảnh báo mức 2"

    result = rag.answer(question, top_k=10, stream=True)

    print("\n" + "=" * 70)
    print(f"Provider: {result['llm_provider']}")
    print(f"Model: {result['model_name']}")
    print(f"Sources: {result['num_sources']}")
    print("=" * 70)


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    test_gemini()
