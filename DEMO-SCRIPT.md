# Demo Film Kit — Sentinel Mesh (2:45 target, hard cap 3:00)

Everything is deterministic (`SENTINEL_REPLAY=1`). Film in one take, English VO.
Label as a **recorded run** — never "live".

## Pre-flight (run once before recording)

```bash
cd /Users/kei/projects/sentinel-mesh && source .venv/bin/activate 2>/dev/null || true
export SENTINEL_MEMORY_DB=$PWD/demo_data/demo_memory.db
python -m http.server 8090 -d dashboard &        # dashboard at localhost:8090
# fleet shots (optional, STEP-7 addendum) — any Gemini API key (AI Studio path):
export SENTINEL_GEMINI_KEY=<your-gemini-api-key>
export GOOGLE_API_KEY=$SENTINEL_GEMINI_KEY
unset GOOGLE_GENAI_USE_VERTEXAI SENTINEL_VERTEX
./.venv/bin/python fleet/serve_worker.py researcher 8001 &
./.venv/bin/python fleet/serve_worker.py planner 8002 &
```

## Shot list

**SHOT 1 — Title (0:00–0:12).** Dashboard hero (localhost:8090). VO:
> "Sentinel Mesh — a verified-memory control plane for A2A agent fleets. Agent
> memory is everywhere now. But every memory layer ships gullible: it stores
> whatever an agent says. We put a referee in the message path."

**SHOT 2 — Real Google stack (0:12–0:35).** Terminal: boot both workers, then
`curl localhost:8001/.well-known/agent-card.json | head -20` showing the live
AgentCard. VO:
> "Three real Google ADK agents, talking over the A2A protocol — live agent cards.
> A three-lens adversarial Gemini panel sits in the message path, grounded in a
> provenance memory store."

**SHOT 3 — Run 1, cold memory (0:35–1:25).** Terminal: `SENTINEL_REPLAY=1 python
demo.py` — point at run 1 lines, then dashboard RUN 1 column. Beats:
- Claim 1 ACCEPT → drills to the advisory source row, written back as VERIFIED.
- Claim 2 "$4,250 refund" → RED veto. VO: *"No LLM in this decision. A
  deterministic gate on money and auth — vetoed before any model could
  rationalize it."*
- Claim 3 (the lie: "related parties") → AMBER FLAG, all three lenses score 3.
  VO: *"It contradicts advisory memory — but advisory memory is unverified, so
  the panel refuses to kill it. Suspicion, not certainty. The operator supplies a
  correction — and even the correction must pass the referee before it enters the
  ledger."* Show the ledger spine: 0 → 2 verified claims.

**SHOT 4 — Run 2, the reveal (1:25–2:15).** Dashboard RUN 2 column. Beats:
- Claim 1: `via memory` badge — VO: *"Already verified — served from the ledger.
  Zero Gemini calls, half a millisecond."*
- Claim 3: now RED VETO — VO: *"Same agents. Same lie. The only thing that
  changed is memory: the referee now reads run one's verified correction as
  ground truth. Flag became veto. The fleet got more reliable — and cheaper —
  with zero retraining."*
- Metrics strip close-up: lens calls 9 → 3, verified 0 → 2, FLAG → VETO.

**SHOT 5 — A2A seam addendum (2:15–2:35).** Terminal: `python
fleet/orchestrator.py` output — turn 1 recorded via A2A, turn 2 vetoed before the
tool fired. VO:
> "And it binds to real Google A2A — the referee hooks ADK's before-tool callback,
> so a vetoed claim never even lands."

**SHOT 6 — Close (2:35–2:50).** Dashboard full frame. VO:
> "Unverified memory can make you suspicious. Only verified memory can make you
> certain. Sentinel Mesh — verify in the message path, remember what survives,
> get smarter every run."
End card: repo URL + hosted dashboard URL + "recorded run, measured counters".

## Upload
YouTube (unlisted is fine for judging) → paste URL into Devpost.
