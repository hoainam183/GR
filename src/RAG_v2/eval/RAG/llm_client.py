"""
llm_client.py — Wrapper thống nhất cho LMStudio và Google Gemini 2.5 Flash

Backends:
  LMSTUDIO             → chỉ dùng LMStudio (Qwen3 8B)
  GEMINI               → chỉ dùng Gemini 2.5 Flash
  GEMINI_WITH_FALLBACK → Gemini 2.5 Flash trước, tự fallback LMStudio khi hết RPD/quota
"""

import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from .config import BackendType, EvalConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


# ─── Helpers: phát hiện rate limit errors ────────────────────────────────────

def _is_rate_limit_error(exc: Exception) -> bool:
    """
    Trả về True nếu exception là do hết quota / rate limit Gemini.
    Bắt tất cả các dạng lỗi 429 từ các thư viện khác nhau.
    """
    err_str = str(exc).lower()
    err_type = type(exc).__name__

    # google.api_core.exceptions.ResourceExhausted (HTTP 429)
    if "resourceexhausted" in err_type.lower():
        return True

    # google.api_core.exceptions.TooManyRequests
    if "toomanyrequests" in err_type.lower():
        return True

    # Các chuỗi thông báo lỗi phổ biến từ Gemini API
    rate_limit_keywords = [
        "quota exceeded",
        "rate limit",
        "resource_exhausted",
        "429",
        "too many requests",
        "requests per day",
        "requests per minute",
        "rpd",
        "rpm",
    ]
    return any(kw in err_str for kw in rate_limit_keywords)


# ─── Base interface ──────────────────────────────────────────────────────────

class BaseLLMClient(ABC):
    """Interface chung cho mọi LLM backend."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Gọi LLM và trả về text response."""
        ...

    @abstractmethod
    def get_langchain_llm(self) -> Any:
        """Trả về LangChain LLM object (dùng với RAGAS)."""
        ...

    @abstractmethod
    def get_langchain_embeddings(self) -> Any:
        """Trả về LangChain Embeddings object (dùng với RAGAS)."""
        ...


# ─── LMStudio client ─────────────────────────────────────────────────────────

class LMStudioClient(BaseLLMClient):
    """
    Client cho LMStudio chạy local.
    LMStudio expose OpenAI-compatible API tại http://localhost:1234/v1
    Model: Qwen3 8B (hoặc bất kỳ model nào đang load trong LMStudio)
    """

    def __init__(self, config: EvalConfig = DEFAULT_CONFIG):
        self.cfg = config.lmstudio
        self._check_dependencies()
        self._client = None

    def _check_dependencies(self):
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError(
                "Cần cài: pip install openai\n"
                "LMStudio sử dụng OpenAI-compatible API."
            )

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self.cfg.base_url,
                api_key="lm-studio",    # LMStudio không cần API key thật
            )
        return self._client

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # /no_think tắt thinking mode của Qwen3 — tiết kiệm token, tăng tốc
        for msg in messages:
            if msg["role"] == "user":
                msg["content"] = "/no_think\n" + msg["content"]
                break

        resp = client.chat.completions.create(
            model=self.cfg.model_name,
            messages=messages,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        content = resp.choices[0].message.content
        return content.strip() if content is not None else ""

    def get_langchain_llm(self):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("pip install langchain-openai")

        return ChatOpenAI(
            model=self.cfg.model_name,
            base_url=self.cfg.base_url,
            api_key="lm-studio",
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,  # type: ignore
            timeout=self.cfg.timeout,
        )

    def get_langchain_embeddings(self):
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError:
            raise ImportError("pip install langchain-openai")

        return OpenAIEmbeddings(
            model="text-embedding-nomic-embed-text-v1.5",
            base_url=self.cfg.base_url,
            api_key="lm-studio",  # type: ignore
        )


# ─── Gemini client ───────────────────────────────────────────────────────────

class GeminiClient(BaseLLMClient):
    """
    Client cho Google Gemini 2.5 Flash.
    Chất lượng cao hơn model local, phù hợp để sinh QA dataset chính xác.
    """

    def __init__(self, config: EvalConfig = DEFAULT_CONFIG):
        self.cfg = config.gemini
        self._resolve_api_key()
        self._check_dependencies()

    def _resolve_api_key(self):
        self.api_key = self.cfg.api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Cần cung cấp GOOGLE_API_KEY.\n"
                "Cách 1: export GOOGLE_API_KEY='your-key'\n"
                "Cách 2: config.gemini.api_key = 'your-key'"
            )

    def _check_dependencies(self):
        try:
            import google.generativeai as genai  # noqa: F401
        except ImportError:
            raise ImportError("pip install google-generativeai")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)  # type: ignore
        model = genai.GenerativeModel(  # type: ignore
            model_name=self.cfg.model_name,
            system_instruction=system_prompt or "Bạn là trợ lý AI hữu ích.",
            generation_config=genai.GenerationConfig(  # type: ignore
                temperature=self.cfg.temperature,
                max_output_tokens=self.cfg.max_tokens,
            ),
        )
        # Delay nhỏ tránh burst rate limit
        time.sleep(0.5)
        response = model.generate_content(prompt)
        return response.text.strip()

    def get_langchain_llm(self):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("pip install langchain-google-genai")

        return ChatGoogleGenerativeAI(
            model=self.cfg.model_name,
            google_api_key=self.api_key,
            temperature=self.cfg.temperature,
        )

    def get_langchain_embeddings(self):
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
        except ImportError:
            raise ImportError("pip install langchain-google-genai")

        return GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=self.api_key,  # type: ignore
        )


