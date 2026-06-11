# Devpost Submission — Sentinel Mesh

**Track 2 — Optimize (Existing Agents)** · Google for Startups AI Agents Challenge

---

## The numbers first (measured, not asserted)

Same ADK/A2A fleet, same three claims, run twice. Nothing changed but memory:

- A verified claim is re-served at **0 Gemini calls / 0.3 ms** (vs 3 calls / 3.7 s on Run 1) — **~12,000× faster, at zero marginal model cost**.
- The lie that was FLAGGED and corrected on Run 1 is **auto-VETOED on Run 2** — the fleet remembers what survived.
- A hallucinated *"auto-approve the $4,250 refund"* is killed by a deterministic tripwire **before any model can rationalize it** — 0 model calls.
- Fleet-level Gemini spend drops **9 → 3 lens calls** between runs. Reliability and cost improve together, **with zero retraining**.
- The referee itself was examined with **Google's own eval tooling**: a 30-claim eval set × 3 runs — **100% verdict accuracy, 100% run-to-run consistency** (ADK `AgentEvaluator` + a deterministic harness; details below).

**Don't take the recording's word for it — the referee is live on Cloud Run: type your own lie and watch it get stamped.** (Testing-access link on this page.)

## Inspiration

Agent memory is exploding — every fleet now ships a memory layer. But every memory layer we've seen is **gullible**: it stores whatever an agent says. One hallucinated claim, remembered once, contaminates every downstream agent — and when a fleet *shares* memory over A2A, it shares the contamination. The verification side of the industry only ships *observability*: dashboards that watch agents fail after the fact. **Memory is trending; *trusted* memory is missing.**

## What it does

Sentinel Mesh is a control plane that sits **in the message path** of a Google ADK / A2A agent fleet. Every claim a worker emits is intercepted mid-flight:

1. A **3-lens adversarial Gemini panel** (robustness / overreach / hard-rules, in parallel on Vertex AI) scores the claim against **memory as ground truth**.
2. A **deterministic tripwire** independently hard-vetoes money/auth/destructive claims with *no model in the loop*.
3. Accepted claims are **written back** into a provenance-tracked verified ledger — every ruling drills down to the row and source that justified it.

The write-back closes the loop: **the referee guards memory; memory grounds the referee; the fleet compounds truth every run.** The verdict rubric encodes a trust hierarchy — *advisory* memory caps suspicion at FLAG; only *verified* ledger rows justify a VETO; paraphrase is never contradiction.

## Verification is portable — Herd Immunity across fleets

The verified ledger is a file this control plane owns. That makes the most expensive thing a fleet produces — *adjudicated truth* — **portable**. A fleet that has paid the Gemini cost to verify a fact can hand a second fleet a **Trust Passport**: an **HMAC-signed** export (signed over issuer + claim-count + a sha256 digest of the verdict-bearing fields). A passport edited in transit — say, to upgrade a FLAG into a verified ACCEPT — fails signature verification before it can poison the importer, because recomputing the digest is not enough without the issuer's signing key. One fleet earns the immunity; every fleet it signs for inherits it.

We demo it with three fleets and one lie — *"Meridian and Atlas are related parties under common ownership"* (`demo_herd.py`, deterministic offline replay — **zero network calls**):

- **Fleet A** runs the full loop, accepts the operator's entity-separation correction, and exports a 2-claim signed Trust Passport.
- **Fleet B** imports the passport and has **never verified anything itself**. It re-serves the inherited verified fact at **0 Gemini calls / 0.1 ms** (cross-fleet zero-cost reserve) — and still **VETOES a lie it has never seen**. That veto *does* run the panel (3 lens calls); the point is that its verdict rests on the `[VERIFIED]` correction Fleet B never paid to earn — inherited immunity, not a free veto.
- **Fleet C** is the control: it verified the same FYE fact but never received the correction. The **same lie only reaches FLAG** — suspicious, but it passes.

The only difference between a fleet that blocks the lie and one that gets infected by it is **one row in a passport**. That row is the vaccine. This is the unit economics argument made literal: a fleet's *verified set* transfers at zero marginal model cost, and every re-ask of an inherited fact re-serves at zero calls — so the more fleets share, the cheaper trusted memory gets, the opposite of a per-call guardrail that re-pays for the same judgement on every agent, every fleet, forever.

## Business case

**Who pays, and why now.** Every team operating a multi-agent fleet in production hits the same wall: agents act on each other's unverified claims, and one bad memory write silently degrades the whole fleet. Today they buy *observability* (watch it fail) or *guardrails* (block per-action, learn nothing). Sentinel Mesh is the third category — **verified memory as infrastructure**: a sidecar that makes the fleet measurably cheaper and more reliable *every additional run*, with no retraining and no migration (it reads any SQLite advisory store and binds to a standard ADK callback).

**We are our own first customer.** Nexus AI Labs (Seoul) is a revenue-generating AI company; we operate a **production Gemini agent for real users on Apps in Toss — a 30-million-user Korean super-app platform** — and a cross-vendor memory broker that three AI harnesses share daily. Sentinel Mesh is the trust layer **built for that fleet and being wired into it**: the demo's "advisory memory" contract is literally our production broker's schema (the public demo ships a fictional, isomorphic dataset).

