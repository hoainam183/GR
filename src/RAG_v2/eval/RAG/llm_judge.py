"""
LLM Judge — Abstraction layer cho RAGAS LLM judge.

Hỗ trợ 2 backends:
  - GeminiBackend   : Google Gemini (có rate limit)
  - LMStudioBackend : Qwen3 8B qua LM Studio (OpenAI-compatible, localhost:1234)

Dùng qua factory:
    judge = LLMJudgeFactory.create("gemini")
    judge = LLMJudgeFactory.create("lmstudio")
    judge = LLMJudgeFactory.create("auto")   # Gemini trước, fallback LM Studio

Interface thống nhất:
    judge.generate(prompt)        → str     (dùng để generate synthetic Q&A)
    judge.get_ragas_llm()         → RAGAS LLMWrapper
    judge.get_ragas_embeddings()  → RAGAS EmbeddingsWrapper

Chạy test nhanh:
    python eval/llm_judge.py --backend lmstudio
    python eval/llm_judge.py --backend gemini
"""

from __future__ import annotations

import logging
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Config defaults (override bằng env var) ─────────────────────────────────

GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL       = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

LMSTUDIO_BASE_URL  = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL     = os.getenv("LMSTUDIO_MODEL", "qwen3-8b")
LMSTUDIO_API_KEY   = os.getenv("LMSTUDIO_API_KEY", "lm-studio")


# ─── Abstract base ────────────────────────────────────────────────────────────


class LLMJudgeBackend(ABC):
    """Base class cho tất cả LLM judge backends."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate text từ prompt — dùng cho synthetic Q&A generation."""
        ...

    @abstractmethod
    def get_ragas_llm(self):
        """Trả về RAGAS-compatible LLM wrapper."""
        ...

    @abstractmethod
    def get_ragas_embeddings(self):
        """Trả về RAGAS-compatible Embeddings wrapper."""
        ...

    def is_available(self) -> bool:
        """Ping test — kiểm tra backend có accessible không."""
        try:
            result = self.generate("test", max_tokens=5)
            return bool(result)
        except Exception as e:
            logger.debug("%s availability check failed: %s", self.name, e)
            return False


# ─── Gemini backend ───────────────────────────────────────────────────────────


class GeminiBackend(LLMJudgeBackend):
    """Google Gemini backend dùng langchain-google-genai + google-generativeai."""

    def __init__(
        self,
        api_key: str = GEMINI_API_KEY,
        model: str = GEMINI_MODEL,
        temperature: float = 0.0,
    ) -> None:
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY chưa được set.\n"
                "export GEMINI_API_KEY=your_key"
            )
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self._genai_model = None
        self._ragas_llm = None
        self._ragas_emb = None

    @property
    def name(self) -> str:
        return f"gemini/{self.model}"

    def _get_genai_model(self):
        if self._genai_model is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)  # type: ignore
            self._genai_model = genai.GenerativeModel(self.model)  # type: ignore
        return self._genai_model

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        model = self._get_genai_model()
        response = model.generate_content(prompt)
        return response.text.strip()

    def get_ragas_llm(self):
        if self._ragas_llm is None:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from ragas.llms import LangchainLLMWrapper
            lc_llm = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=self.api_key,
                temperature=self.temperature,
            )
            self._ragas_llm = LangchainLLMWrapper(lc_llm)
        return self._ragas_llm

    def get_ragas_embeddings(self):
        if self._ragas_emb is None:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            from ragas.embeddings import LangchainEmbeddingsWrapper
            lc_emb = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=self.api_key,  # type: ignore
            )
            self._ragas_emb = LangchainEmbeddingsWrapper(lc_emb)
        return self._ragas_emb


# ─── LM Studio backend ────────────────────────────────────────────────────────


