#!/usr/bin/env python3
"""Run the ADK AgentEvaluator over the referee agent's EvalSet.

Usage (from repo root):
  SENTINEL_VERTEX=1 GOOGLE_CLOUD_PROJECT=<proj> GOOGLE_GENAI_USE_VERTEXAI=1 \
    .venv/bin/python eval/run_adk_eval.py [num_runs]

This is Google's own eval machinery (EvalSet -> AgentEvaluator) scoring:
  - tool_trajectory_avg_score == 1.0 : the agent must route every claim through
    referee_verdict verbatim (no skipped or paraphrased tool calls)
  - response_match_score >= 0.8     : the final answer must be the verdict word
"""
import asyncio
import datetime
import json
import os
import pathlib
import sys

EVAL_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))          # makes `referee_agent` importable
os.chdir(EVAL_DIR)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")

from google.adk.evaluation.agent_evaluator import AgentEvaluator  # noqa: E402

ARTIFACT = EVAL_DIR / "adk_results.json"  # committed proof, not just a stdout line


async def main(num_runs):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    try:
        await AgentEvaluator.evaluate(
            agent_module="referee_agent",
            eval_dataset_file_path_or_dir=str(EVAL_DIR / "referee.test.json"),
            num_runs=num_runs,
        )
        status = "GREEN"
    except Exception as e:  # noqa: BLE001 — record the failure, then re-raise
        ARTIFACT.write_text(json.dumps({
            "status": "RED", "error": f"{type(e).__name__}: {e}",
            "num_runs": num_runs, "started_at": started,
        }, indent=1))
        raise
    ARTIFACT.write_text(json.dumps({
        "status": status,
        "harness": "google.adk.evaluation.AgentEvaluator",
        "eval_set": "referee.test.json",
        "criteria": {"tool_trajectory_avg_score": 1.0, "response_match_score": 0.8},
        "num_runs": num_runs,
        "started_at": started,
        "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "note": "AgentEvaluator raises on criterion failure; GREEN = no raise.",
    }, indent=1))
    print(f"ADK EVAL: {status} (artifact: {ARTIFACT})")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
