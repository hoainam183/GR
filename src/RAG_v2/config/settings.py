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

    Provider strategy (recommended):
        - llm_provider = "gemini"      → chat answer generation (quality-critical)
        - reflection_provider = "gemini" → query rewrite (quality-critical)
        - agent_model = Qwen2.5 (local) → tool-calling only (low quality OK)
        - agent_synthesis_provider = "gemini" → final agent answer (quality-critical)

    Parameters:
        google_api_key: Google API key for Gemini.
        openai_api_key: OpenAI API key (optional, not used by default pipeline).
        tavily_api_key: Tavily API key for web search fallback.
        qdrant_host: Qdrant server hostname.
        qdrant_port: Qdrant server port.
        elasticsearch_host: Elasticsearch hostname.
        elasticsearch_port: Elasticsearch port.
        mongodb_uri: MongoDB connection URI.
        mongodb_database: MongoDB database name.
        collections: Qdrant collection names to search.
        chat_model: Gemini model identifier for answer generation.
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

    # --- Provider Selectors (change in .env, no code edits needed) ---
    # ✅ GEMINI: chat answer generation — quality-critical, needs strong model
    llm_provider: str = "gemini"       # gemini | openai | azure | ollama | lm_studio
    embedding_provider: str = "ensemble"  # ensemble | bge_m3 | e5
    reranker_provider: str = "bge"     # bge | cohere | none

    # --- API Keys ---
    google_api_key: str = ""
    openai_api_key: str = ""
    tavily_api_key: str = ""

    # Unified LLM API key alias (active provider's key resolved by factory)
    llm_api_key: str = ""

    # --- Azure OpenAI ---
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_deployment: str = ""

    # --- LM Studio / Local ---
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_url: str = "http://localhost:1234/v1"

    # --- Agent (LangGraph) ---
    # ✅ LM STUDIO / QWEN: tool-calling only — needs fast inference, low quality OK
    agent_enabled: bool = True
    agent_max_iterations: int = 3       # reduced from 4 → faster, less runaway
    agent_model: str = "qwen2.5-7b-instruct"  # local Qwen for tool selection
    agent_temperature: float = 0.0     # deterministic tool selection
    agent_max_tokens: int = 1200       # enough for multi-tool reasoning
    agent_tool_result_limit: int = 5000  # max chars per ToolMessage

    # Agent synthesis — uses a STRONGER model for the final answer.
    # ✅ GEMINI: synthesis is quality-critical (user-facing final answer)
    agent_synthesis_provider: str = "gemini"   # "" | "gemini" | "lm_studio" | "ollama"
    agent_synthesis_model: str = "gemini-3.1-flash-lite"  # fast + quality
    agent_synthesis_temperature: float = 0.2
    agent_synthesis_max_tokens: int = 2500     # increased from 2000 to prevent truncation

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"

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

    # --- Chat Model (answer generation) ---
    # ✅ GEMINI: main answer generation — most important quality point
    chat_model: str = "gemini-3.1-flash-lite"   # fast + quality
    chat_temperature: float = 0.0
    chat_max_tokens: int = 1500            # increased from 1024 to prevent mid-sentence truncation

    # --- Retrieval ---
    top_k: int = 5
    vector_top_k: int = 50
    keyword_top_k: int = 50
    vector_pool_k: int = 40
    keyword_pool_k: int = 40
    vector_weight: float = 0.8
    keyword_weight: float = 0.2
    context_doc_char_limit: int = 2000
    context_total_char_budget: int = 12000
    context_list_total_char_budget: int = 24000
    agent_search_result_count: int = 4
    agent_search_result_char_limit: int = 1200

    # --- Reranker ---
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 5
    # BGE reranker raw-logit threshold. Documents scoring below this are
    # dropped from the context. 0.0 is the natural decision boundary;
    # lower to -0.5 if you need more recall, raise to 0.5 for higher precision.
    reranker_score_threshold: float = 0.0
    # Table chunks use a relaxed threshold because cross-encoder typically gives
    # lower raw logits for tabular text. -1.0 keeps clearly relevant tables
    # (scores > -1.0) while dropping irrelevant/wrong-program tables that tend
    # to score below -1.0 (previously -5.0 was too permissive, allowing
    # wrong-program table docs to pollute LLM context).
    reranker_table_score_threshold: float = -1.0

    # --- Router ---
    router_mode: str = "classifier"

    # --- Evaluation & Fallback ---
    self_eval_enabled: bool = False     # disabled by default — adds ~2-5s per query
    # BGE reranker returns raw logits, not probabilities. Keep this very high
    # to avoid skipping self-eval just because a raw logit is greater than 0.72.
    self_eval_min_top_score: float = 100.0
    tavily_fallback_enabled: bool = False
    tavily_search_depth: str = "basic"    # basic (1 credit) | advanced (2 credits)
    tavily_max_results: int = 5           # fetch pool size (filter xuống tavily_web_result_count)
    tavily_web_content_char_limit: int = 1500  # per-result content char limit cho web results
    tavily_web_result_count: int = 3      # số results giữ lại sau filter (≤ max_results)
    web_fallback_dynamic_collections: List[str] = ["kehoach"]
    web_fallback_on_dynamic: bool = True
    web_fallback_on_no_info: bool = True
    tavily_cache_ttl_seconds: int = 3600
    tavily_cache_maxsize: int = 200

    # --- Offline Evaluation ---
    post_index_eval_enabled: bool = True
    post_index_eval_command: str = ""
    post_index_eval_max_cases: int = 120

    # --- Reflection ---
    # ✅ GEMINI: query rewriting — quality-critical for retrieval accuracy
    reflection_enabled: bool = True
    reflection_provider: str = "gemini"      # gemini | lm_studio | ollama | openai
    reflection_model: str = "gemini-3.1-flash-lite"  # fast flash for rewrite task
    reflection_temperature: float = 0.0      # low temp → more deterministic rewrite
    reflection_max_tokens: int = 1024         # increased from 256 to prevent truncation

    # --- Collection-aware Routing (Phase 8) ---
    domain_routing_enabled: bool = True
    domain_confidence_threshold: float = 0.65

    # --- Auto Crawler ---
    crawler_enabled: bool = True
    crawler_schedule_hour: int = 2
    crawler_schedule_minute: int = 0
    crawler_delay: float = 1.0
    crawler_retention_months: int = 6
    crawler_tags: str = "ĐTĐH:%C4%90T%C4%90H"  # comma-sep "Name:encoded,..."

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True            # Master switch for Redis
    redis_max_connections: int = 20
    redis_socket_timeout: float = 5.0
    redis_connect_timeout: float = 5.0
    redis_health_check_interval: int = 30  # seconds between PING on idle conns
    use_redis_session: bool = True        # Phase 1: session migration
    use_redis_cache: bool = True          # Phase 2: LLM response cache
    use_redis_history: bool = True        # Phase 2: conversation history cache

    # --- Rate Limiting ---
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 20              # requests per minute
    rate_limit_rpd: int = 200             # requests per day
    rate_limit_alert_threshold: float = 0.8  # alert at 80% capacity

    # --- Retrieval Improvement Flags (all default OFF for safe rollout) ---
    web_query_enrichment_enabled: bool = False    # A1: academic year + homepage filter
    score_cliff_enabled: bool = False             # B1: per-collection score cliff
    per_collection_norm_enabled: bool = False     # B2: per-collection normalization
    sibling_expansion_enabled: bool = False       # C1: sibling chunk expansion
    parent_context_enabled: bool = True           # C5: parent-child context expansion
    freshness_tavily_check_enabled: bool = False  # C3: date_str freshness check
    low_conf_pool_expand_enabled: bool = False    # C4: 2x candidate pool in Tier 3
    hyde_enabled: bool = False                    # HyDE post-rerank fallback
    hyde_min_results: int = 3                     # trigger when reranked < N results
    hyde_confidence_threshold: float = 0.3        # trigger when reranker mean < this
    sibling_budget_ratio: float = 0.30            # 30% of total budget for siblings
    sibling_per_doc_limit: int = 800              # Per-sibling char limit
    parent_max_chars: int = 1500                  # Max chars from parent content
    parent_max_chars_agent: int = 500             # Reduced for agent (tighter token budget)
    context_total_char_budget_with_expansion: int = 16000  # Expanded total when siblings

    # --- Admin / Document Upload ---
    superadmin_user_ids: str = ""       # comma-separated MongoDB ObjectIds
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50
    max_upload_batch: int = 5

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
