#!/usr/bin/env python3
"""Build the ADK EvalSet for the referee agent from eval/claims.json.

Empty-ledger categories only (A–E): the seeded-ledger asymmetry cases need a
pre-seeded verified ledger, which lives in eval/run_eval.py; the ADK eval set
keeps a single, clean initial state per ADK eval semantics.

Emits:
  eval/referee.test.json  — EvalSet (ADK schema, built via ADK's own pydantic models)
  eval/test_config.json   — criteria: exact tool trajectory + final-response match
"""
import json
import pathlib
import time

from google.adk.evaluation.eval_case import EvalCase, IntermediateData, Invocation
from google.adk.evaluation.eval_set import EvalSet
from google.genai import types

EVAL_DIR = pathlib.Path(__file__).resolve().parent
spec = json.loads((EVAL_DIR / "claims.json").read_text())
cases = [c for c in spec["cases"] if c["ledger"] == "empty"]

eval_cases = []
for c in cases:
    inv = Invocation(
        invocation_id=f"inv-{c['id']}",
        user_content=types.Content(role="user", parts=[types.Part(text=c["claim"])]),
        final_response=types.Content(role="model", parts=[types.Part(text=c["expected"])]),
        intermediate_data=IntermediateData(
            tool_uses=[types.FunctionCall(name="referee_verdict", args={"claim": c["claim"]})]
        ),
        creation_timestamp=time.time(),
    )
    eval_cases.append(EvalCase(
        eval_id=c["id"],
        conversation=[inv],
        creation_timestamp=time.time(),
    ))

es = EvalSet(
    eval_set_id="referee-verdicts",
    name="Sentinel Mesh referee — expected-verdict eval (empty ledger)",
    description=spec["description"],
    eval_cases=eval_cases,
    creation_timestamp=time.time(),
)
(EVAL_DIR / "referee.test.json").write_text(es.model_dump_json(indent=1))
(EVAL_DIR / "test_config.json").write_text(json.dumps(
    {"criteria": {"tool_trajectory_avg_score": 1.0, "response_match_score": 0.8}}, indent=1))
print(f"wrote referee.test.json with {len(eval_cases)} cases + test_config.json")
