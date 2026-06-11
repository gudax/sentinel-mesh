# Sentinel Mesh

**A verified-memory control plane for Google ADK / A2A agent fleets.**

> Verify in the message path. Remember what survives. Get smarter every run.

**Demo film:** [youtu.be/qM20NV_Q2oU](https://youtu.be/qM20NV_Q2oU) ·
**Working papers:** [sentinel.k.nexus](https://sentinel.k.nexus) ·
**Live playground:** [try to lie to the referee](https://sentinel-playground-675241948019.asia-northeast1.run.app) ·
**Architecture:** [dashboard/architecture.svg](dashboard/architecture.svg)

Agent fleets are getting good at *talking* to each other over A2A — and bad at
*trusting* what they say. Sentinel Mesh sits in the message path: every claim a
worker agent emits is judged by a 3-lens adversarial **Gemini** panel against
**memory as ground truth**; a deterministic tripwire independently hard-vetoes
money/auth/destructive claims with **no model in the loop**. Accepted claims are
written back into a provenance-tracked verified ledger — so the next run reads
strictly cleaner memory.

**The closed loop:** the referee guards memory; memory grounds the referee; the
fleet compounds truth every run. A claim FLAGGED and corrected on Run 1 is
auto-VETOED on Run 2; a claim already verified is served from memory with **zero
Gemini calls**.

**Herd Immunity:** the verified ledger is a file this plane owns — so immunity is
*portable*. A fleet exports a tamper-evident **Trust Passport** of what it verified;
a second fleet imports it and **vetoes a lie it has never seen** (the inherited
`[VERIFIED]` row is now its ground truth) while re-serving the verified fact at
**0 Gemini calls**. A control fleet without the passport only FLAGs the same lie —
it passes. One fleet earns the immunity; every fleet inherits it, at zero marginal
model cost. See `demo_herd.py` (`passport.py` for the export/verify/import).

```
 Worker A (ADK/A2A :8001) ──┐                       ┌─ 3-lens Gemini referee
 Worker B (ADK/A2A :8002) ──┤→ before_tool_callback ┤  (robust·overreach·nevers)
 Orchestrator (RemoteA2aAgent) ─┘   intercept()     └─ + deterministic tripwire
                       │                                   │
                advisory memory (read-only)         verified ledger (write-back)
                       └────────── run N+1 reads cleaner memory ──────────┘
```

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install 'google-adk[a2a]' mcp google-genai uvicorn   # NOT bare google-adk
python probe.py                                          # env truth gate

python demo_data/seed.py                                  # fictional demo memory
export SENTINEL_MEMORY_DB=$PWD/demo_data/demo_memory.db

# the closed loop, end to end (referee + ledger + two-run demo)
SENTINEL_REPLAY=1 python demo.py                          # deterministic, offline

# Herd Immunity — verification crosses fleet boundaries (Trust Passport)
SENTINEL_REPLAY=1 python demo_herd.py                     # 3 fleets, 1 lie, 0 new Gemini calls
# or live:  SENTINEL_VERTEX=1 GOOGLE_CLOUD_PROJECT=<proj> \
#           GOOGLE_APPLICATION_CREDENTIALS=<sa.json> SENTINEL_RECORD=1 python demo.py

# real A2A fleet
python fleet/serve_worker.py researcher 8001 &
python fleet/serve_worker.py planner 8002 &
curl localhost:8001/.well-known/agent-card.json           # live AgentCard
python fleet/orchestrator.py                              # delegation + veto seam

# dashboard
cp fixtures/runs.json dashboard/runs.json
python -m http.server 8090 -d dashboard

# examine the examiner — referee eval (30 claims, accept/flag/veto + edges)
SENTINEL_REPLAY=1 python eval/run_eval.py --runs 3        # offline, deterministic
# ADK eval (Google's own framework): tool trajectory + response match
pip install 'google-adk[eval]'
SENTINEL_VERTEX=1 GOOGLE_CLOUD_PROJECT=<proj> GOOGLE_GENAI_USE_VERTEXAI=1 \
  python eval/run_adk_eval.py

# live playground — try to lie to the referee (FastAPI; deployed on Cloud Run)
pip install fastapi && uvicorn playground.app:app --port 8080
```

**Try it live:** the playground runs the real referee on Cloud Run —
type your own claim, watch the tripwire and the three lenses rule on it,
then contradict your own verified claim and watch the closed loop veto it.
Linked from the dashboard at [sentinel.k.nexus](https://sentinel.k.nexus).

## Components

| File | Role |
|---|---|
| `referee.py` | 3-lens adversarial Gemini panel (parallel) + deterministic tripwire. Verdicts: any lens ≤2 or tripwire → **veto** · min ==3 → **flag** · all ≥4 → **accept**. |
| `memory.py` | Verified-claim ledger (`sentinel.db`, its own file — broker refresh jobs can never clobber rulings) + read-only advisory ground-truth reads from any SQLite with a `memories` table. |
| `plane.py` | The closed-loop seam: memory-first `intercept()` (verified claims cost 0 model calls) + gated `correct()` (even corrections must pass the referee). |
| `demo.py` | The filmable two-run sequence with honest, measured counters. |
| `passport.py` | **Trust Passport**: export verified ledger rows as a tamper-evident bundle (sha256 over verdict-bearing fields), `verify_passport()`, and `import_passport()` into another fleet's ledger — verification made portable. |
| `demo_herd.py` | **Herd Immunity** demo: Fleet A exports a passport; Fleet B inherits it and vetoes an unseen lie at 0 re-judging cost; control Fleet C (no passport) only FLAGs the same lie. Deterministic, offline, zero new Gemini calls. |
| `fleet/` | Real ADK agents over the A2A protocol (`to_a2a`, `RemoteA2aAgent`) with the sentinel bound to the non-experimental `before_tool_callback`. |
| `eval/` | The referee examined: a 30-claim expected-verdict set (paraphrase, advisory-contradiction, verified-contradiction, tripwire word-boundary edges) scored by a deterministic harness **and** Google ADK eval (`EvalSet` + `AgentEvaluator`). Live Vertex result: **100% verdict accuracy × 3 runs, 100% consistency** — after the eval itself caught a rubric ambiguity (96.9% → fix → 100%). |
| `playground/` | "Try to lie to the referee" — FastAPI service on Cloud Run running the real referee against read-only demo memory + an ephemeral per-session verified ledger. Rate-limited; nothing persisted. |
| `dashboard/` | Working papers: RUN 1 \| verified ledger \| RUN 2 diff panel + independent-examination (eval) panel + playground link. |

## The rubric (the part that matters)

- **[ADVISORY] memory** (curated, unadjudicated): agreement supports a claim;
  contradiction caps at score 3 — *suspicion, never a hard veto*.
- **[VERIFIED] ledger** (survived the panel): contradiction scores 1–2 — veto.
- **Paraphrase is never contradiction** ("December 31" vs "31 December").
- **Money/auth/destructive claims**: deterministic regex tripwire, vetoed before
  any model can rationalize them.

Unverified memory can make you suspicious. Only verified memory can make you certain.

## Honest engineering notes

- `pip install google-adk` does **not** pull A2A — you need `google-adk[a2a]` + `mcp`.
- ADK's `ExecuteInterceptor` is `@a2a_experimental` and can't be passed through
  `to_a2a()`; we bind to the non-experimental `before_tool_callback` and name the
  interceptor as the production A2A hook.
- The demo film is a **recorded run** (fixture replay, hash-seed-stable) — never
  narrated as live. All counters are measured, not asserted.
- In production this control plane reads its advisory layer from our operator's
  SQLite memory broker (kaia); the public demo ships a fictional, isomorphic
  seeded store (`demo_data/`).

## License

MIT — see [LICENSE](LICENSE).
