"""
config.py — Cấu hình LLM backend cho RAG Evaluation
Hỗ trợ: LMStudio (Qwen3 8B local) và Google Gemini 2.5 Flash
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class BackendType(str, Enum):
    LMSTUDIO = "lmstudio"
    GEMINI = "gemini"
    GEMINI_WITH_FALLBACK = "gemini_with_fallback"   # Gemini 2.5 Flash → fallback LMStudio khi hết RPD


@dataclass
class LMStudioConfig:
    base_url: str = "http://localhost:1234/v1"
    model_name: str = "qwen3-8b"          # Tên model trong LMStudio
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: int = 120                     # giây, model local cần thêm thời gian


@dataclass
class GeminiConfig:
    model_name: str = "gemini-3.1-flash-lite-preview"  # gemini-3.1-flash-lite-preview | gemini-3.1-flash-lite-preview-preview-04-17
    temperature: float = 0.1
    max_tokens: int = 2048
    api_key: Optional[str] = None         # None → đọc từ GOOGLE_API_KEY env
    # Fallback settings (dùng khi backend = GEMINI_WITH_FALLBACK)
    retry_on_rate_limit: bool = True       # tự động retry khi bị 429
    fallback_wait_seconds: float = 5.0    # chờ trước khi chuyển sang LMStudio


@dataclass
class EvalConfig:
    """Cấu hình tổng thể cho pipeline evaluation."""

    backend: BackendType = BackendType.GEMINI_WITH_FALLBACK  # default: Gemini → LMStudio fallback

    # Đường dẫn dữ liệu
    chunk_files: list = field(default_factory=lambda: [
        "data/ITE6_fix_chunks.json",
        "data/06__Quy_dinh_ngoai_ngu_K70_chunks.json",
    ])
    output_dir: str = "outputs"

    # Tham số sinh QA
    num_questions_per_chunk: int = 2       # số câu hỏi mỗi chunk
    max_chunks_to_sample: int = 30         # giới hạn chunk để tránh tốn quota
    min_chunk_size: int = 100              # bỏ qua chunk quá ngắn (ký tự)

    # Tỷ lệ loại câu hỏi (tổng = 1.0)
    question_type_ratios: dict = field(default_factory=lambda: {
        "factoid":      0.35,   # Câu hỏi sự kiện cụ thể
        "multi_hop":    0.25,   # Cần kết hợp nhiều thông tin
        "comparative":  0.20,   # So sánh
        "procedural":   0.20,   # Quy trình, điều kiện
    })

    # RAGAS metrics cần đánh giá
    ragas_metrics: list = field(default_factory=lambda: [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    ])

    lmstudio: LMStudioConfig = field(default_factory=LMStudioConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)


# ─── Singleton config (import từ các module khác) ───────────────────────────
DEFAULT_CONFIG = EvalConfig()