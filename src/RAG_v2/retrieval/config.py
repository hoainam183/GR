# Retrieval Configuration
#
# HyDE (Hypothetical Document Embedding) — post-rerank fallback settings.
# When initial retrieval returns low-confidence results, HyDE generates a
# hypothetical answer via LLM, embeds it, and runs a second-pass search.
#
# These defaults are mirrored in config/settings.py (Settings class) and
# mapped to the pipeline cfg dict via rag_pipeline._settings_to_cfg().
# To override at runtime, set the corresponding env var or pass via cfg dict.

# ── HyDE Post-Rerank Fallback ────────────────────────────────────────────────

# Master switch — must be True to activate HyDE fallback.
HYDE_ENABLED: bool = False

# Trigger condition 1: activate when fewer than N documents survive reranking.
HYDE_MIN_RESULTS: int = 3

# Trigger condition 2: activate when reranker mean score falls below threshold.
# BGE reranker scores are raw logits; 0.3 is a reasonable low-confidence cutoff.
HYDE_CONFIDENCE_THRESHOLD: float = 0.3
