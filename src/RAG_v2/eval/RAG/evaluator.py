"""
evaluator.py — Chạy RAGAS evaluation trên QA dataset

Tính các metrics:
  - faithfulness        : LLM answer có trung thực với context không?
  - answer_relevancy    : Answer có liên quan đến question không?
  - context_precision   : Context được retrieve có chứa thông tin cần thiết không?
  - context_recall      : Ground truth có được cover bởi context không?
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import EvalConfig, DEFAULT_CONFIG
from .qa_generator import QADataset, QAPair
from .llm_client import BaseLLMClient, create_llm_client


@dataclass
class EvalResult:
    """Kết quả RAGAS evaluation."""
    metrics: dict[str, float] = field(default_factory=dict)
    per_sample_scores: list[dict] = field(default_factory=list)
    total_samples: int = 0
    backend_used: str = ""

    def summary(self) -> str:
        lines = [
            f"\n{'='*50}",
            f" RAGAS Evaluation Results ({self.backend_used})",
            f"{'='*50}",
            f" Số mẫu: {self.total_samples}",
            "",
        ]
        metric_names = {
            "faithfulness": "Faithfulness      (trung thực)",
            "answer_relevancy": "Answer Relevancy  (liên quan)",
            "context_precision": "Context Precision (chính xác)",
            "context_recall": "Context Recall    (bao phủ)",
        }
        for key, name in metric_names.items():
            if key in self.metrics:
                score = self.metrics[key]
                bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
                lines.append(f"  {name}: {score:.3f} |{bar}|")
        lines.append(f"{'='*50}\n")
        return "\n".join(lines)

    def save(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "backend": self.backend_used,
            "total_samples": self.total_samples,
            "metrics": self.metrics,
            "per_sample_scores": self.per_sample_scores,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã lưu eval results → {path}")


class RAGASEvaluator:
    """
    Wrapper RAGAS evaluation.

    RAGAS tính các metrics bằng cách dùng một LLM "judge" để đánh giá.
    Chúng ta dùng cùng LLM client đã setup (LMStudio hoặc Gemini).
    """

    def __init__(self, llm_client: BaseLLMClient, config: EvalConfig = DEFAULT_CONFIG):
        self.client = llm_client
        self.config = config
        self._check_ragas()

    def _check_ragas(self):
        try:
            import ragas
        except ImportError:
            raise ImportError(
                "Cần cài RAGAS:\n"
                "  pip install ragas\n"
                "  pip install langchain langchain-openai"
            )

    def _build_ragas_dataset(self, qa_dataset: QADataset, answers: list[str]) -> "Any":
        """Chuyển QADataset sang format RAGAS Dataset."""
        from datasets import Dataset

        assert len(answers) == len(qa_dataset.pairs), (
            f"Số answers ({len(answers)}) không khớp với số QA pairs ({len(qa_dataset.pairs)})"
        )

        data = {
            "question": [],
            "answer": [],
            "contexts": [],
            "ground_truth": [],
        }

        for pair, answer in zip(qa_dataset.pairs, answers):
            data["question"].append(pair.question)
            data["answer"].append(answer)
            data["contexts"].append([pair.context])     # List of retrieved contexts
            data["ground_truth"].append(pair.ground_truth)

        return Dataset.from_dict(data)

    def _load_metrics(self) -> list:
        """Load các RAGAS metrics được cấu hình."""
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )

        metric_map = {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
        }

        return [
            metric_map[m]
            for m in self.config.ragas_metrics
            if m in metric_map
        ]

    def evaluate(
        self,
        qa_dataset: QADataset,
        answers: list[str],
        batch_size: int = 5,
    ) -> EvalResult:
        """
        Chạy RAGAS evaluation.

        Args:
            qa_dataset: Dataset chứa questions và ground truths
            answers: List câu trả lời từ RAG system (hoặc LLM)
            batch_size: Số samples xử lý mỗi lần (tránh timeout)

        Returns:
            EvalResult với scores và per-sample breakdown
        """
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper

        print(f"\n📊 Bắt đầu RAGAS evaluation...")
        print(f"   Metrics: {self.config.ragas_metrics}")
        print(f"   Số mẫu: {len(qa_dataset.pairs)}")

        # Lấy LangChain wrapper cho RAGAS
        langchain_llm = LangchainLLMWrapper(self.client.get_langchain_llm())
        langchain_emb = LangchainEmbeddingsWrapper(self.client.get_langchain_embeddings())

        # Build RAGAS dataset
        ragas_dataset = self._build_ragas_dataset(qa_dataset, answers)

        # Config metrics với LLM/Embeddings của chúng ta
        metrics = self._load_metrics()
        for metric in metrics:
            metric.llm = langchain_llm
            if hasattr(metric, "embeddings"):
                metric.embeddings = langchain_emb

        # Chạy evaluation
        print("\n  Đang chạy evaluation (có thể mất vài phút)...")
        result_df: Any = evaluate(
            dataset=ragas_dataset,
            metrics=metrics,
            raise_exceptions=False,    # Tiếp tục dù có lỗi ở sample nào đó
        )

        # Thu thập kết quả
        scores_dict = result_df.to_pandas().to_dict(orient="records")
        aggregate = {}
        for metric_name in self.config.ragas_metrics:
            if metric_name in result_df:
                aggregate[metric_name] = float(result_df[metric_name])

        eval_result = EvalResult(
            metrics=aggregate,
            per_sample_scores=scores_dict,
            total_samples=len(qa_dataset.pairs),
            backend_used=self.config.backend.value,
        )

        print(eval_result.summary())
        return eval_result


class SimpleAnswerGenerator:
    """
    Sinh câu trả lời đơn giản từ context (giả lập RAG system).
    Dùng để test evaluator mà không cần RAG pipeline thật.
    """

    def __init__(self, llm_client: BaseLLMClient):
        self.client = llm_client

    ANSWER_PROMPT = """Dựa vào đoạn văn bản dưới đây, hãy trả lời câu hỏi một cách ngắn gọn và chính xác.
