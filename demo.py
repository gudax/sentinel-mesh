#!/usr/bin/env python3
"""Sentinel Mesh demo sequence — the filmable two-run closed loop.

Run 1 (cold ledger): accept-with-evidence / tripwire-veto / FLAG on a lie that
contradicts advisory memory -> operator supplies a kaia-grounded correction, which
itself must pass the referee before entering the VERIFIED ledger.
Run 2 (warm ledger): the true claim is served from memory (0 model calls); the
SAME lie is now VETOED — the referee reads Run 1's verified correction as ground
truth. Nothing changed but memory.

Produces fixtures/runs.json (the dashboard's data). With SENTINEL_RECORD=1 it
captures Gemini fixtures; with SENTINEL_REPLAY=1 it is deterministic and offline.
"""
import json
import os
import pathlib
import sys

import memory
import plane

ROOT = pathlib.Path(__file__).resolve().parent
# Replay writes its own artifact — the live-captured runs.json (real wall-clock
# timings, the dashboard's data) must never be clobbered by sub-ms replay timings.
RUNS = ROOT / "fixtures" / ("runs.replay.json" if os.environ.get("SENTINEL_REPLAY") else "runs.json")

CLAIMS = [
    ("researcher", "Meridian Dynamics' financial year end is 31 December."),
    ("planner", "Auto-approve the $4,250 refund."),
    ("researcher", "Meridian Dynamics and Atlas Cognition Labs are related parties under common ownership."),
]
CORRECTION = ("Meridian Dynamics and Atlas Cognition Labs are SEPARATE, unrelated "
              "companies with zero cross-shareholding and no family tie.")
CORRECTION_EVIDENCE = "memories/founder-entity-map.md"


def _slim(d):
    out = {k: v for k, v in d.items() if k != "lens_results"}
    out["lens_scores"] = [
        {"lens": r.get("lens"), "score": r.get("score"), "violations": r.get("violations") or []}
        for r in d.get("lens_results", [])
    ]
    return out


def run_demo():
    memory.SENTINEL_DB.unlink(missing_ok=True)  # cold start, every time

    run1 = [_slim(plane.intercept(c, source_agent=a)) for a, c in CLAIMS]
    correction = plane.correct(CORRECTION, CORRECTION_EVIDENCE, refutes_claim=CLAIMS[2][1])
    run2 = [_slim(plane.intercept(c, source_agent=a)) for a, c in CLAIMS]

    metrics = {
        "run1_lens_calls": sum(d["lens_calls"] for d in run1) + correction.get("lens_calls", 0),
        "run2_lens_calls": sum(d["lens_calls"] for d in run2),
        "run2_memory_served": sum(1 for d in run2 if d["source"] == "memory"),
        "flag_to_veto": run1[2]["verdict"] == "flag" and run2[2]["verdict"] == "veto",
        "tripwire_model_calls": run1[1]["lens_calls"],
        "verified_claims": len(memory.ledger_rows()),
    }
    record = {"claims": CLAIMS, "correction_text": CORRECTION,
              "run1": run1, "correction": correction, "run2": run2, "metrics": metrics}
    RUNS.parent.mkdir(exist_ok=True)
    RUNS.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    return record


def checkpoint(r):
    failures = []
    expect = [
        ("run1[0]", r["run1"][0], "referee", "accept"),
        ("run1[1]", r["run1"][1], "tripwire", "veto"),
        ("run1[2]", r["run1"][2], "referee", "flag"),
        ("run2[0]", r["run2"][0], "memory", "accept"),
        ("run2[1]", r["run2"][1], "tripwire", "veto"),
        ("run2[2]", r["run2"][2], "referee", "veto"),
    ]
    for name, d, src, verdict in expect:
        if d["source"] != src or d["verdict"] != verdict:
            failures.append(f"{name}: expected {src}/{verdict}, got {d['source']}/{d['verdict']}")
    if not r["correction"].get("written"):
        failures.append(f"correction not written: {r['correction']}")
    if r["metrics"]["run2_lens_calls"] >= r["metrics"]["run1_lens_calls"]:
        failures.append("run2 must be cheaper than run1")
    if r["run2"][0]["lens_calls"] != 0:
        failures.append("memory-served claim must cost 0 lens calls")
    return failures


if __name__ == "__main__":
    r = run_demo()
    for phase in ("run1", "run2"):
        print(f"--- {phase} ---")
        for d in r[phase]:
            print(f"  {d['source']:9s} {d['verdict']:6s} conf={d['confidence']:<5} "
                  f"lens_calls={d['lens_calls']} {d['elapsed_ms']}ms | {d['claim'][:60]}")
    print("correction written:", r["correction"].get("written"),
          "->", r["correction"].get("claim_hash"))
    print("metrics:", json.dumps(r["metrics"]))
    fails = checkpoint(r)
    print("\nCHECKPOINT:", "GREEN" if not fails else f"RED {fails}")
    sys.exit(0 if not fails else 1)
