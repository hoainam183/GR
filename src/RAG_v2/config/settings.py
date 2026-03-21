"""Application Settings — centralised configuration via Pydantic BaseSettings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


# ═══════════════════════════════════════════════════════════════════════════════
class Settings(BaseSettings):
    """All configurable knobs for the RAG v2 system.

    Values are loaded from environment variables and / or a ``.env`` file
    located at the RAG_v2 root.  Any field can be overridden by setting the
    corresponding env var (case-insensitive).

    Parameters:
        google_api_key: Google API key for Gemini.
        openai_api_key: OpenAI API key (for query reflection).
        tavily_api_key: Tavily API key for web search fallback.
        qdrant_host: Qdrant server hostname.
        qdrant_port: Qdrant server port.
        elasticsearch_host: Elasticsearch hostname.
        elasticsearch_port: Elasticsearch port.
        mongodb_uri: MongoDB connection URI.
        mongodb_database: MongoDB database name.
        collections: Qdrant collection names to search.
        chat_model: Gemini model identifier.
        chat_temperature: Sampling temperature for chat.
        chat_max_tokens: Max tokens for chat generation.
        top_k: Final number of documents after reranking.
        vector_top_k: Per-collection vector search limit.
        keyword_top_k: Per-collection keyword search limit.
        vector_pool_k: Global vector pool size after collection merge.
        keyword_pool_k: Global keyword pool size after collection merge.
        vector_weight: Weight for vector scores in RRF fusion.
        keyword_weight: Weight for keyword scores in RRF fusion.
        reranker_top_k: Number of documents after reranking.
        router_mode: Query router mode (``classifier`` or ``llm``).
        self_eval_enabled: Whether to run self-evaluation on responses.
        tavily_fallback_enabled: Whether to use Tavily when self-eval fails.
        cors_origins: Allowed CORS origins.
        api_host: FastAPI listen host.
        api_port: FastAPI listen port.
    """

    # --- API Keys ---
    google_api_key: str = ""
    openai_api_key: str = ""
    tavily_api_key: str = ""

    # --- Qdrant ---
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # --- Elasticsearch ---
    elasticsearch_host: str = "localhost"
    elasticsearch_port: int = 9200

    # --- MongoDB ---
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "rag_chatbot"
    mongodb_enabled: bool = True

    # --- Collections ---
    collections: List[str] = ["stsv", "quydinh", "kehoach", "ctdt"]

    # --- Chat Model ---
    chat_model: str = "gemini-2.5-flash"
    chat_temperature: float = 0.3
    chat_max_tokens: int = 1024 * 5

    # --- Retrieval ---
    top_k: int = 5
    vector_top_k: int = 20
    keyword_top_k: int = 20
    vector_pool_k: int = 15
    keyword_pool_k: int = 15
    vector_weight: float = 0.8
    keyword_weight: float = 0.2

    # --- Reranker ---
    reranker_top_k: int = 5

    # --- Router ---
    router_mode: str = "classifier"

    # --- Evaluation & Fallback ---
    self_eval_enabled: bool = False
    tavily_fallback_enabled: bool = False

    # --- CORS ---
    cors_origins: List[str] = ["*"]

    # --- Server ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
