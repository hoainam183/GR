"""Diagnostic script: trace agent execution for compare_programs query.

Run: .venv/bin/python scratch/diagnose_agent_latency.py
"""
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("diag")

from config.settings import Settings
from agent.react_agent import ReActAgent

settings = Settings()
agent = ReActAgent(settings)

QUERY = (
    "So sánh học phần Hệ điều hành giữa ngành "
    "Công nghệ thông tin Việt - Nhật (IT-E6) "
    "và ngành Công nghệ thông tin (IT-E7)"
)

logger.info("=" * 70)
logger.info("QUERY: %s", QUERY)
logger.info("=" * 70)

t0 = time.perf_counter()
state = agent.run(QUERY, session_id="diag-test")
total = time.perf_counter() - t0

logger.info("=" * 70)
logger.info("RESULT SUMMARY")
logger.info("-" * 70)
logger.info("Total time:      %.2fs", total)
logger.info("Iterations:      %d", state.iteration)
logger.info("Tool history:    %s", state.tool_call_history)
logger.info("Error:           %s", state.error)
logger.info("Final answer:    %s", (state.final_answer or "")[:200])
logger.info("Tool results:    %d entries", len(state.tool_results))
for i, tr in enumerate(state.tool_results):
    logger.info(
        "  [%d] tool=%s args=%s result_len=%d",
        i, tr.tool_name, str(tr.args)[:100], len(tr.result),
    )
logger.info("=" * 70)
