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
import os
import pathlib
import sys

EVAL_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))          # makes `referee_agent` importable
os.chdir(EVAL_DIR)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")

from google.adk.evaluation.agent_evaluator import AgentEvaluator  # noqa: E402


async def main(num_runs):
    await AgentEvaluator.evaluate(
        agent_module="referee_agent",
        eval_dataset_file_path_or_dir=str(EVAL_DIR / "referee.test.json"),
        num_runs=num_runs,
    )
    print("ADK EVAL: GREEN (AgentEvaluator raises on criterion failure)")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
