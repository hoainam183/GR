"""
FastAPI Backend for RAG v2 Chatbot

This module re-exports the FastAPI app from the modular ``api`` package
inside RAG_v2 so that the original entry point still works::

    python src/RAG_v2/backend/main.py
    uvicorn src.RAG_v2.backend.main:app --reload
"""

import sys
from pathlib import Path

# Ensure RAG_v2 root (parent of this backend/ folder) is importable
_RAG_V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAG_V2_ROOT))

from api.main import app  # noqa: E402,F401

# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
