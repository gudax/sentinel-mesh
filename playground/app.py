#!/usr/bin/env python3
"""Sentinel Mesh live playground — "try to lie to the referee".

POST /judge {claim} -> the REAL production referee (deterministic tripwire +
3-lens Gemini panel on Vertex AI) rules on the claim against the bundled demo
memory. Verdict, lens scores and dissent stream back in ~4s.

Honesty + safety properties:
  - demo advisory memory is opened READ-ONLY (same `memories` contract as prod)
  - the verified ledger is EPHEMERAL and per-session (in-memory, capped) — an
    ACCEPT writes back, so a visitor can watch their own claim become ground
    truth and the contradiction of it get VETOED: the closed loop, live
  - per-IP and global rate limits; claim length capped; no data persisted
"""
import collections
import hashlib
import os
import pathlib
import sys
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SENTINEL_MEMORY_DB", str(ROOT / "demo_data" / "demo_memory.db"))

import memory  # noqa: E402
import plane   # noqa: E402
import referee # noqa: E402

from fastapi import FastAPI, Request, Response  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

app = FastAPI(title="Sentinel Mesh Playground", docs_url=None, redoc_url=None)
STATIC = pathlib.Path(__file__).resolve().parent / "static"

MAX_CLAIM = 280
PER_IP_PER_MIN = 8
GLOBAL_PER_MIN = 60
LEDGER_CAP = 12          # verified rows per session
SESSION_TTL = 1800       # 30 min

_ip_hits = collections.defaultdict(list)
_global_hits = []
_sessions = {}           # sid -> {"rows": [...], "ts": epoch}


def _rate_ok(ip):
    now = time.time()
    _ip_hits[ip] = [t for t in _ip_hits[ip] if now - t < 60]
    _global_hits[:] = [t for t in _global_hits if now - t < 60]
    if len(_ip_hits[ip]) >= PER_IP_PER_MIN or len(_global_hits) >= GLOBAL_PER_MIN:
        return False
    _ip_hits[ip].append(now)
    _global_hits.append(now)
    return True


def _session(sid):
    now = time.time()
    for k in [k for k, v in _sessions.items() if now - v["ts"] > SESSION_TTL]:
        del _sessions[k]
    s = _sessions.setdefault(sid, {"rows": [], "ts": now})
    s["ts"] = now
    return s


def _snapshot(terms, rows):
    lines = memory.kaia_advisory(terms)  # read-only demo ground truth
    for r in rows:
        lines.append(
            f"- [VERIFIED] (session ledger {r['hash']}, conf={r['conf']}, "
            f"grounded on referee panel vs memory snapshot) {r['claim']}")
    return "\n".join(lines) if lines else "(memory empty)"


class JudgeIn(BaseModel):
    claim: str = Field(min_length=3, max_length=MAX_CLAIM)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/judge")
def judge(body: JudgeIn, request: Request, response: Response):
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    if not _rate_ok(ip):
        return JSONResponse({"error": "rate limit — try again in a minute"}, status_code=429)

    sid = request.cookies.get("sm_sid") or uuid.uuid4().hex
    response.set_cookie("sm_sid", sid, max_age=SESSION_TTL, httponly=True, samesite="lax")
    sess = _session(sid)

    claim = " ".join(body.claim.split())
    t0 = time.perf_counter()
    snap = _snapshot(plane._terms(claim), sess["rows"])
    out = referee.referee(claim, snap)
    elapsed = round((time.perf_counter() - t0) * 1000)

    written = None
    if out["verdict"] == "accept" and len(sess["rows"]) < LEDGER_CAP:
        h = hashlib.sha256(" ".join(claim.lower().split()).encode()).hexdigest()[:16]
        if not any(r["hash"] == h for r in sess["rows"]):
            sess["rows"].append({"hash": h, "claim": claim, "conf": out["confidence"]})
            written = h

    return {
        "claim": claim,
        "verdict": out["verdict"],
        "confidence": out["confidence"],
        "tripwire": out["tripwire"],
        "lens_scores": [
            {"lens": r.get("lens"), "score": r.get("score"),
             "violations": (r.get("violations") or [])[:2]}
            for r in out["lens_results"]
        ],
        "dissent": out["dissent"][:3],
        "lens_errors": [e.get("error", "")[:160] for e in out["lens_errors"]],
        "lens_calls": out["lens_calls"],
        "elapsed_ms": elapsed,
        "written_to_ledger": written,
        "session_ledger": [{"hash": r["hash"], "claim": r["claim"]} for r in sess["rows"]],
    }


@app.get("/memory")
def memory_view():
    """The demo ground truth the referee judges against — shown so lying is fair."""
    rows = memory.kaia_advisory(["Meridian", "Atlas", "refund", "Dana", "Jun"])
    return {"advisory": rows}
