#!/usr/bin/env python3
"""Sentinel Mesh memory layer — verified-claim ledger + kaia ground-truth reads.

Two stores, deliberately separated:
  - WRITES  -> sentinel.db / `sentinel_verified_claims` (this file owns it). Never
    kaia's temporal_facts: kaia's refreshTemporalGraph rebuilds derived rows and
    would clobber external writes — and kaia.db is a live broker DB we must not touch.
  - READS   -> kaia.db opened read-only (`mode=ro`) via stdlib sqlite3. Advisory
    ground-truth comes from operator-curated `memories` rows (+ `temporal_facts`),
    each carrying a provenance pointer (filename / source_table:source_id).

The snapshot fed to the referee UNIONs both layers:
  [ADVISORY] lines  = kaia rows   -> contradiction scores exactly 3 (FLAG)
  [VERIFIED] lines  = our ledger  -> contradiction scores 1-2     (VETO)
That asymmetry is the closed loop: a Run-1 verified correction upgrades the same
lie from FLAG to VETO on Run 2.
"""
import hashlib
import json
import os
import pathlib
import sqlite3
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
SENTINEL_DB = ROOT / "sentinel.db"
# Advisory ground-truth source: any SQLite exposing the `memories` table contract.
# Production = the operator's kaia broker; the public demo ships a seeded fictional
# store (demo_data/demo_memory.db) selected via SENTINEL_MEMORY_DB.
KAIA_DB = pathlib.Path(
    os.environ.get("SENTINEL_MEMORY_DB", "/Users/kei/projects/kaia-v2/data/kaia.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sentinel_verified_claims (
  claim_hash    TEXT PRIMARY KEY,
  claim_text    TEXT NOT NULL,
  subject       TEXT,
  predicate     TEXT,
  object        TEXT,
  verdict       TEXT NOT NULL,            -- accept | veto | flag (as ruled when written)
  confidence    REAL NOT NULL,
  dissent_json  TEXT,                     -- panel dissent at ruling time
  source_agent  TEXT,                     -- which fleet agent emitted the claim
  evidence_ref  TEXT,                     -- kaia provenance that grounded the ruling
  ruling_ref    TEXT,                     -- prior claim_hash this ruling chains to
  valid_from    TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'current'
);
"""


def claim_hash(text):
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()[:16]


def _conn():
    c = sqlite3.connect(SENTINEL_DB)
    c.row_factory = sqlite3.Row
    c.execute(_SCHEMA)
    return c


def write_verified(claim_text, verdict, confidence, dissent=None, source_agent=None,
                   evidence_ref=None, ruling_ref=None, spo=(None, None, None)):
    h = claim_hash(claim_text)
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO sentinel_verified_claims "
            "(claim_hash, claim_text, subject, predicate, object, verdict, confidence, "
            " dissent_json, source_agent, evidence_ref, ruling_ref, valid_from, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'current')",
            (h, claim_text, spo[0], spo[1], spo[2], verdict, confidence,
             json.dumps(dissent or [], ensure_ascii=False), source_agent,
             evidence_ref, ruling_ref, datetime.now(timezone.utc).isoformat()),
        )
    return h


def lookup_verified(claim_text):
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM sentinel_verified_claims WHERE claim_hash=? AND status='current'",
            (claim_hash(claim_text),),
        ).fetchone()
    return dict(row) if row else None


def trace_chain(h, max_depth=10):
    """Follow ruling_ref links back to the origin ruling — local trace-to-origin."""
    chain = []
    with _conn() as c:
        while h and len(chain) < max_depth:
            row = c.execute(
                "SELECT * FROM sentinel_verified_claims WHERE claim_hash=?", (h,)
            ).fetchone()
            if not row:
                break
            chain.append(dict(row))
            h = row["ruling_ref"]
    return chain


def ledger_rows():
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM sentinel_verified_claims WHERE status='current' "
            "ORDER BY valid_from").fetchall()]


# --- kaia ground-truth (READ-ONLY) -------------------------------------------------
def _kaia():
    return sqlite3.connect(f"file:{KAIA_DB}?mode=ro", uri=True)


def _snippet(body, terms, width=500):
    """Slice the body around the densest cluster of term hits — a head-truncated
    gist can cut off exactly the sentence that matters (live-earned: the entity-
    separation line sat past char 400 and the referee flagged a true correction)."""
    flat = " ".join(body.split())
    low = flat.lower()
    hits = [i for t in terms for i in [low.find(t.lower())] if i >= 0]
    if not hits:
        return flat[:width]
    center = sorted(hits)[len(hits) // 2]
    start = max(0, center - width // 3)
    return ("…" if start else "") + flat[start:start + width]


def kaia_advisory(terms, limit=4):
    """Pull operator-curated memory rows ranked by how many query terms they hit;
    return [ADVISORY] lines with provenance (memories/<filename>). Read-only."""
    rows = {}
    with _kaia() as c:
        for term in terms:
            for fn, name, body in c.execute(
                "SELECT filename, name, body FROM memories "
                "WHERE body LIKE ? AND archive_tier='live'",
                (f"%{term}%",),
            ):
                e = rows.setdefault(fn, {"name": name, "body": body, "hits": 0})
                e["hits"] += 1
    best = sorted(rows.items(), key=lambda kv: -kv[1]["hits"])[:limit]
    return [
        f"- [ADVISORY] (kaia memories/{fn}) {e['name']}: {_snippet(e['body'], terms)}"
        for fn, e in best
    ]


def kaia_cited(filename, terms, width=700):
    """Fetch ONE specific kaia row by filename — the evidence a correction cites —
    and return it as a [CITED-EVIDENCE] line snippeted around the claim terms."""
    with _kaia() as c:
        row = c.execute(
            "SELECT filename, name, body FROM memories WHERE filename=?",
            (filename,),
        ).fetchone()
    if not row:
        return None
    fn, name, body = row
    return f"- [CITED-EVIDENCE] (kaia memories/{fn}) {name}: {_snippet(body, terms, width)}"


def snapshot(terms):
    """The referee's memory_facts: kaia advisory layer + our VERIFIED ledger."""
    lines = kaia_advisory(terms)
    for r in ledger_rows():
        lines.append(
            f"- [VERIFIED] (sentinel ledger {r['claim_hash']}, conf={r['confidence']}, "
            f"grounded on {r['evidence_ref']}) {r['claim_text']}"
        )
    return "\n".join(lines) if lines else "(memory empty)"


# --- STEP 2 checkpoint (runs against the bundled demo memory) -------------------------
if __name__ == "__main__":
    failures = []

    # (a) separate-file isolation: the verified ledger never shares a file with the
    # advisory broker, so the broker's refresh jobs can never clobber rulings.
    if SENTINEL_DB.resolve() == KAIA_DB.resolve():
        failures.append("sentinel.db must not be the advisory memory db")
    # (b) write -> lookup -> chain
    h1 = write_verified("Meridian Dynamics' financial year end is 31 December.",
                        "accept", 1.0, evidence_ref="memories/meridian-fye.md",
                        source_agent="checkpoint")
    h2 = write_verified("Meridian Dynamics and Atlas Cognition Labs are SEPARATE unrelated companies.",
                        "accept", 0.95, evidence_ref="memories/founder-entity-map.md",
                        ruling_ref=h1, source_agent="checkpoint")
    got = lookup_verified("meridian dynamics'  financial year end is 31 december.")  # normalized hash
    if not got or got["claim_hash"] != h1:
        failures.append(f"lookup_verified failed: {got}")
    chain = trace_chain(h2)
    if [r["claim_hash"] for r in chain] != [h2, h1]:
        failures.append(f"trace_chain failed: {[r['claim_hash'] for r in chain]}")

    # (c) advisory read-only ground-truth reads succeed
    fye = kaia_advisory(["Meridian", "financial year"])
    sep = kaia_advisory(["conflate", "unrelated"])
    if not any("31 December" in l for l in fye):
        failures.append(f"advisory FYE read failed: {fye[:1]}")
    if not any("founder-entity-map" in l for l in sep):
        failures.append(f"advisory entity-map read failed: {sep[:1]}")

    # (d) read-only really is read-only
    try:
        with _kaia() as c:
            c.execute("CREATE TABLE _should_fail (x)")
        failures.append("advisory connection allowed a write — mode=ro broken")
    except sqlite3.OperationalError:
        pass

    print(f"ledger: {SENTINEL_DB.name} · advisory: {KAIA_DB} (separate files: OK)")
    print(f"write->lookup->chain: {h2} -> {h1} (OK)" if not failures else "")
    for l in (fye + sep)[:3]:
        print("  ", l[:160])
    snap = snapshot(["Meridian"])
    print(f"snapshot has VERIFIED layer: {'[VERIFIED]' in snap}")
    print("\nCHECKPOINT:", "GREEN" if not failures else f"RED {failures}")
    raise SystemExit(0 if not failures else 1)