Chỉ sử dụng thông tin trong đoạn văn, không thêm thông tin bên ngoài.

ĐOẠN VĂN:
{context}

CÂU HỎI: {question}

TRẢ LỜI:"""

    def generate_answers(self, pairs: list[QAPair]) -> list[str]:
        """Sinh câu trả lời cho tất cả QA pairs."""
        answers = []
        for i, pair in enumerate(pairs, 1):
            print(f"  Sinh answer {i}/{len(pairs)}...", end="\r")
            prompt = self.ANSWER_PROMPT.format(
                context=pair.context[:2000],    # Giới hạn context length
                question=pair.question,
            )
            try:
                answer = self.client.generate(prompt)
                answers.append(answer)
            except Exception as e:
                print(f"\n  ⚠️  Lỗi answer {i}: {e}")
                answers.append("")    # Answer rỗng → điểm thấp
        print(f"  ✓ Đã sinh {len(answers)} answers          ")
        return answers


if __name__ == "__main__":
    """Test nhanh với mock data."""
    from .qa_generator import QAPair, QADataset

    # Mock data
    mock_dataset = QADataset(pairs=[
        QAPair(
            question="Tổng số tín chỉ của chương trình CNTT Việt-Nhật là bao nhiêu?",
            ground_truth="148 tín chỉ",
            question_type="factoid",
            source_chunk_id="chunk_0001",
            source_file="ITE6_fix_chunks.json",
            context="Khối lượng kiến thức toàn khóa: 148 tín chỉ\nThời gian đào tạo: 4 năm",
            hierarchy_path="CHƯƠNG TRÌNH GIÁO DỤC ĐẠI HỌC 2020 > CỬ NHÂN CNTT VIỆT-NHẬT",
        ),
    ])
    mock_answers = ["Tổng số tín chỉ là 148 tín chỉ."]

    print("Mock dataset created:", mock_dataset.to_dict())
    print("Để chạy RAGAS evaluation thật, cần setup LLM client và chạy evaluator.evaluate()")