# ─── Fallback client ─────────────────────────────────────────────────────────

class FallbackClient(BaseLLMClient):
    """
    Gemini 2.5 Flash làm primary; tự động fallback sang LMStudio khi:
      - Nhận lỗi 429 (Too Many Requests)
      - ResourceExhausted (hết RPD/quota ngày)
      - Bất kỳ rate limit error nào khác

    Trạng thái fallback được giữ trong session: một khi đã chuyển sang
    LMStudio thì mọi request tiếp theo cũng dùng LMStudio (tránh retry
    liên tục gây delay). Có thể reset bằng cách gọi reset_to_primary().

    get_langchain_llm() và get_langchain_embeddings() luôn dùng active client
    tại thời điểm gọi (quan trọng vì RAGAS gọi sau khi generate đã chạy xong).
    """

    def __init__(self, config: EvalConfig = DEFAULT_CONFIG):
        self.config = config
        self._gemini = GeminiClient(config)
        self._lmstudio = LMStudioClient(config)
        self._using_fallback = False         # False = đang dùng Gemini
        self._fallback_reason: Optional[str] = None
        self._gemini_call_count = 0
        self._fallback_call_count = 0

    @property
    def active_client(self) -> BaseLLMClient:
        return self._lmstudio if self._using_fallback else self._gemini

    @property
    def active_name(self) -> str:
        if self._using_fallback:
            return f"LMStudio ({self.config.lmstudio.model_name}) [FALLBACK]"
        return f"Gemini ({self.config.gemini.model_name})"

    def _switch_to_fallback(self, reason: str):
        """Chuyển sang LMStudio và log lý do."""
        self._using_fallback = True
        self._fallback_reason = reason
        wait = self.config.gemini.fallback_wait_seconds
        print(f"\n⚠️  RATE LIMIT: {reason}")
        print(f"   → Chuyển sang LMStudio fallback (chờ {wait}s...)")
        time.sleep(wait)
        print(f"   ✓ Đang dùng LMStudio ({self.config.lmstudio.model_name})\n")

    def reset_to_primary(self):
        """Reset về Gemini (dùng nếu quota được reset sau 1 ngày)."""
        self._using_fallback = False
        self._fallback_reason = None
        print("🔄 Reset về Gemini primary client")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Nếu đã chuyển sang fallback → dùng luôn LMStudio
        if self._using_fallback:
            self._fallback_call_count += 1
            return self._lmstudio.generate(prompt, system_prompt)

        # Thử Gemini trước
        try:
            result = self._gemini.generate(prompt, system_prompt)
            self._gemini_call_count += 1
            return result

        except Exception as exc:
            if _is_rate_limit_error(exc):
                self._switch_to_fallback(str(exc)[:120])
                # Retry ngay bằng LMStudio
                self._fallback_call_count += 1
                return self._lmstudio.generate(prompt, system_prompt)
            else:
                # Lỗi khác (network, parse...) → re-raise
                raise

    def get_langchain_llm(self):
        """Trả về LangChain LLM của client đang active."""
        return self.active_client.get_langchain_llm()

    def get_langchain_embeddings(self):
        """Trả về embeddings của client đang active."""
        return self.active_client.get_langchain_embeddings()

    def print_stats(self):
        """In thống kê số lượng call mỗi backend."""
        total = self._gemini_call_count + self._fallback_call_count
        print(f"\n📊 FallbackClient stats:")
        print(f"   Gemini calls   : {self._gemini_call_count:4d} ({self._gemini_call_count/max(total,1)*100:.0f}%)")
        print(f"   LMStudio calls : {self._fallback_call_count:4d} ({self._fallback_call_count/max(total,1)*100:.0f}%)")
        if self._fallback_reason:
            print(f"   Fallback reason: {self._fallback_reason}")


# ─── Factory ─────────────────────────────────────────────────────────────────

def create_llm_client(config: EvalConfig = DEFAULT_CONFIG) -> BaseLLMClient:
    """
    Factory function — trả về client phù hợp với config.backend.

    LMSTUDIO             → LMStudioClient
    GEMINI               → GeminiClient (Gemini 2.5 Flash)
    GEMINI_WITH_FALLBACK → FallbackClient (Gemini 2.5 Flash + LMStudio fallback)
    """
    if config.backend == BackendType.LMSTUDIO:
        print(f"🔧 Backend: LMStudio ({config.lmstudio.model_name}) tại {config.lmstudio.base_url}")
        return LMStudioClient(config)

    elif config.backend == BackendType.GEMINI:
        print(f"✨ Backend: Gemini ({config.gemini.model_name})")
        return GeminiClient(config)

    elif config.backend == BackendType.GEMINI_WITH_FALLBACK:
        print(f"✨ Backend: Gemini ({config.gemini.model_name}) + LMStudio fallback ({config.lmstudio.model_name})")
        return FallbackClient(config)

    else:
        raise ValueError(f"Backend không được hỗ trợ: {config.backend}")