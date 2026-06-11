#!/usr/bin/env python3
"""Sentinel Mesh — Herd Immunity demo: verification crosses fleet boundaries.

The two-run demo (demo.py) shows a single fleet getting smarter every run. This
shows the next thing: that immunity is *portable*. One fleet pays the Gemini cost
to verify a fact; a signed Trust Passport hands that immunity to a second fleet
that never ran the panel — and a control fleet without the passport gets infected
by the very same lie.

Three fleets, one lie ("Meridian and Atlas are related parties under common
ownership"):

  FLEET A  — full closed loop. Verifies the FYE fact AND accepts the operator's
             entity-separation correction. Exports a Trust Passport.
  FLEET B  — fresh ledger, imports A's passport, runs the panel on the lie ONCE.
             It has never verified anything itself, yet it VETOES the lie (the
             imported [VERIFIED] correction is ground truth) — and re-asking the
             verified fact costs 0 Gemini calls (cross-fleet zero-cost reserve).
  FLEET C  — control. Knows the FYE fact but never received the correction. The
             SAME lie only reaches FLAG: suspicious, but it passes. No immunity.

The only difference between B and C is one row in a passport. That row is the
vaccine. Fully deterministic under SENTINEL_REPLAY (reuses fixtures/calls.json) —
no network, no key, no new Gemini calls.

  SENTINEL_REPLAY=1 python3 demo_herd.py          # offline, GREEN
"""
import json
import os
import pathlib
import sys

import memory
import plane
import passport
from demo import CLAIMS, CORRECTION, CORRECTION_EVIDENCE

ROOT = pathlib.Path(__file__).resolve().parent
HERD = ROOT / "fixtures" / "herd.json"
HERD_DASH = ROOT / "dashboard" / "herd.json"   # the dashboard panel's data
FYE = CLAIMS[0][1]          # "Meridian Dynamics' financial year end is 31 December."
LIE = CLAIMS[2][1]          # "...related parties under common ownership."

_DBS = {
    "A": ROOT / "fixtures" / ".herd_fleet_a.db",
    "B": ROOT / "fixtures" / ".herd_fleet_b.db",
    "C": ROOT / "fixtures" / ".herd_fleet_c.db",
}


def _use_ledger(name):
    """Point the memory module at a named fleet's ledger (isolated from sentinel.db)."""
    memory.SENTINEL_DB = _DBS[name]
    _DBS[name].unlink(missing_ok=True)


def _slim(d):
    return {"source": d["source"], "verdict": d["verdict"], "confidence": d["confidence"],
            "lens_calls": d["lens_calls"], "elapsed_ms": d["elapsed_ms"],
            "provenance": d.get("provenance", {})}


def build_fleet_a():
    """Full closed loop: verify the FYE fact, accept the entity-separation correction."""
    _use_ledger("A")
    for agent, claim in CLAIMS:
        plane.intercept(claim, source_agent=agent)          # FYE accepted; refund vetoed; lie flagged
    plane.correct(CORRECTION, CORRECTION_EVIDENCE, refutes_claim=LIE)  # correction -> VERIFIED
    return memory.ledger_rows()


