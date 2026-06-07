#!/usr/bin/env python3
"""ADK agent wrapper around the Sentinel Mesh referee — the evaluable surface.

`adk eval` / AgentEvaluator evaluate ADK agents, not bare functions, so the
referee is exposed as the single tool of a minimal LlmAgent. The eval then
exercises the REAL production path (term extraction -> memory snapshot ->
tripwire -> 3-lens panel) and ADK's own metrics score it:
  - tool_trajectory_avg_score: the agent must call referee_verdict(claim) verbatim
  - response_match_score:      the final answer must be the verdict word
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SENTINEL_MEMORY_DB", str(ROOT / "demo_data" / "demo_memory.db"))

import memory  # noqa: E402
import plane   # noqa: E402
import referee # noqa: E402

# Isolated, EMPTY ledger — the ADK eval set covers the empty-ledger categories;
# the seeded-ledger asymmetry cases live in eval/run_eval.py.
memory.SENTINEL_DB = ROOT / "eval" / ".adk_eval_ledger.db"
memory.SENTINEL_DB.unlink(missing_ok=True)

from google.adk.agents import LlmAgent          # noqa: E402
from google.adk.models.google_llm import Gemini # noqa: E402
from google.genai import types                  # noqa: E402


def referee_verdict(claim: str) -> dict:
    """Verify one claim through the Sentinel Mesh control-plane referee.

    Returns the ruling: verdict is one of accept | flag | veto.
    """
    snap = memory.snapshot(plane._terms(claim))
    out = referee.referee(claim, snap)
    return {
        "verdict": out["verdict"],
        "confidence": out["confidence"],
        "tripwire": bool(out["tripwire"]),
        "dissent": out["dissent"][:2],
    }


root_agent = LlmAgent(
    name="sentinel_referee_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=5, initial_delay=2.0, max_delay=30.0),
    ),
    description="Verifies fleet claims through the Sentinel Mesh referee.",
    instruction=(
        "You are the Sentinel Mesh verification front. For EVERY user message, "
        "call referee_verdict with the user's claim text VERBATIM as the `claim` "
        "argument. Then respond with EXACTLY the verdict word the tool returned: "
        "accept, flag, or veto. Lowercase, one word, no punctuation, nothing else."
    ),
    generate_content_config=types.GenerateContentConfig(temperature=0.0),
    tools=[referee_verdict],
)
