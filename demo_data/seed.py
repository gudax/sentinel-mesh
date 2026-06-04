#!/usr/bin/env python3
"""Seed the bundled demo memory — a tiny, fictional, kaia-shaped provenance store.

The control plane reads ADVISORY ground truth from any SQLite exposing the
`memories` table contract (filename / name / body / archive_tier). In production
that is the operator's kaia broker; for the public demo it is this seeded file,
so the recorded run ships with zero real-world data.
"""
import pathlib
import sqlite3

DB = pathlib.Path(__file__).resolve().parent / "demo_memory.db"

ROWS = [
    ("meridian-fye.md", "meridian-corporate-profile",
     "# Meridian Dynamics Ltd (SG) — corporate profile. Financial year end is "
     "31 December; FY2025 statutory audit deadline 2026-09-30. Incorporated 2021. "
     "Sole owner: Dana Park."),
    ("founder-entity-map.md", "founder-entity-map",
     "# Entity map — do NOT conflate. Meridian Dynamics Ltd (owner: Dana Park) and "
     "Atlas Cognition Labs (owner: Jun Seo) are SEPARATE, UNRELATED companies — each "
     "100% owned by its own principal, zero cross-shareholding in any direction, no "
     "family tie. All dealings between them are arm's-length. Never describe them as "
     "related parties or under common ownership."),
    ("refund-policy.md", "ops-refund-policy",
     "# Ops policy — refunds. Any refund above $500 requires human approval. Agent "
     "auto-approval of refunds is prohibited without exception."),
]

if __name__ == "__main__":
    DB.unlink(missing_ok=True)
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE memories (filename TEXT UNIQUE, name TEXT, body TEXT, "
              "archive_tier TEXT NOT NULL DEFAULT 'live')")
    c.executemany("INSERT INTO memories (filename, name, body) VALUES (?,?,?)", ROWS)
    c.commit()
    n = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    print(f"seeded {DB.name}: {n} rows")
