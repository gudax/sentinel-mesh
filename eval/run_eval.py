#!/usr/bin/env python3
"""Sentinel Mesh referee eval harness — deterministic scorer over eval/claims.json.

Runs the REAL referee (tripwire + 3-lens Gemini panel) against the bundled demo
memory, with an ISOLATED eval ledger (never the repo's sentinel.db), in two
phases: empty-ledger cases first, then the seeded-ledger cases — so the
advisory-vs-verified asymmetry (FLAG vs VETO on the same kind of contradiction)
is measured, not asserted.

Outputs:
  eval/results.json    — full per-case, per-run record
  dashboard/eval.json  — summary the dashboard panel renders

Honors SENTINEL_REPLAY / SENTINEL_RECORD (fixtures) and SENTINEL_VERTEX exactly
like referee.py, so the published numbers are reproducible offline:
  SENTINEL_REPLAY=1 python eval/run_eval.py --runs 3
"""
import argparse
import concurrent.futures
import json
import os
import pathlib
import sys
import time
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Demo memory must be selected BEFORE memory.py is imported (KAIA_DB binds at import).
os.environ.setdefault("SENTINEL_MEMORY_DB", str(ROOT / "demo_data" / "demo_memory.db"))

import memory  # noqa: E402
import plane   # noqa: E402
import referee # noqa: E402

EVAL_DIR = pathlib.Path(__file__).resolve().parent
LEDGER = EVAL_DIR / ".eval_ledger.db"  # isolated — repo sentinel.db is never touched
VERDICTS = ("accept", "flag", "veto")


def _reset_ledger():
    LEDGER.unlink(missing_ok=True)
    memory.SENTINEL_DB = LEDGER  # module-global lookup happens at call time


def _seed_ledger(seeds):
    for s in seeds:
        memory.write_verified(s["claim"], "accept", s["confidence"],
                              source_agent="eval-seed", evidence_ref=s["evidence_ref"])


