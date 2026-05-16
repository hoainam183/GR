"""Fail-soft post-index evaluation trigger."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def trigger_post_index_eval(
    settings: Any,
    *,
    reason: str,
    document_id: Optional[str] = None,
    collection: Optional[str] = None,
) -> Dict[str, Any]:
    """Start current-policy eval after indexing without blocking indexing.

    This is intentionally best-effort.  Evaluation failures must appear in the
    dashboard, not break document ingestion.
    """
    if not getattr(settings, "post_index_eval_enabled", False):
        return {"status": "disabled"}

    configured = str(getattr(settings, "post_index_eval_command", "") or "").strip()
    if configured:
        cmd = shlex.split(configured)
    else:
        python_bin = Path(sys.executable)
        local_python = PROJECT_ROOT / ".venv" / "bin" / "python"
        if local_python.exists():
            python_bin = local_python
        max_cases = int(getattr(settings, "post_index_eval_max_cases", 120) or 120)
        cmd = [
            str(python_bin),
            "-m",
            "evaluation.two_layer_eval",
            "current",
            "--max-cases",
            str(max_cases),
            "--persist",
            "--trigger",
            reason,
        ]
        if collection:
            cmd.extend(["--trigger-collection", collection])
        if document_id:
            cmd.extend(["--trigger-document-id", document_id])

    env = os.environ.copy()
    existing_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{PROJECT_ROOT}{os.pathsep}{existing_path}"
        if existing_path
        else str(PROJECT_ROOT)
    )
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info("Post-index eval started: pid=%s cmd=%s", proc.pid, " ".join(cmd))
        return {"status": "started", "pid": proc.pid, "cmd": cmd}
    except Exception as exc:
        logger.warning("Failed to start post-index eval: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}
