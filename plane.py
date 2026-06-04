#!/usr/bin/env python3
"""Sentinel Mesh control plane — the closed-loop seam.

ONE function, intercept(claim), wires the loop:
  1. memory-first: a current VERIFIED ruling on this exact claim is served from the
     ledger — zero model calls (the honest cost win).
  2. otherwise the referee runs (deterministic tripwire, then the 3-lens Gemini
     panel grounded in ADVISORY kaia facts + VERIFIED ledger claims).
  3. an ACCEPT writes the claim back as VERIFIED — so the next run reads strictly
     cleaner memory. FLAG/VETO never enter the ledger; corrections do, via correct().

Every decision carries measured wall-clock + lens-call counters: the demo metrics
are recorded, not asserted.
"""
import json
import sys
import time

import memory
import referee


_STOP = {"the", "and", "that", "this", "with", "from", "are", "was", "were", "has",
         "have", "its", "their", "under", "into", "for", "not", "all", "any"}


def _terms(claim, extra=None):
    """Snapshot search terms: capitalized entity tokens first (root-cause fix for
    short entity names that a length filter drops), then the longest words."""
    toks = [w.strip(".,!?'\"()").removesuffix("'s") for w in claim.split()]
    toks = [w for w in toks if len(w) >= 3 and w.lower() not in _STOP]
    entities = [w for w in toks if w[0].isupper() and not w.isupper() or w.isupper()]
    # total order (-len, alpha): set iteration order is hash-seed-random per process,
    # and a len-only sort leaves ties in that random order — which changed the
    # snapshot text between processes and broke fixture replay (live-earned).
    longest = sorted({w.lower() for w in toks}, key=lambda w: (-len(w), w))
    out, seen = [], set()
    for w in (extra or []) + entities + longest:
        if w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out[:6]


def intercept(claim, source_agent="fleet", terms=None):
    t0 = time.perf_counter()
    prior = memory.lookup_verified(claim)
    if prior:  # fast path — already verified, no model in the loop
        return {
            "claim": claim, "source": "memory", "verdict": prior["verdict"],
            "confidence": prior["confidence"], "lens_calls": 0,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "dissent": json.loads(prior["dissent_json"] or "[]"),
            "provenance": {"claim_hash": prior["claim_hash"],
                           "evidence_ref": prior["evidence_ref"],
                           "chain": [r["claim_hash"] for r in memory.trace_chain(prior["claim_hash"])]},
        }
    snap = memory.snapshot(terms or _terms(claim))
    ruling = referee.referee(claim, snap)
    decision = {
        "claim": claim,
        "source": "tripwire" if ruling["tripwire"] else "referee",
        "verdict": ruling["verdict"], "confidence": ruling["confidence"],
        "lens_calls": ruling["lens_calls"],
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "dissent": ruling["dissent"], "lens_results": ruling["lens_results"],
        "provenance": {"grounded_on_snapshot": snap.count("- ["),
                       "verified_in_snapshot": snap.count("[VERIFIED]")},
    }
    if ruling["verdict"] == "accept":  # the write-back that closes the loop
        h = memory.write_verified(
            claim, "accept", ruling["confidence"], dissent=ruling["dissent"],
            source_agent=source_agent, evidence_ref="referee panel vs memory snapshot")
        decision["provenance"]["claim_hash"] = h
    return decision


def correct(correction_text, evidence_ref, refutes_claim=None, source_agent="operator"):
    """Operator/orchestrator supplies a memory-grounded correction; the referee must
    still accept it before it becomes VERIFIED — even corrections pass the gate.
    The cited evidence row is injected into the snapshot VERBATIM: a correction
    that names its source gets judged against that source, not against whatever
    the retrieval happened to surface."""
    terms = _terms(correction_text, extra=["unrelated", "separate"])
    snap = memory.snapshot(terms)
    for prefix in ("kaia memories/", "memories/"):
        if evidence_ref.startswith(prefix):
            cited = memory.kaia_cited(evidence_ref.removeprefix(prefix), terms)
            if cited:
                snap = cited + "\n" + snap
            break
    ruling = referee.referee(correction_text, snap)
    if ruling["verdict"] != "accept":
        return {"written": False, "verdict": ruling["verdict"], "dissent": ruling["dissent"]}
    ref = memory.claim_hash(refutes_claim) if refutes_claim else None
    h = memory.write_verified(
        correction_text, "accept", ruling["confidence"], dissent=ruling["dissent"],
        source_agent=source_agent, evidence_ref=evidence_ref, ruling_ref=ref)
    return {"written": True, "claim_hash": h, "verdict": "accept",
            "confidence": ruling["confidence"], "lens_calls": ruling["lens_calls"],
            "evidence_ref": evidence_ref}


if __name__ == "__main__":
    claim = sys.argv[1] if len(sys.argv) > 1 else "Meridian Dynamics' financial year end is 31 December."
    d = intercept(claim)
    d.pop("lens_results", None)
    print(json.dumps(d, ensure_ascii=False, indent=2))
