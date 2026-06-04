# Devpost Submission — Sentinel Mesh

**Track 2 — Optimize (Existing Agents)** · Google for Startups AI Agents Challenge

---

## Inspiration

Agent memory is exploding — every fleet now ships a memory layer. But every memory
layer we've seen is **gullible**: it stores whatever an agent says. One hallucinated
claim, remembered once, contaminates every downstream agent forever — and when a
fleet *shares* memory, it shares the contamination. Meanwhile the verification side
of the industry only ships *observability*: dashboards that watch agents fail in
production, after the fact.

We've been building multi-agent orchestration since before the current wave (our
production stack runs an adversarial decision engine and a cross-vendor SQLite
memory broker that three different AI harnesses share daily). The hype skipped the
hard problem both halves create together: **memory is trending; *trusted* memory is
missing.**

## What it does

Sentinel Mesh is a control plane that sits **in the message path** of a Google
ADK / A2A agent fleet. Every claim a worker emits is intercepted mid-flight:

1. A **3-lens adversarial Gemini panel** (robustness / overreach / hard-rules, run
   in parallel) scores the claim against **memory as ground truth**.
2. A **deterministic tripwire** independently hard-vetoes money/auth/destructive
   claims with *no model in the loop* — a hallucinated "auto-approve the refund"
   is dropped before any LLM can rationalize it.
3. Accepted claims are **written back** into a provenance-tracked verified ledger —
   every ruling drills down to the row and source that justified it.

That write-back closes the loop: **the referee guards memory; memory grounds the
referee; the fleet compounds truth every run.** In our recorded demo, the same
fleet runs the same three claims twice. Run 2: the true claim is served from
verified memory at **0 Gemini calls / 0.5 ms** (vs 3 calls / 3.7 s), and the lie
that was FLAGGED and corrected on Run 1 is now **VETOED** — the referee cites both
the original advisory fact *and* the Run-1 verified correction. Nothing changed
but memory.

## How we built it — Business impact + Technical spotlight

**Business impact.** Three outcomes a startup CFO understands:
- **Fewer false-accepts reach production** — the money/auth tripwire is
  LLM-independent; in the demo it blocks an auto-refund claim before any model runs.
- **Cost falls every run** — verified claims are never re-judged. Measured: Run 1 =
  9 Gemini lens calls, Run 2 = 3; memory-served claims cost 0.
- **Compounding reliability with zero retraining** — fleet accuracy becomes a
  function of accumulated verified memory, not model weights. It improves the
  moment you run it again.

**Technical spotlight — four Google-stack pieces, all load-bearing:**
1. **ADK agents over real A2A.** Two `LlmAgent` workers exposed via `to_a2a()` with
   live AgentCards (`/.well-known/agent-card.json`); an orchestrator consumes them
   through `RemoteA2aAgent`. Real protocol transport, not a mock.
2. **Gemini as the adversarial judge — on Vertex AI.** The 3-lens hostile panel runs
   `gemini-flash` in parallel with structured-JSON outputs and explicit retry/backoff.
   We lifted the judge core from our production adversarial-decision engine and
   swapped its model call to Gemini: the referee itself is Google-stack.
3. **Memory as ground truth.** The judge's "constitution" is a live snapshot of an
   SQLite provenance store. The verdict rubric encodes the trust hierarchy:
   *advisory* memory caps suspicion at FLAG; only *verified* ledger rows justify a
   VETO. Unverified memory can make you suspicious; only verified memory can make
   you certain.
4. **Veto in the message path.** The referee binds to ADK's non-experimental
   `before_tool_callback` — returning a dict skips the real tool, so a vetoed claim
   never lands. (`ExecuteInterceptor.after_event` is the production A2A hook; it is
   still `@a2a_experimental`, so we say so instead of pretending it's free.)

## Challenges we ran into (the honest list)

- **Dependency truth:** bare `google-adk` does not include A2A (`No module named
  'a2a'`); the build is gated behind a 30-minute import probe so this surfaces at
  minute 0, not hour 6.
- **The referee flagged our own correction.** Our first correction ("the companies
  are separate") was *rejected by our own panel* because head-truncated retrieval
  cut off exactly the sentence that proved it. Fix: snippet retrieval centered on
  the densest term cluster + corrections must cite their evidence row, which is
  injected verbatim. The gate gating us was the system working.
- **Determinism is earned:** Python's per-process hash seed silently reordered
  retrieval terms and broke fixture replay; total-order sorting fixed it. The film
  is a deterministic **recorded run** across hash seeds, labeled as such.
- **Durable external memory:** verified claims live in their own SQLite file, never
  inside the broker's derived tables — refresh jobs can't clobber rulings.
- **Public-data hygiene:** the recorded demo ships a fictional, isomorphic dataset;
  in production the advisory layer is our real cross-harness memory broker.

## What's next

`ExecuteInterceptor`-native A2A binding once it stabilizes; near-duplicate claim
hashing so paraphrases hit the memory fast path; per-claim trust decay; packaging
as a sidecar for Gemini Enterprise / Cloud Marketplace (Track 3 follow-on).

---

**Demo video:** https://youtu.be/MKovySTtX_g · **Dashboard:** https://sentinel.k.nexus · **Repo:** https://github.com/gudax/sentinel-mesh
*All demo counters are measured, not asserted. The film is a fixture-replayed
recorded run.*