**Unit economics.** The memory-first fast path means the marginal cost of a verified claim is zero — the more a fleet runs, the larger the verified set, the fewer Gemini calls per run (measured 9 → 3 in two runs). The cost curve *bends down* with usage; that is the opposite of every per-call guardrail product.

**Path to revenue.** Sidecar pricing per fleet + verified-ledger storage; Cloud Marketplace / Gemini Enterprise packaging is the natural Track-3 follow-on (the control plane is already a single container on Cloud Run).

## We verified the verifier — with Google's own eval tooling

A judge you can't measure is just another opinion. We built a **30-claim eval set** spanning the rubric's load-bearing edges — verbatim accepts, paraphrase accepts ("December 31" vs "31 December"), memory-silent flags, advisory-contradiction flags, verified-contradiction vetoes, tripwire vetoes (EN + KR), and tripwire word-boundary *negatives* ("tokenizes" must not match `\btoken\b`) — and ran it two ways:

- **Google ADK eval** (`EvalSet` + `AgentEvaluator`): the referee exposed as an ADK agent tool, scored on exact tool trajectory + response match. **GREEN.**
- **A deterministic harness** (3 full passes, isolated two-phase ledger): **100% verdict accuracy, 100% consistency, tripwire exactness with zero model calls.**

The eval earned its keep immediately: it caught a real failure mode — a financial *statement* ("revenue grew strongly") was over-vetoed because one lens read a performance *statement* as a money *action* (the tripwire is intentionally multilingual, which is what surfaced the edge case). We tightened the rubric to distinguish the two and re-ran: **96.9% → 100%**. That loop — Google eval tooling finds the flaw, the rubric improves, the numbers prove it — is Track 2's "optimize existing agents" applied to the optimizer itself.

## How we built it — four Google-stack pieces, all load-bearing

1. **ADK agents over real A2A.** Two `LlmAgent` workers via `to_a2a()` with live AgentCards; an orchestrator consumes them through `RemoteA2aAgent`. Real protocol transport, not a mock.
2. **Gemini as the adversarial judge — on Vertex AI.** The 3-lens hostile panel runs `gemini-flash` in parallel, structured-JSON verdicts, temp 0, explicit retry/backoff. Vendored from our production adversarial-decision engine with the model call swapped to Gemini.
3. **Memory as ground truth.** The judge's "constitution" is a live snapshot of an SQLite provenance store — advisory layer (read-only) + verified ledger (its own file, so broker refresh jobs can never clobber rulings).
4. **Veto in the message path.** The referee binds to ADK's non-experimental `before_tool_callback` — returning a dict skips the real tool, so a vetoed claim never lands. (`ExecuteInterceptor` is the production A2A hook; it's still `@a2a_experimental`, so we say so instead of pretending it's free.)

Plus the live layer: **Cloud Run playground** ("try to lie to the referee") running the identical referee with an ephemeral per-session ledger — visitors watch their own accepted claim become ground truth, then watch its contradiction get vetoed.

## Accomplishments we're proud of

- **The loop closes, measurably.** The same lie that cost a 3-call panel and a FLAG on Run 1 is auto-VETOED on Run 2 — and the verified claim re-serves at 0 model calls / 0.3 ms. Every counter on the dashboard is from the recorded run, not a slide.
- **We shipped the eval, not just the agent.** 30 expected-verdict claims × 3 live Vertex runs, 100% accuracy and consistency — and the eval caught a real rubric flaw before any human did (96.9% → 100%).
- **The referee gated its own builders.** Our correction got flagged by our own retrieval bug; fixing the system instead of overriding it is the whole product thesis in one anecdote.
- **A judge can attack it live.** The Cloud Run playground runs the identical referee — type your own lie, watch it get stamped, then watch its contradiction get vetoed.

## Challenges we ran into (the honest list)

- **Dependency truth:** bare `google-adk` does not include A2A; the build is gated behind an import probe so this surfaces at minute 0, not hour 6.
- **The referee flagged our own correction** — head-truncated retrieval cut off exactly the sentence that proved it. Fix: snippet retrieval centered on the densest term cluster + corrections must cite their evidence row. The gate gating us was the system working.
- **Determinism is earned:** Python's per-process hash seed silently reordered retrieval terms and broke fixture replay; total-order sorting fixed it. The film is a deterministic **recorded run**, labeled as such.
- **The eval gated the rubric:** statement-vs-action ambiguity found and fixed by measurement (96.9% → 100%), not intuition.
- **Public-data hygiene:** the recorded demo ships a fictional, isomorphic dataset; in production the advisory layer is our real cross-harness memory broker.

## What's next

`ExecuteInterceptor`-native A2A binding once it stabilizes; near-duplicate claim hashing so paraphrases hit the memory fast path; per-claim trust decay; shadow-mode pilot on our own production gateway; Cloud Marketplace / Gemini Enterprise sidecar packaging (Track 3 follow-on).

---

**Demo video:** https://youtu.be/bZ9pLzWL-hk · **Dashboard:** https://sentinel.k.nexus · **Live playground (Cloud Run):** https://sentinel-playground-675241948019.asia-northeast1.run.app · **Repo:** https://github.com/gudax/sentinel-mesh
*All counters measured, not asserted. The film is a fixture-replayed recorded run; the playground is live.*
