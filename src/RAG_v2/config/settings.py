"""Application Settings — centralised configuration via Pydantic BaseSettings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from pydantic import Field
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
        - llm_provider = "deepseek"    → chat answer generation (quality-critical)
        - reflection_provider = "gemini" → query rewrite (quality-critical)
        - agent_model = Qwen2.5 (local) → tool-calling only (low quality OK)
        - agent_synthesis_provider = "gemini" → final agent answer (quality-critical)

    Parameters:
        deepseek_api_key: DeepSeek API key for answer generation.
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
        chat_model: Chat model identifier for answer generation.
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
    # ✅ DEEPSEEK: chat answer generation — quality-critical, needs strong model
    llm_provider: str = (
        "deepseek"  # deepseek | gemini | openai | azure | ollama | lm_studio
    )
    embedding_provider: str = "ensemble"  # ensemble | bge_m3 | e5
    reranker_provider: str = "bge"  # bge | cohere | none

    # --- API Keys ---
    deepseek_api_key: str = ""
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
    agent_max_iterations: int = 3  # reduced from 4 → faster, less runaway
    agent_model: str = "qwen2.5-7b-instruct"  # local Qwen for tool selection
    agent_temperature: float = 0.0  # deterministic tool selection
    agent_max_tokens: int = 1200  # enough for multi-tool reasoning
    agent_tool_result_limit: int = 5000  # max chars per ToolMessage

    # Agent synthesis — uses a STRONGER model for the final answer.
    # ✅ GEMINI: synthesis is quality-critical (user-facing final answer)
    agent_synthesis_provider: str = (
        "gemini"  # "" | "gemini" | "lm_studio" | "ollama"
    )
    agent_synthesis_model: str = "gemini-3.1-flash-lite"  # fast + quality
    agent_synthesis_temperature: float = 0.2
    agent_synthesis_max_tokens: int = (
        2500  # increased from 2000 to prevent truncation
    )

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
    # When True, bypass collection routing and run hybrid search across ALL
    # collections in `collections`. Useful for debugging or when a query
    # is known to span multiple domains. When False (default), the pipeline
    # routes to the collection(s) chosen by the classifier / selector.
    find_all: bool = False

    # --- Chat Model (answer generation) ---
    # ✅ DEEPSEEK: main answer generation — most important quality point
    chat_model: str = "deepseek-v4-flash"  # fast + quality
    chat_temperature: float = 0.0
    chat_max_tokens: int = (
        1500  # increased from 1024 to prevent mid-sentence truncation
    )

    # --- Retrieval ---
    top_k: int = 7
    vector_top_k: int = 50
    keyword_top_k: int = 50
    vector_pool_k: int = 40
    keyword_pool_k: int = 40
    raw_candidate_multiplier: float = 4.0
    raw_candidate_min: int = 20
    vector_weight: float = 0.8
    keyword_weight: float = 0.2
    context_doc_char_limit: int = 2000
    context_total_char_budget: int = 12000
    context_list_total_char_budget: int = 24000
    agent_search_result_count: int = 4
    agent_search_result_char_limit: int = 1200

    # --- Reranker ---
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 7
    # BGE reranker raw-logit threshold. Documents scoring below this are
    # dropped from the context. Calibrated on labelled queries
    # (evaluation/reranker_threshold_calib.py): relevant docs scored >=1.39
    # (p10=2.77), irrelevant median=-2.38; threshold 1.0 keeps 100% recall while
    # ~halving the low-relevance tail. Lower to 0.0 for more recall.
    reranker_score_threshold: float = 0.0
    # Table chunks use a relaxed threshold because cross-encoder typically gives
    # lower raw logits for tabular text. -1.0 keeps clearly relevant tables
    # (scores > -1.0) while dropping irrelevant/wrong-program tables that tend
    # to score below -1.0 (previously -5.0 was too permissive, allowing
    # wrong-program table docs to pollute LLM context).
    reranker_table_score_threshold: float = -1.0
    # Keep at least this many top reranker-scored candidates even when all
    # scores fall below thresholds. This prevents retrieval from returning
    # top0 while preserving score ordering for answer context.
    reranker_min_top_k: int = 3

    # --- Router ---
    router_mode: str = "classifier"

    # --- Evaluation & Fallback ---
    self_eval_enabled: bool = (
        False  # disabled by default — adds ~2-5s per query
    )
    # BGE reranker returns raw logits, not probabilities. Keep this very high
    # to avoid skipping self-eval just because a raw logit is greater than 0.72.
    self_eval_min_top_score: float = 100.0
    # Master switch for Tavily web-search fallback. Actual API calls only happen
    # when this is True AND a trigger condition fires (no_info pattern / no_sources
    # / dynamic_query / freshness_query). Set self_eval_enabled=True as well to
    # additionally use the LLM quality judge as a Tavily trigger.
    tavily_fallback_enabled: bool = False
    tavily_search_depth: str = (
        "basic"  # basic (1 credit) | advanced (2 credits)
    )
    tavily_max_results: int = (
        5  # fetch pool size (filter xuống tavily_web_result_count)
    )
    tavily_web_content_char_limit: int = (
        1500  # per-result content char limit cho web results
    )
    tavily_web_result_count: int = (
        3  # số results giữ lại sau filter (≤ max_results)
    )
    web_fallback_dynamic_collections: List[str] = ["kehoach"]
    # Granular sub-flags that control which conditions trigger Tavily.
    # These also govern LLM response-cache bypass: dynamic/freshness queries
    # bypass the cache even when tavily_fallback_enabled=False, because their
    # answers can go stale regardless of whether web search is enabled.
    web_fallback_on_dynamic: bool = False
    web_fallback_on_no_info: bool = False
    tavily_cache_ttl_seconds: int = 3600
    tavily_cache_maxsize: int = 200

    # --- Offline Evaluation ---
    post_index_eval_enabled: bool = True
    post_index_eval_command: str = ""
    post_index_eval_max_cases: int = 120

    # --- Reflection ---
    # ✅ GEMINI: query rewriting — quality-critical for retrieval accuracy
    reflection_enabled: bool = True
    reflection_provider: str = "gemini"  # gemini | lm_studio | ollama | openai
    reflection_model: str = (
        "gemini-3.1-flash-lite"  # fast flash for rewrite task
    )
    reflection_temperature: float = 0.0  # low temp → more deterministic rewrite
    reflection_max_tokens: int = (
        1024  # increased from 256 to prevent truncation
    )

    # --- Collection-aware Routing (Phase 8) ---
    domain_routing_enabled: bool = True
    domain_confidence_threshold: float = 0.65

    # --- Auto Crawler ---
    crawler_enabled: bool = True
    crawler_schedule_hour: int = 2
    crawler_schedule_minute: int = 0
    crawler_delay: float = 1.0
    crawler_retention_months: int = 12
    crawler_tags: str = "ĐTĐH:%C4%90T%C4%90H"  # comma-sep "Name:encoded,..."

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True  # Master switch for Redis
    redis_max_connections: int = 20
    redis_socket_timeout: float = 5.0
    redis_connect_timeout: float = 5.0
    redis_health_check_interval: int = 30  # seconds between PING on idle conns
    use_redis_session: bool = True  # Phase 1: session migration
    use_redis_cache: bool = True  # Phase 2: LLM response cache
    use_redis_history: bool = True  # Phase 2: conversation history cache

    # --- Rate Limiting ---
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 20  # requests per minute
    rate_limit_rpd: int = 200  # requests per day
    rate_limit_alert_threshold: float = 0.8  # alert at 80% capacity

    # --- Retrieval Improvement Flags (all default OFF for safe rollout) ---
    web_query_enrichment_enabled: bool = (
        False  # A1: academic year + homepage filter
    )
    score_cliff_enabled: bool = False  # B1: per-collection score cliff
    per_collection_norm_enabled: bool = (
        False  # B2: per-collection normalization
    )
    sibling_expansion_enabled: bool = False  # C1: sibling chunk expansion
    parent_context_enabled: bool = True  # C5: parent-child context expansion
    freshness_tavily_check_enabled: bool = False  # C3: date_str freshness check
    low_conf_pool_expand_enabled: bool = (
        False  # C4: 2x candidate pool in Tier 3
    )
    hyde_enabled: bool = True  # HyDE post-rerank fallback
    hyde_min_results: int = 3  # trigger when reranked < N results
    hyde_confidence_threshold: float = 0.3  # trigger when reranker mean < this
    sibling_budget_ratio: float = 0.30  # 30% of total budget for siblings
    sibling_per_doc_limit: int = 800  # Per-sibling char limit
    parent_max_chars: int = 1500  # Max chars from parent content
    parent_max_chars_agent: int = (
        500  # Reduced for agent (tighter token budget)
    )
    context_total_char_budget_with_expansion: int = (
        16000  # Expanded total when siblings
    )

    # --- Admin / Document Upload ---
    superadmin_user_ids: str = ""  # comma-separated MongoDB ObjectIds
    upload_dir: str = "uploads"

    # --- Exam schedule (lịch thi) — structured PDF/Excel ingestion ---
    # Exam schedules are tabular, not prose: they are parsed into a dedicated
    # Mongo collection + ES index and queried with structured filters instead of
    # vector search. See services/exam_schedule_parser.py.
    exam_schedule_es_index: str = "exam_schedules"
    # Exam schedule is a structured DB lookup, not vector retrieval — cap is set
    # high enough to effectively return every matching row for normal queries.
    exam_schedule_search_top_k: int = 500
    # Two-digit years in the "Ngày" column (e.g. "9/5/26") map to 2000 + yy.
    exam_schedule_two_digit_year_pivot: int = 2000
    # strptime formats tried (in order) for the "Ngày" column. "%d/%m/%Y" also
    # parses non-zero-padded values like "9/5/2026"; dotted "dd.mm.yyyy" (e.g.
    # "06.07.2026") appears in some layouts. Keep in sync with
    # utils.vn_datetime._DEFAULT_DATE_FORMATS.
    exam_schedule_date_formats: List[str] = Field(
        default_factory=lambda: [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%Y-%m-%d",
            "%d/%m/%y",
            "%d-%m-%y",
            "%d.%m.%y",
        ]
    )
    # Folded Excel/PDF header → canonical field. Keys are accent-/case-folded via
    # query.signals.fold_vietnamese_text so matching is robust to diacritics. The
    # schedule ships in two column-naming layouts (e.g. "Mã HP"/"Mã học phần",
    # "Tuần thi"/"Tuần", "SL"/"Số lượng"); both are aliased to one field so a
    # single schema serves both. Keep in sync with parser._DEFAULT_COLUMN_MAP.
    exam_schedule_column_map: dict[str, str] = Field(
        default_factory=lambda: {
            "ma lop qt": "mgmt_class_code",
            "ma lop": "mgmt_class_code",
            "ma hp": "subject_code",
            "ma hoc phan": "subject_code",
            "ten hoc phan": "subject_name",
            "ghi chu": "note",
            "nhom": "group",
            "tuan thi": "exam_week",
            "tuan": "exam_week",
            "thu": "weekday",
            "ngay": "exam_date",
            "kip thi": "exam_session",
            "phong thi": "exam_room",
            "sl": "student_count",
            "so luong": "student_count",
            "dot": "exam_batch",
            "ma lop thi": "exam_class_code",
        }
    )
    # Optional "Kíp thi" → display start-time fallback. The PDF banner's legend
    # ("Kíp 1 (7h00) …") is parsed at ingest and takes precedence over this.
    exam_schedule_kip_time_map: dict[str, str] = Field(default_factory=dict)

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
