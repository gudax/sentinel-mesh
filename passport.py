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
import hmac
import json
import os

import memory

PASSPORT_VERSION = "1.1"

# Issuer signing key. A passport is HMAC-SHA256 signed over (issuer + digest), so a
# claim edited in transit fails verification unless the attacker also holds this
# key — recomputing the plain digest is not enough. The public demo ships a fixed
# key; in production each issuer fleet holds its own secret (env override).
_SIGNING_KEY = os.environ.get(
    "SENTINEL_PASSPORT_KEY", "sentinel-mesh:demo-issuer-signing-key:v1").encode()
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


def _sign(issuer, claim_count, dg):
    """HMAC-SHA256 over the binding (issuer, claim_count, digest)."""
    msg = f"{issuer}\x00{claim_count}\x00{dg}".encode()
    return hmac.new(_SIGNING_KEY, msg, hashlib.sha256).hexdigest()


def export_passport(rows, issuer="sentinel-mesh:fleet"):
    """Serialize ACCEPTed ledger rows into a signed passport.

    Only ACCEPT rows are exported (a fleet shares what it trusts). The passport is
    HMAC-signed over issuer + claim_count + digest, so neither the claims, the
    issuer, nor the count can be altered without the signing key."""
    claims = [
        {k: r.get(k) for k in _SIGNED_FIELDS + ("source_agent",)}
        for r in rows if r.get("verdict") == "accept"
    ]
    dg = digest(claims)
    return {
        "passport_version": PASSPORT_VERSION,
        "issuer": issuer,
        "claim_count": len(claims),
        "claims": claims,
        "digest": dg,
        "sig": _sign(issuer, len(claims), dg),
    }


def verify_passport(passport):
    """True iff the passport is intact AND its signature checks out.

    Three gates: version match; digest still matches the claims (no tamper, no
    truncation); and the HMAC signature over (issuer, claim_count, digest) is valid
    — a forged claim set fails here even if its plain digest was recomputed, and
    every claim must be an ACCEPT (a fleet never ships a flag/veto as trusted)."""
    if passport.get("passport_version") != PASSPORT_VERSION:
        return False
    claims = passport.get("claims", [])
    if any(c.get("verdict") != "accept" for c in claims):
        return False
    dg = digest(claims)
    if passport.get("digest") != dg:
        return False
    if passport.get("claim_count") != len(claims):
        return False
    expected = _sign(passport.get("issuer"), len(claims), dg)
    return hmac.compare_digest(passport.get("sig", ""), expected)


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
    # forge the claim AND recompute the digest — a digest-only scheme would accept
    # this; HMAC must still reject it because the signature needs the issuer key.
    forged = export_passport(sample, issuer="sentinel-mesh:selftest")
    forged["claims"][0]["claim_text"] = "X is FALSE."     # flip the verified claim
    forged["digest"] = digest(forged["claims"])           # attacker recomputes digest
    if verify_passport(forged):
        fails.append("digest-recomputed forgery must fail the HMAC signature")
    # a flag/veto smuggled in as a trusted claim must be rejected
    sneak = export_passport(sample, issuer="sentinel-mesh:selftest")
    sneak["claims"].append({"claim_hash": "c" * 16, "claim_text": "Z.",
                            "verdict": "flag", "confidence": 0.5,
                            "evidence_ref": None, "ruling_ref": None})
    if verify_passport(sneak):
        fails.append("a non-accept claim must never verify as trusted")
    print("passport:", json.dumps({k: v for k, v in p.items() if k != "claims"}))
    print("\nCHECKPOINT:", "GREEN" if not fails else f"RED {fails}")
    raise SystemExit(0 if not fails else 1)
