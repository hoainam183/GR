"""Root conftest.py — adds the RAG_v2 project root to sys.path.

This ensures that top-level packages (agent, api, schemas, config, …)
are importable from any test file without requiring a full install.
"""

from __future__ import annotations

import sys
from pathlib import Path

# RAG_v2 root is the directory containing this conftest.py.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
