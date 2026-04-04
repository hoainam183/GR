"""
Pre-download tất cả local ML models về HuggingFace cache.
Chạy script này MỘT LẦN trên server trước khi khởi động backend.

Usage:
    python scripts/download_models.py
"""

from __future__ import annotations

import sys

print("=" * 60)
print("Pre-downloading all local ML models")
print("This only needs to run once per machine.")
print("=" * 60)

# ── 1. E5 Multilingual ────────────────────────────────────────
print("\n[1/3] Downloading intfloat/multilingual-e5-large (~1.1 GB)...")
try:
    from sentence_transformers import SentenceTransformer

    SentenceTransformer("intfloat/multilingual-e5-large")
    print("      ✓ E5 multilingual ready")
except Exception as e:
    print(f"      ✗ Failed: {e}")
    sys.exit(1)

# ── 2. BGE-M3 ────────────────────────────────────────────────
print("\n[2/3] Downloading BAAI/bge-m3 (~2.3 GB)...")
try:
    from FlagEmbedding import BGEM3FlagModel

    BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
    print("      ✓ BGE-M3 ready")
except Exception as e:
    print(f"      ✗ Failed: {e}")
    sys.exit(1)

# ── 3. BGE Reranker ──────────────────────────────────────────
print("\n[3/3] Downloading BAAI/bge-reranker-v2-m3 (~1.1 GB)...")
try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-m3")
    AutoModelForSequenceClassification.from_pretrained(
        "BAAI/bge-reranker-v2-m3"
    )
    print("      ✓ BGE Reranker ready")
except Exception as e:
    print(f"      ✗ Failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("All models downloaded successfully!")
print("You can now start the backend without internet access.")
print("=" * 60)