def run():
    # --- FLEET A: earn the immunity, export the passport -----------------------
    rows_a = build_fleet_a()
    ppt = passport.export_passport(rows_a, issuer="sentinel-mesh:fleet-A")
    assert passport.verify_passport(ppt), "fleet-A passport must verify"

    # --- FLEET B: inherit the passport, never verify anything itself ------------
    _use_ledger("B")
    imported = passport.import_passport(ppt, into_agent="fleet-B")
    b_reserve = _slim(plane.intercept(FYE, source_agent="fleet-B"))   # re-ask a verified fact
    b_lie = _slim(plane.intercept(LIE, source_agent="fleet-B"))       # attack with an unseen lie

    # --- FLEET C: control — knows the FYE fact, never got the correction -------
    _use_ledger("C")
    plane.intercept(FYE, source_agent="fleet-C")            # verify only the FYE fact (no correction)
    c_lie = _slim(plane.intercept(LIE, source_agent="fleet-C"))

    record = {
        "lie": LIE,
        "verified_fact": FYE,
        "passport": {"issuer": ppt["issuer"], "claim_count": ppt["claim_count"],
                     "digest": ppt["digest"],
                     "claims": [{"claim_text": c["claim_text"], "verdict": c["verdict"],
                                 "confidence": c["confidence"]} for c in ppt["claims"]]},
        "fleet_b": {"imported_hashes": imported,
                    "reserve_verified_fact": b_reserve,   # expect 0 lens calls, memory source
                    "veto_unseen_lie": b_lie},            # expect veto, panel actually ran
        "fleet_c": {"flag_same_lie": c_lie},              # expect flag — no immunity
        "headline": {
            "cross_fleet_reserve_lens_calls": b_reserve["lens_calls"],
            "b_verdict_on_unseen_lie": b_lie["verdict"],
            "c_verdict_on_same_lie": c_lie["verdict"],
            "immunity_transferred": b_lie["verdict"] == "veto" and c_lie["verdict"] == "flag",
        },
    }
    HERD.parent.mkdir(exist_ok=True)
    blob = json.dumps(record, ensure_ascii=False, indent=1)
    HERD.write_text(blob)
    if HERD_DASH.parent.exists():
        HERD_DASH.write_text(blob)
    for db in _DBS.values():
        db.unlink(missing_ok=True)                          # leave no scratch ledgers behind
    return record


def checkpoint(r):
    fails = []
    b = r["fleet_b"]
    if b["reserve_verified_fact"]["lens_calls"] != 0:
        fails.append("Fleet B re-asking a verified fact must cost 0 Gemini calls (cross-fleet fast path)")
    if b["reserve_verified_fact"]["source"] != "memory":
        fails.append("Fleet B verified-fact reserve must be served from imported memory")
    if b["veto_unseen_lie"]["verdict"] != "veto":
        fails.append(f"Fleet B must VETO the unseen lie, got {b['veto_unseen_lie']['verdict']}")
    if b["veto_unseen_lie"]["lens_calls"] <= 0:
        fails.append("Fleet B's veto must come from an actual panel run on a never-seen claim")
    if r["fleet_c"]["flag_same_lie"]["verdict"] != "flag":
        fails.append(f"Fleet C (no passport) must only FLAG the same lie, got {r['fleet_c']['flag_same_lie']['verdict']}")
    if not r["headline"]["immunity_transferred"]:
        fails.append("immunity_transferred must be True (B veto, C flag)")
    return fails


if __name__ == "__main__":
    r = run()
    p = r["passport"]
    print(f"FLEET A → Trust Passport  issuer={p['issuer']}  claims={p['claim_count']}  "
          f"digest={p['digest'][:12]}…")
    for c in p["claims"]:
        print(f"           • [{c['verdict']}] conf={c['confidence']} {c['claim_text'][:64]}")
    b, c = r["fleet_b"], r["fleet_c"]
    print(f"\nFLEET B (imported passport, never ran the loop):")
    print(f"  re-ask verified fact  → {b['reserve_verified_fact']['source']:7s} "
          f"{b['reserve_verified_fact']['verdict']:6s} "
          f"lens_calls={b['reserve_verified_fact']['lens_calls']} "
          f"{b['reserve_verified_fact']['elapsed_ms']}ms   (cross-fleet zero-cost reserve)")
    print(f"  attack: unseen lie    → {b['veto_unseen_lie']['source']:7s} "
          f"{b['veto_unseen_lie']['verdict']:6s} "
          f"lens_calls={b['veto_unseen_lie']['lens_calls']}   (inherited immunity)")
    print(f"\nFLEET C (control, no passport):")
    print(f"  attack: SAME lie      → {c['flag_same_lie']['source']:7s} "
          f"{c['flag_same_lie']['verdict']:6s} "
          f"lens_calls={c['flag_same_lie']['lens_calls']}   (no immunity — it passes as a FLAG)")
    print(f"\nimmunity transferred across fleets: {r['headline']['immunity_transferred']}")
    fails = checkpoint(r)
    print("\nCHECKPOINT:", "GREEN" if not fails else f"RED {fails}")
    sys.exit(0 if not fails else 1)
