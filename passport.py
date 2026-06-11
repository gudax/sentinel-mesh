#!/usr/bin/env python3
"""Sentinel Mesh — Trust Passport: portable, tamper-evident verified memory.

A verified-claim ledger is just an SQLite file this process owns (see memory.py).
That makes verification *portable*: a fleet that has paid the Gemini cost to verify
a fact can hand a second fleet a signed export of what survived — and the second
fleet inherits the immunity without re-running the panel.

  export_passport(rows)        -> a dict: issuer + claims + a content digest over
                                  the immunity-bearing fields (NOT valid_from, which
                                  is wall-clock and would break reproducibility).
  verify_passport(passport)    -> recompute the digest; tamper is detectable.
  import_passport(passport)    -> write the claims into THIS fleet's ledger,
                                  preserving claim_hash / verdict / confidence /
                                  evidence_ref / ruling_ref so the imported snapshot
                                  is byte-identical to the issuer's — the closed-loop
                                  asymmetry (advisory FLAG vs verified VETO) transfers
                                  intact, and a re-asked verified claim still hits the
                                  zero-model fast path.

Only ACCEPTed (verified) rows are passportable: a fleet shares what it *trusts*,
never its flags or vetoes. The digest binds the claim text to its verdict, so a
passport that has been edited to upgrade a flag into a verified accept fails
verification before it can poison the importer.
"""
import hashlib
import json

import memory

PASSPORT_VERSION = "1.0"
# Fields that carry immunity — the digest is computed over exactly these, in this
# order, so two fleets agree on a passport's identity regardless of when each row
# was written (valid_from is deliberately excluded: it is wall-clock, not content).
_SIGNED_FIELDS = ("claim_hash", "claim_text", "verdict", "confidence",
                  "evidence_ref", "ruling_ref")


def _canonical(claims):
    norm = [{k: c.get(k) for k in _SIGNED_FIELDS} for c in claims]
    norm.sort(key=lambda c: c["claim_hash"])
    return json.dumps(norm, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(claims):
    return hashlib.sha256(_canonical(claims).encode()).hexdigest()


def export_passport(rows, issuer="sentinel-mesh:fleet"):
    """Serialize ACCEPTed ledger rows into a tamper-evident passport."""
    claims = [
        {k: r.get(k) for k in _SIGNED_FIELDS + ("source_agent",)}
        for r in rows if r.get("verdict") == "accept"
    ]
    return {
        "passport_version": PASSPORT_VERSION,
        "issuer": issuer,
        "claim_count": len(claims),
        "claims": claims,
        "digest": digest(claims),
    }


def verify_passport(passport):
    """True iff the digest still matches the claims (no tamper, no truncation)."""
    return (passport.get("passport_version") == PASSPORT_VERSION
            and passport.get("digest") == digest(passport.get("claims", [])))


def import_passport(passport, into_agent="imported"):
    """Write a verified passport into THIS fleet's ledger (memory.SENTINEL_DB).

    Refuses a passport that fails digest verification — an importer never trusts
    claims whose verdict may have been forged. Returns the list of claim_hashes
    written. Re-importing is idempotent (INSERT OR REPLACE on claim_hash)."""
    if not verify_passport(passport):
        raise ValueError("passport digest mismatch — refusing to import tampered memory")
    written = []
    for c in passport["claims"]:
        h = memory.write_verified(
            c["claim_text"], c["verdict"], c["confidence"],
            source_agent=f"{into_agent}:{passport['issuer']}",
            evidence_ref=c.get("evidence_ref"), ruling_ref=c.get("ruling_ref"))
        written.append(h)
    return written


if __name__ == "__main__":
    # Self-check: round-trip + tamper detection (no Gemini, no network).
    sample = [
        {"claim_hash": "a" * 16, "claim_text": "X is true.", "verdict": "accept",
         "confidence": 0.9, "evidence_ref": "memories/x.md", "ruling_ref": None,
         "source_agent": "checkpoint"},
        {"claim_hash": "b" * 16, "claim_text": "Y is false.", "verdict": "flag",
         "confidence": 0.6, "evidence_ref": None, "ruling_ref": None,
         "source_agent": "checkpoint"},
    ]
    p = export_passport(sample, issuer="sentinel-mesh:selftest")
    fails = []
    if p["claim_count"] != 1:
        fails.append("only ACCEPT rows should be passportable")
    if not verify_passport(p):
        fails.append("freshly exported passport must verify")
    p["claims"][0]["verdict"] = "accept"           # forge an upgrade
    p["claims"][0]["confidence"] = 1.0
    if verify_passport(p):
        fails.append("tampered passport must NOT verify")
    print("passport:", json.dumps({k: v for k, v in p.items() if k != "claims"}))
    print("\nCHECKPOINT:", "GREEN" if not fails else f"RED {fails}")
    raise SystemExit(0 if not fails else 1)