def _judge(case):
    t0 = time.perf_counter()
    snap = memory.snapshot(plane._terms(case["claim"]))
    out = referee.referee(case["claim"], snap)
    return {
        "id": case["id"], "category": case["category"], "claim": case["claim"],
        "expected": case["expected"], "got": out["verdict"],
        "ok": out["verdict"] == case["expected"],
        "tripwire": bool(out["tripwire"]), "lens_calls": out["lens_calls"],
        "confidence": out["confidence"], "dissent": out["dissent"][:3],
        "lens_errors": out["lens_errors"],
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def run_once(cases, seeds, workers):
    """One full pass: phase 1 = empty ledger, phase 2 = seeded ledger."""
    records = []
    for phase, ledger_state in (("empty", "empty"), ("seeded", "seeded")):
        batch = [c for c in cases if c["ledger"] == ledger_state]
        if not batch:
            continue
        _reset_ledger()
        if ledger_state == "seeded":
            _seed_ledger(seeds)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            records += list(ex.map(_judge, batch))
    return records


def metrics(records):
    n = len(records)
    acc = sum(r["ok"] for r in records) / n
    confusion = defaultdict(Counter)
    for r in records:
        confusion[r["expected"]][r["got"]] += 1
    per_class = {}
    for v in VERDICTS:
        tp = confusion[v][v]
        fn = sum(confusion[v][g] for g in VERDICTS if g != v)
        fp = sum(confusion[e][v] for e in VERDICTS if e != v)
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        per_class[v] = {
            "precision": round(prec, 3) if prec is not None else None,
            "recall": round(rec, 3) if rec is not None else None,
            "support": tp + fn,
        }
    by_cat = {}
    for r in records:
        c = by_cat.setdefault(r["category"], {"n": 0, "ok": 0})
        c["n"] += 1
        c["ok"] += r["ok"]
    trip = [r for r in records if r["category"] == "veto_tripwire"]
    tripwire_exact = all(r["tripwire"] and r["lens_calls"] == 0 and r["ok"] for r in trip)
    # tripwire word-boundary negatives: panel (not tripwire) must have judged these
    trip_neg = [r for r in records if r["id"] in ("C4", "C5")]
    return {
        "n_cases": n, "accuracy": round(acc, 4),
        "confusion": {e: dict(confusion[e]) for e in confusion},
        "per_class": per_class,
        "by_category": {k: {"n": v["n"], "ok": v["ok"], "acc": round(v["ok"] / v["n"], 3)}
                        for k, v in sorted(by_cat.items())},
        "tripwire_exact": tripwire_exact,
        "tripwire_negatives_ok": all(r["ok"] for r in trip_neg),
        "total_lens_calls": sum(r["lens_calls"] for r in records),
        "mean_panel_ms": round(
            sum(r["elapsed_ms"] for r in records if r["lens_calls"]) /
            max(1, sum(1 for r in records if r["lens_calls"])), 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3, help="repeat passes (consistency)")
    ap.add_argument("--workers", type=int, default=3, help="concurrent cases per pass")
    ap.add_argument("--min-accuracy", type=float, default=0.85)
    args = ap.parse_args()

    spec = json.loads((EVAL_DIR / "claims.json").read_text())
    cases, seeds = spec["cases"], spec["ledger_seeds"]

    runs = []
    for i in range(args.runs):
        t0 = time.perf_counter()
        records = run_once(cases, seeds, args.workers)
        m = metrics(records)
        m["wall_s"] = round(time.perf_counter() - t0, 1)
        runs.append({"run": i + 1, "metrics": m, "records": records})
        print(f"run {i + 1}/{args.runs}: accuracy={m['accuracy']:.2%} "
              f"lens_calls={m['total_lens_calls']} wall={m['wall_s']}s")
        for r in records:
            if not r["ok"]:
                print(f"   MISS {r['id']} expected={r['expected']} got={r['got']} | {r['claim'][:80]}")

    # consistency: fraction of cases whose verdict is identical across all runs
    by_id = defaultdict(list)
    for run in runs:
        for r in run["records"]:
            by_id[r["id"]].append(r["got"])
    consistent = sum(1 for v in by_id.values() if len(set(v)) == 1)
    consistency = round(consistent / len(by_id), 4)
    mean_acc = round(sum(r["metrics"]["accuracy"] for r in runs) / len(runs), 4)

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": ("replay" if os.environ.get("SENTINEL_REPLAY")
                 else "vertex" if os.environ.get("SENTINEL_VERTEX") else "api-key"),
        "model": referee.GEMINI_MODEL,
        "n_cases": len(cases), "n_runs": args.runs,
        "mean_accuracy": mean_acc, "consistency": consistency,
        "per_run_accuracy": [r["metrics"]["accuracy"] for r in runs],
        "per_class": runs[-1]["metrics"]["per_class"],
        "by_category": runs[-1]["metrics"]["by_category"],
        "tripwire_exact": all(r["metrics"]["tripwire_exact"] for r in runs),
        "tripwire_negatives_ok": all(r["metrics"]["tripwire_negatives_ok"] for r in runs),
        "mean_panel_ms": runs[-1]["metrics"]["mean_panel_ms"],
    }
    (EVAL_DIR / "results.json").write_text(
        json.dumps({"summary": summary, "runs": runs}, ensure_ascii=False, indent=1))
    (ROOT / "dashboard" / "eval.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1))
    LEDGER.unlink(missing_ok=True)

    print(f"\nmean accuracy {mean_acc:.2%} over {args.runs} runs · "
          f"consistency {consistency:.2%} · tripwire_exact={summary['tripwire_exact']}")
    green = mean_acc >= args.min_accuracy and summary["tripwire_exact"]
    print("CHECKPOINT:", "GREEN" if green else "RED")
    return 0 if green else 1


if __name__ == "__main__":
    raise SystemExit(main())