class LMStudioBackend(LLMJudgeBackend):
    """Qwen3 8B qua LM Studio OpenAI-compatible API (localhost:1234).

    Lưu ý Qwen3 thinking mode:
        Qwen3 có thể sinh ra block <think>...</think> trước câu trả lời.
        _strip_thinking() tự động loại bỏ phần này khỏi output.
        Nếu muốn tắt thinking hoàn toàn: thêm "/no_think" vào cuối prompt,
        hoặc set enable_thinking=False trong LM Studio model settings.
    """

    def __init__(
        self,
        base_url: str = LMSTUDIO_BASE_URL,
        model: str = LMSTUDIO_MODEL,
        api_key: str = LMSTUDIO_API_KEY,
        temperature: float = 0.0,
        timeout: int = 180,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout
        self._client = None
        self._ragas_llm = None
        self._ragas_emb = None

    @property
    def name(self) -> str:
        return f"lmstudio/{self.model}"

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """Strip Qwen3 <think>...</think> block và khoảng trắng thừa."""
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return cleaned.strip()

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        client = self._get_client()
        # Thêm /no_think để tắt thinking mode của Qwen3, giảm latency
        full_prompt = prompt + "\n/no_think"
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": full_prompt}],
            max_tokens=max_tokens,
            temperature=self.temperature,
        )
        raw = resp.choices[0].message.content or ""
        return self._strip_thinking(raw)

    def get_ragas_llm(self):
        if self._ragas_llm is None:
            from langchain_openai import ChatOpenAI
            from ragas.llms import LangchainLLMWrapper
            lc_llm = ChatOpenAI(
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,  # type: ignore
                temperature=self.temperature,
                timeout=self.timeout,
            )
            self._ragas_llm = LangchainLLMWrapper(lc_llm)
        return self._ragas_llm

    def get_ragas_embeddings(self):
        """
        Ưu tiên: LM Studio /v1/embeddings → fallback BGE-M3 qua sentence-transformers.
        LM Studio cần load sẵn 1 embedding model (vd: nomic-embed-text) để dùng endpoint này.
        """
        if self._ragas_emb is None:
            self._ragas_emb = self._build_embeddings()
        return self._ragas_emb

    def _build_embeddings(self):
        # 1) Thử LM Studio embeddings endpoint
        try:
            from langchain_openai import OpenAIEmbeddings
            from ragas.embeddings import LangchainEmbeddingsWrapper
            emb = OpenAIEmbeddings(
                model="text-embedding-ada-002",  # LM Studio map tới local model
                base_url=self.base_url,
                api_key=self.api_key,  # type: ignore
                timeout=self.timeout,
            )
            emb.embed_query("ping")  # test
            logger.info("LMStudio: dùng local embeddings endpoint")
            return LangchainEmbeddingsWrapper(emb)
        except Exception as e:
            logger.warning(
                "LMStudio embeddings endpoint không available (%s) — "
                "fallback sang sentence-transformers BGE-M3.", e
            )

        # 2) Fallback: BGE-M3 local qua sentence-transformers
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from ragas.embeddings import LangchainEmbeddingsWrapper
            hf_emb = HuggingFaceEmbeddings(
                model_name="BAAI/bge-m3",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("LMStudio: dùng BGE-M3 local (sentence-transformers) cho RAGAS embeddings")
            return LangchainEmbeddingsWrapper(hf_emb)
        except ImportError:
            raise RuntimeError(
                "Không thể init RAGAS embeddings cho LMStudio backend.\n"
                "Hãy load 1 embedding model trong LM Studio (vd: nomic-embed-text),\n"
                "hoặc: pip install langchain-community sentence-transformers"
            )


# ─── Auto backend ─────────────────────────────────────────────────────────────


class AutoBackend(LLMJudgeBackend):
    """Tự động chọn backend: thử Gemini trước, fallback LM Studio khi rate limited.

    Rate limit detection: HTTP 429 / "quota" / "resource_exhausted" trong error message.
    """

    def __init__(self) -> None:
        self._primary: Optional[LLMJudgeBackend] = None
        self._fallback: Optional[LLMJudgeBackend] = None
        self._active: Optional[LLMJudgeBackend] = None
        self._setup()

    def _setup(self) -> None:
        candidates = []
        if GEMINI_API_KEY:
            try:
                candidates.append(GeminiBackend())
                logger.info("AutoBackend: Gemini available")
            except Exception as e:
                logger.warning("AutoBackend: Gemini init failed: %s", e)
        try:
            candidates.append(LMStudioBackend())
            logger.info("AutoBackend: LMStudio available")
        except Exception as e:
            logger.warning("AutoBackend: LMStudio init failed: %s", e)

        if not candidates:
            raise RuntimeError(
                "Không có LLM backend nào khả dụng.\n"
                "Set GEMINI_API_KEY hoặc chạy LM Studio ở localhost:1234."
            )
        self._primary = candidates[0]
        self._fallback = candidates[1] if len(candidates) > 1 else None
        self._active = self._primary
        assert self._primary is not None
        logger.info(
            "AutoBackend: primary=%s, fallback=%s",
            self._primary.name,
            self._fallback.name if self._fallback else "None",
        )

    @property
    def name(self) -> str:
        assert self._active is not None
        return f"auto[active={self._active.name}]"

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(kw in msg for kw in ("429", "rate limit", "quota", "resource_exhausted"))

    def _try_switch_fallback(self) -> bool:
        assert self._active is not None
        if self._fallback and self._active is not self._fallback:
            logger.warning(
                "Rate limit trên %s — chuyển sang %s",
                self._active.name, self._fallback.name,
            )
            self._active = self._fallback
            return True
        return False

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        assert self._active is not None
        for attempt in range(2):
            try:
                return self._active.generate(prompt, max_tokens)
            except Exception as e:
                if self._is_rate_limit_error(e) and attempt == 0 and self._try_switch_fallback():
                    time.sleep(2)
                    continue
                raise
        return ""

    def get_ragas_llm(self):
        assert self._active is not None
        return self._active.get_ragas_llm()

    def get_ragas_embeddings(self):
        assert self._active is not None
        return self._active.get_ragas_embeddings()


# ─── Factory ──────────────────────────────────────────────────────────────────


class LLMJudgeFactory:
    """Factory tạo LLM judge backend theo tên string."""

    @classmethod
    def create(cls, backend: str = "auto", **kwargs) -> LLMJudgeBackend:
        """
        Args:
            backend: "gemini" | "lmstudio" | "auto"
            **kwargs: Override params (api_key, model, base_url, temperature, ...)

        Ví dụ::
            judge = LLMJudgeFactory.create("gemini")
            judge = LLMJudgeFactory.create("lmstudio", model="qwen3-8b-instruct")
            judge = LLMJudgeFactory.create("auto")
        """
        backend = backend.lower().strip()
        mapping = {
            "gemini": GeminiBackend,
            "lmstudio": LMStudioBackend,
            "auto": AutoBackend,
        }
        if backend not in mapping:
            raise ValueError(
                f"Backend '{backend}' không hợp lệ. Chọn: {list(mapping.keys())}"
            )
        klass = mapping[backend]
        if backend == "auto":
            return klass()
        import inspect
        valid = inspect.signature(klass.__init__).parameters
        filtered = {k: v for k, v in kwargs.items() if k in valid}
        return klass(**filtered)


# ─── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(description="Test LLM judge backend")
    parser.add_argument("--backend", choices=["gemini", "lmstudio", "auto"], default="auto")
    parser.add_argument("--prompt", default="Sinh viên ĐHBK cần bao nhiêu tín chỉ để tốt nghiệp?")
    args = parser.parse_args()

    print(f"\nTesting backend: {args.backend}")
    print("─" * 50)
    try:
        judge = LLMJudgeFactory.create(args.backend)
        print(f"Backend : {judge.name}")
        print(f"Prompt  : {args.prompt}\n")
        resp = judge.generate(args.prompt)
        print(f"Response:\n{resp}")
        print("\n✅ Backend hoạt động bình thường.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)