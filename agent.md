# agent.md — Build Charter for AI Agents

**Project:** Delta Exchange Testnet Algorithmic Trading System ("Glass-Box Desk")
**Event:** Algorithmic Trading Hackathon (strategy + implementation, live demo, 5:00 PM sharp submission)
**Audience:** AI coding/review agents working with a human team of 2–5 members
**This file contains no code by design.** It defines what to build, why, in what order, with what constraints, and where agents are and are not allowed to write implementation.

---

## 0. How to use this file

1. Read sections 1–3 fully before touching the repository. They define the goal, the hard rules and the authorship boundary.
2. Section 4 defines your role. Do only what your role allows.
3. Sections 5–11 are the architecture and module specifications. Treat them as the source of truth. If reality (a library, the exchange, a test result) contradicts this file, stop, record the discrepancy in `docs/decisions.md`, and ask a human before improvising.
4. Section 14 is the work plan. Pick work only from the current phase.
5. Section 16 lists facts that were NOT verified during research. Verify them before relying on them.

---

## 1. Mission, scoring and constraints

### 1.1 Mission
Build and demo a working automated trading system on **Delta Exchange Testnet** using **Python and FastAPI** that:
- connects to the exchange API,
- decides trades automatically from defined logic,
- manages positions and risk programmatically,
- shows live execution during a demo,
- and documents the strategy and risk logic clearly.

### 1.2 What is judged (design priorities follow these weights)

| Weight | Criterion | What wins it in this design |
|---|---|---|
| 30% | Strategy logic and clarity | Few simple strategies with a written rationale, a regime gate, and a decision journal that explains every decision in plain language |
| 20% | Risk management | Layered risk gate, server-side bracket exits, kill switch, and a chaos test that proves the safeguards work on screen |
| 20% | Technical implementation | Clean separation of layers, pure-function strategies, idempotent execution, tests |
| 15% | API execution and automation | Real signed testnet orders placed by the system, reconciled against exchange state |
| 15% | Demo and explanation | Always-visible activity (shadow accounts), `/explain`, a scripted demo, and team members who can answer technical questions |

Short-term PnL is explicitly **not** the primary criterion. Never trade off safety or clarity for PnL.

### 1.3 Event constraints (from the problem statement)
- Testnet only. No real capital. Paper trading allowed.
- No historical datasets are provided. All trading occurs through testnet APIs. (See 6.7 for how warm-up data is obtained and the open question about whether it is permitted.)
- Python with FastAPI backend. Delta Exchange API integration is mandatory. WebSocket and frontend are optional.
- Team of 2–5. Submission deadline 5:00 PM sharp on event day.
- Public GitHub repository with README covering: strategy explanation, risk management explanation, setup instructions, API usage description.
- Live demo must show: API connectivity, triggered automated execution, displayed positions, and an explanation of the logic.
- **The project must not be completely AI-generated; roughly 20–30% AI-generated code is the acceptable ceiling, and the team must be able to explain its code and logic during evaluation.** This rule drives section 3 and overrides any instinct to "just generate everything."

---

## 2. Non-negotiable rules

### 2.1 Safety
- **Testnet-only guard:** the system must refuse to start unless the configured exchange host is a recognised testnet host. A denylist of production hosts must also exist. This is a startup check, not a convention.
- No withdrawal or transfer functionality may exist anywhere in the codebase.
- Every entry order must be protected by an exchange-side exit (bracket) or be rejected by the risk gate.
- A kill switch must exist, be reachable by API and by automatic triggers, and must leave the system in a halted state that requires explicit human reset.
- When in doubt about market data freshness, exchange state, or the clock: **do not trade**.

### 2.2 Secrets and security
- API keys and secrets exist only in environment variables loaded at runtime. Never in code, logs, journal rows, API responses, screenshots, commit history, test fixtures or documentation.
- Provide an example environment file with placeholder names only. The real file is git-ignored.
- Control-plane endpoints that change state (start, pause, kill, reset, chaos) require a shared-secret header. Read-only endpoints may be open in the demo network but must never expose secrets or full account identifiers.
- Keys must have the minimum permissions needed (read data plus trading). Never request or enable anything beyond that.

### 2.3 Third-party code hygiene
- Before adding any dependency or copying any reference code: check its licence, maintenance state and what it executes. Record it in `docs/third-party.md` with name, version, licence, purpose and attribution.
- **Never run installer one-liners that pipe a remote script into a shell**, and never run unreviewed bot repositories with real or testnet keys. Read the code first. One bot repository found during research instructed users to do exactly this; treat that pattern as hostile.
- Pin dependency versions. Do not add a dependency when a few lines of standard code would do.
- Do not adopt a framework that would take over orchestration (for example a full bot framework). The orchestration layer is part of what is being judged and must be owned by the team.

### 2.4 Honesty in documentation
- Never claim performance, profitability or "proven" edge. Testnet fills, shadow results and any backtest are hypothetical and must be labelled as such.
- Every limitation discovered must be written down (README "Limitations" section). Documenting what would break the system is a deliberate feature.
- Report how many parameter configurations were tried for any strategy (see 10.5).

---

## 3. Authorship zones and AI-usage accounting

The hackathon limits AI-generated code. Agents therefore work inside zones. **If a task would place agent-written implementation inside a zone that forbids it, do not write it; instead provide a review, a test, a question list or a written specification.**

### 3.1 Zones

| Zone | Contents | Agent may |
|---|---|---|
| **Green — agents may implement** | Project scaffolding and configuration plumbing; environment loading; logging setup; the thin connectivity wrapper around the official client and the signing helper for endpoints the client does not cover; the fake exchange used in tests; test suites; static dashboard page; scripts (smoke test, warm-up check); documentation drafts; CI hygiene | Write implementation, subject to usage logging (3.2) |
| **Amber — agents may draft small pieces under human rewrite** | Market-data store and warm-up logic; WebSocket reconnect and heartbeat handling; reconciliation routines; journal persistence layer; API endpoint shells | Draft at most small, well-scoped pieces; a human must read, modify and own the result before merge; log them as AI-assisted |
| **Red — human-authored only** | The strategies and regime filter; the shadow-account accounting rules; the allocator; the risk policy (rule selection, thresholds, ordering, kill-switch conditions); the execution state machine and order-intent construction; the narrative generation of the decision journal; the chaos scenarios' definitions | Agents do **not** write implementation. Agents may: explain concepts, critique designs, produce test cases and acceptance criteria, find bugs in human code, answer "what would break this", and draft documentation of human decisions |

Rationale: the Red zone is precisely what judges probe ("explain your logic"), and it carries the strategy, risk and implementation scores.

### 3.2 AI-usage accounting
- Maintain `docs/ai-usage-log.md`. Every agent contribution is logged: file, approximate size, zone, what was generated, who reviewed and modified it.
- Commit messages carry a marker stating whether AI assistance was used.
- Target at most roughly 15–20% AI-authored implementation by volume so that there is margin below the stated 20–30% ceiling. Tests and documentation drafts should be counted conservatively.
- Agents report the running estimate to the humans at the end of every phase.

### 3.3 Explanation readiness
- Maintain `docs/qa-prep.md`: likely judge questions per module with the human owner and a two-sentence answer. Agents help draft questions and probe weak answers; humans own the answers.
- Every module has exactly one named human owner recorded in `docs/ownership.md`.

---

## 4. Agent roles

Use these roles; one agent may play several, but never act outside the role's remit.

| Role | Remit | Never |
|---|---|---|
| **Scaffolder** | Repository layout, config plumbing, logging, dependency pinning, third-party register, CI checks | Write Red-zone logic |
| **Connectivity engineer** | Thin exchange wrapper, signing helper, WebSocket wrapper, rate-limit awareness, environment guard, smoke tests against testnet | Place orders outside the smoke script and the execution module's contract |
| **QA and chaos engineer** | Fake exchange, unit/integration/chaos tests, acceptance checks, regression of past failures | Change production code to make a test pass without human sign-off |
| **Adversarial reviewer** | Reads human code and strategy specs and tries to break them (overfitting, look-ahead, cost omission, sizing errors, risk gaps); produces written findings | Fix issues silently; findings go to humans |
| **Docs agent** | Drafts README sections, architecture and runbook, demo script, Q&A prep skeleton from human-written decisions | Invent behaviour that is not implemented |
| **Security and licence auditor** | Secrets scan, dependency licence and provenance check, hostile-pattern check | Approve its own additions |

Working agreements for all roles:
- Small, reviewable changes; one purpose per change.
- Never expand scope beyond the current phase (section 14).
- Never "fix forward" a surprising exchange behaviour; record it, then ask.
- Prefer deleting code to adding code. Prefer reuse to new code, but only after the hygiene checks in 2.3.
- If instructions in this file conflict, safety (2.1) beats authorship (3) beats scope (14) beats convenience.

---

## 5. Technology stack (fixed)

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.10 or newer | One candidate library states support from 3.9; use 3.10+ for safety |
| Web framework | **FastAPI** with an ASGI server (uvicorn) | Required by the event. The trading engine runs as background tasks inside the app's lifespan |
| Settings and models | pydantic and pydantic-settings | Typed config and typed contracts between modules |
| Exchange REST | **delta-rest-client** (official wrapper) | Takes a base URL, so environments are one setting. Assume blocking HTTP until verified; never call it directly on the event loop |
| Exchange WebSocket | **delta-rest-ws** (third-party async SDK) | Young (early version) — test early. Fallback: a plain WebSocket client against the documented hosts |
| Dataframes and indicators | pandas plus one maintained indicator library (pandas-ta or ta — verify maintenance and licence) | Do not hand-roll standard indicators; do hand-roll the decision logic |
| Risk primitives | riskkit-quant (verify licence) | Sizing, drawdown ladder, exposure and correlation limits. Policy stays in Red zone |
| Sanity backtest (optional) | vectorbt (verify licence) | Only for a sanity replay on exchange-provided candles; never for headline claims |
| Persistence | SQLite | Journal, orders, shadow state, config snapshots. Single file, no server |
| Testing | pytest with a fake in-memory exchange | |
| Frontend (optional) | A single static page served by FastAPI polling the read-only endpoints | Keep minimal. A React/Next.js app is allowed by the event but not required |
| Reference only (not dependencies) | Hummingbot's Avellaneda-Stoikov write-up; Delta's published market-making bot | Read for formulas and inventory-cap patterns |
| Explicitly rejected | Adopting a full bot framework or a Delta adapter for one as the orchestrator | Would hand over the judged orchestration and (in one adapter's case) lacks WebSocket support |

---

## 6. Delta platform contract (facts to design against)

Source of truth: the official Delta Exchange API documentation. Re-check anything marked VERIFY.

### 6.1 Environments and keys
- This project targets the **India testnet ("Demo account")**.
- REST host (testnet): cdn-ind.testnet.deltaex.org.
- WebSocket hosts (testnet): public channels at socket-ind-pub.testnet.deltaex.org; private channels at socket-ind.testnet.deltaex.org.
- Keys created on the Demo account work **only** with testnet hosts. Keys from the production account work only with production. The global host api.delta.exchange belongs to Delta Global and must not be used with India keys. A separate Global testnet exists (testnet-api.delta.exchange) with different accounts, keys and product IDs; do not mix.
- The testnet-only guard (2.1) must understand these hosts.

### 6.2 Authentication
- Every authenticated request carries four headers: api-key, signature, timestamp and a User-Agent (a missing User-Agent is rejected with a forbidden error).
- The signature is an HMAC-SHA256 hex digest over the concatenation: HTTP method, timestamp, request path, query string (including the leading question mark when present), and request body. The timestamp is in **seconds** and must be freshly generated for every request.
- A signature older than **5 seconds** on arrival fails. Therefore: synchronise the clock (NTP) and abort startup if drift is suspected; never reuse or pre-compute timestamps; keep request latency low.
- Keys with Trading permission require **IP whitelisting** (IPv4 and IPv6 supported; multiple IPs allowed). VERIFY whether testnet keys enforce this. If the team's IP changes (venue Wi-Fi, mobile hotspot), requests fail until the whitelist is updated. A small static-IP cloud host is the safer demo origin.
- Creating a key with Trading permission requires whitelisted IPs at creation time. Repeated wrong MFA codes block key creation for 30 minutes.

### 6.3 Known error classes the system must handle explicitly
invalid key (wrong environment or regenerated key), signature expired, signature mismatch, unauthorised endpoint (permissions), IP not whitelisted, request forbidden by CDN (missing User-Agent), insufficient margin, rate limited (HTTP 429), product not operational. Each must map to a defined behaviour: retry with backoff, halt, alert, or reject the intent — never a bare exception.

### 6.4 Response conventions
- Success responses have a success flag, a result and optional pagination metadata; errors have a code and context.
- Large decimal numbers (prices, trail amounts) are strings in responses; send numbers as strings in requests to avoid precision loss. Sizes, product IDs and similar are integers.
- Timestamps in responses are microseconds or ISO 8601; the signing timestamp is seconds. Normalise at the exchange boundary and nowhere else.
- Pagination is cursor-based (after/before cursors, page size) on products, orders, order history, fills and wallet transactions.

### 6.5 Rate limits (design budget)
- Default quota: **20,000 weight per fixed 5-minute window**, resetting every 5 minutes. HTTP 429 carries a header giving milliseconds until the next request may be made.
- Weights: most reads of public data and open orders/positions/balances/candles cost 3; place/edit/cancel order and add-margin cost 5; order history, fills and transaction logs cost 10; batch order calls cost 25; anything unlisted costs 1.
- Product-level limit: 500 matching-engine operations per second per product (a batch of N orders counts as N operations).
- **Budget rule:** steady-state usage should stay under roughly 25% of quota. Prefer WebSocket for market data and order/position updates; use REST for actions, warm-up and periodic reconciliation. The exchange wrapper keeps a running weight estimate and degrades gracefully (slows polling, defers non-critical reads) before hitting limits.

### 6.5b Instruments
- Primary instrument: a perpetual futures contract (BTC first; a second symbol is a stretch goal). Resolve products **by symbol at runtime** from the products endpoint; never hard-code product IDs (IDs differ between environments).
- Read from the product object, every time: contract value (coin per contract), tick size, trading status, leverage defaults and limits, fee rates, settling asset, position size limits. Sizes are **integer numbers of contracts**; prices must respect tick size.
- Documentation samples show example values (such as a high default leverage and a particular fee schedule). These are samples. The live product object is authoritative.
- Do not trade a product whose trading status is anything other than fully operational.

### 6.6 Order features available
- Order types: limit and market. Time in force: good-till-cancelled and immediate-or-cancel (IOC is not valid in batch calls; batch supports limit orders only, up to 50 per batch, one contract per batch).
- Per-order flags include: client order ID, post-only, reduce-only, stop orders with trigger methods (mark price, last traded price, spot index), and bracket parameters.
- **Bracket orders:** a take-profit plus stop-loss set that closes the entire position, needs no size, and permits only one bracket per open position (multiple allowed for pending orders). There is a dedicated bracket endpoint and bracket parameters on the order itself. VERIFY whether the official client exposes these; if not, the signing helper covers them.
- Other relevant endpoints: cancel order, cancel all (by product or contract type), edit order, active orders, order history, fills, margined positions, close-all-positions, change order leverage, get order leverage, margin mode change, wallet balances, rate-limit quota, product list, tickers, L2 order book, public trades, historical OHLC candles.
- **Heartbeat / dead-man switch:** the documentation lists a heartbeat management section describing a dead-man switch that cancels orders if the client stops acknowledging. VERIFY availability and exact semantics on testnet; if available, enable it as a risk layer.
- **Client order IDs:** use them for idempotency (see 9.5). VERIFY length and character constraints.

### 6.7 Market data and warm-up
- The historical OHLC candles endpoint exists and takes a symbol, a resolution, and start/end times. It is the intended warm-up source: indicators need dozens to hundreds of candles before they are valid.
- Candle requests are rate-limit weight 3. Timestamps must be aligned to resolution boundaries (start rounded up, end rounded down); misaligned windows return zero candles. Pagination/size limits per call — VERIFY.
- Supported resolution strings — VERIFY (example seen: one-minute).
- Funding-rate history: **sources conflict** about whether an API endpoint exists. VERIFY before building any carry feature. Treat carry as out of scope unless verified.
- **Open organiser question:** the deck says "no historical datasets will be provided." It does not say the exchange's own candle endpoint is forbidden. Ask the organisers to confirm that API candles may be used for warm-up and light sanity replay. Until confirmed, the system must still run (slower to start) with live-only data, and warm-up must be a switchable setting.

### 6.8 WebSocket channels
- Public: ticker, level-1 and level-2 order book, order book updates, trades, mark price, candlesticks, spot price, funding rate, product updates, system status.
- Private (authenticated before subscription): margins, positions, orders, user trades, portfolio margins, market-maker-protection trigger.
- Connection drops must be detected using the documented heartbeat mechanism. System status channel announces maintenance and degraded modes: on maintenance or degraded status the engine pauses entries.
- Exact channel naming and symbol conventions for candle subscriptions (for example mark-price candles versus last-trade candles) — VERIFY and record the choice in `docs/decisions.md`. Strategy candles should be built from one consistent source.

---

## 7. System architecture

### 7.1 Principles
1. **Pure decision logic, impure edges.** Strategies, regime filter, allocator and risk rules are deterministic functions of explicit inputs. All I/O (exchange, clock, database) lives at the edges and is injected. This makes replay, testing, shadow accounting and the chaos endpoint possible.
2. **The exchange is the source of truth for positions and orders.** Local state is a cache that is reconciled, never trusted after a restart or an error.
3. **Every decision is explainable.** A decision cannot execute without a journal record that a human can read.
4. **Fail closed.** Missing data, stale data, ambiguous state, an unknown error: no new risk.
5. **Few strategies, deliberately simple, diversified by horizon.** Evidence from the research favours: slower trend persistence, hours-scale reversal, regime-dependent behaviour, and volatility-scaled sizing.

### 7.2 Layers (top to bottom)
1. **Exchange adapter** — official REST client plus signing helper plus WebSocket client, behind one internal interface. Owns: environment guard, clock-drift check, signing, retries/backoff, rate-limit accounting, error normalisation, unit normalisation (strings to decimals, microseconds to datetimes).
2. **Market data service** — builds and serves closed candles (warm-up from history plus live stream), top-of-book snapshots, mark and index prices, and a freshness signal. Emits a "candle closed" event per timeframe.
3. **Signal layer** — indicator computation, regime filter, and the strategies. Each strategy is a pure function from candle history (and config) to a proposed signal with reasons.
4. **Shadow layer** — one virtual account per strategy that trades every signal on paper with realistic costs; plus the allocator that chooses which strategy (or none) is allowed to take real risk.
5. **Risk gate** — a single mandatory checkpoint between a chosen signal and any order. Approves, resizes or rejects, and records which rules fired.
6. **Execution manager** — converts approved intents into exchange orders with brackets, tracks the order lifecycle, reconciles with the exchange, and feeds measured fill quality back to the shadow cost model.
7. **Cross-cutting** — decision journal (SQLite), FastAPI control plane, dashboard, chaos injector, configuration, logging.

### 7.3 Runtime model
- One process, one asyncio event loop. Blocking REST calls run in a worker thread pool. No blocking call on the loop.
- Background tasks started in the application lifespan: market-data stream, candle-close dispatcher, execution/reconciliation loop, heartbeat/dead-man loop, shadow-mark loop. Each task is supervised: on crash, log, mark engine degraded, restart with backoff, and halt entries if restarts exceed a threshold.
- Strategy evaluation is triggered **only on closed candles** (not on every tick). Ticks and order-book updates serve guards and execution quality, not signal generation.
- A bounded queue sits between the candle-close dispatcher and the decision pipeline; if the pipeline falls behind, stale decisions are dropped (and journalled), never executed late.

### 7.4 End-to-end flow per closed candle
1. Market data confirms the candle is closed and data is fresh and contiguous (no gaps).
2. Indicators and regime are computed once and shared.
3. Every strategy evaluates and proposes a signal (flat, long, short) with strength, a proposed stop distance, and reason codes.
4. Every shadow account processes the new candle: fills pending paper entries/exits using the cost model, marks open paper positions, updates its performance statistics.
5. The allocator, using shadow evidence and the regime, selects which strategy (if any) may trade for real, and with what weight in [0, 1].
6. The selected signal becomes an **order intent**: side, strategy, entry style, proposed stop and take-profit distances, desired risk fraction.
7. The risk gate evaluates the intent against account state, exposure, guards and limits; returns approve / resize / reject with numeric reasons.
8. If approved, the execution manager sets leverage, sizes to integer contracts respecting tick and size limits, places the entry with a client order ID, attaches the bracket, and tracks to completion.
9. Private WebSocket events (and periodic REST reconciliation) update orders and positions.
10. The journal writes one decision record covering steps 1–9, whether or not a trade happened. Non-trades are first-class records.

### 7.5 Engine state machine
States: **Initialising → Warming up → Running → Paused → Halted (kill switch) → Stopped.**
- Initialising: config validation, environment guard, clock check, credentials check, product resolution.
- Warming up: candle history loaded (if permitted) or live accumulation until indicators are valid. Shadow accounts may run; real trading may not.
- Running: normal operation.
- Paused: no new entries; existing positions keep their exchange-side protection; reachable by API or automatically on degraded conditions (stale feed, maintenance status, repeated errors, WebSocket down beyond a grace period).
- Halted: reached by the kill switch. Cancels working orders, closes positions via reduce-only/close-all, stops all entries, requires explicit human reset.
- Transitions and their triggers are logged in the journal.

---

## 8. Domain contracts (words, not code)

Agents must keep these contracts stable; changes need human approval and an entry in `docs/decisions.md`.

- **Candle:** instrument, timeframe, open time, close time, open/high/low/close, volume, a flag for closed vs forming, source (which price series).
- **Market snapshot:** best bid and ask with sizes, mark price, index/spot price, timestamp, derived spread, freshness age.
- **Signal:** strategy name, instrument, direction (long/short/flat), strength in [0, 1], proposed stop distance in price units, optional take-profit distance, time-stop in candles, list of reason codes with the numeric values that triggered them, indicator snapshot used.
- **Regime reading:** label (trending, ranging, chaotic/stand-aside), the metrics behind the label, the previous label (for hysteresis), confidence.
- **Shadow trade:** strategy, entry time/price (after modelled costs), exit time/price, exit reason, net result after fees and slippage, holding time, which stop/target logic closed it.
- **Shadow account statistics:** trade count, wins/losses, net result, drawdown, rolling-window versions of those, last update.
- **Allocation decision:** per-strategy sampled values, the selected strategy or "none", weight, whether exploration or evidence drove it, regime override flag.
- **Order intent:** strategy, direction, desired risk fraction of equity, proposed stop distance and take-profit distance, entry style, urgency, linked decision ID.
- **Risk verdict:** approve / resize / reject; resulting risk fraction and contract count; list of rules evaluated with pass/fail and the numbers compared; the binding rule.
- **Order record:** internal ID, client order ID, exchange order ID, parent decision ID, role (entry, bracket stop, bracket take-profit, forced exit), state, size, price fields, fills, fees, slippage versus expectation, timestamps.
- **Position view:** instrument, side, contracts, entry price, mark price, unrealised result, leverage, margin, active bracket, source (exchange-reconciled).
- **Decision record (journal):** see 9.7.
- **Engine event:** state transition, guard trigger, kill-switch event, reconciliation mismatch, with cause and timestamp.

---

## 9. Module specifications

### 9.1 Exchange adapter (Green zone for wrapper; Amber for reconnect logic)
Responsibilities:
- One internal interface exposing: product lookup by symbol, wallet balances, positions, active orders, order by ID/client ID, place order (with optional bracket), place bracket, cancel, cancel all, close all, set leverage, candles, ticker, order book, server-time/drift check, quota query, heartbeat operations, and streaming subscriptions.
- Environment guard and credential check at start; clock-drift check at start and periodically.
- Retry policy: retry only safe/idempotent reads automatically; for order placement, never blind-retry — first query by client order ID to see whether the previous attempt landed.
- Backoff on rate limiting using the exchange's reset header; reduce polling when budget is low.
- Normalisation: all prices/sizes become decimals (never floats for money), all times become timezone-aware datetimes, all errors become a small internal error taxonomy.
- A **fake exchange** implementing the same internal interface (and a thin simulation of the REST/WebSocket contract) lives in tests; it can emit scripted prices, partial fills, rejects, rate-limit errors and disconnects.
Acceptance: smoke script (signed read, tiny order, cancel) passes on testnet; guard refuses production hosts; drift check triggers on a skewed clock in tests.

### 9.2 Market data service (Amber)
- Warm-up: request the needed number of base-timeframe candles per strategy requirement plus a safety margin; respect alignment and pagination; verify contiguity (no gaps) and uniqueness; log any gaps and refuse to compute indicators across a gap.
- Live: build closed candles from the streaming feed using one consistent price series; guard against duplicate or out-of-order messages; on reconnect, backfill the missed interval from REST before resuming.
- Provide: latest closed candles per timeframe, top-of-book, mark/index prices, data age, and a boolean "fresh enough" per consumer with configurable staleness thresholds.
- Emit exactly one candle-closed event per candle per timeframe.
- A clock-based fallback closes candles if the feed stalls, but marks them degraded.
Acceptance: restart mid-session reconstructs the same candle history; a simulated feed gap produces a backfill and no duplicate events; stale data flips the freshness flag within the configured window.

### 9.3 Signal layer (Red zone) — see section 10 for strategy specifications
Common rules:
- Pure functions; no I/O; no randomness; no access to wall-clock time (time comes from candle timestamps).
- Strictly **no look-ahead**: a decision at candle close N may use only candles up to N.
- Each strategy declares its minimum history requirement; the engine will not call it earlier.
- Each strategy returns reason codes with numbers — the raw material for the journal narrative.

### 9.4 Shadow layer and allocator (Red zone)
**Shadow accounts**
- One virtual account per strategy with its own equity, positions, and statistics, starting from a fixed notional.
- Entry/exit fills are simulated against the next available price (never the same candle's close — avoids optimistic fills), then charged: exchange taker/maker fee from the live product object, plus a slippage allowance per side.
- Slippage allowance: start from a conservative default (research suggests at least a tenth to two-tenths of a percent per side on crypto, more in fast conditions) and **replace it with the measured median realised slippage** from real testnet fills once enough fills exist (see 9.6).
- Shadow accounts use the same stop/take-profit and time-stop logic the strategy proposes, so shadow results are comparable to what a real trade would experience.
- Shadow accounts run continuously, including when real trading is paused or halted; they are never allowed to affect real orders directly.
- Everything shadow-related is labelled "hypothetical" in all outputs.

**Allocator**
- Purpose: decide which strategy may take real risk on this candle, and how much of the risk budget it may use. Evidence-based, simple, explainable.
- Method: a Bayesian multi-armed-bandit (Thompson-sampling style) over strategies, where an arm's "success" is a closed shadow trade that is net-positive after costs. Use a recency window or exponential forgetting so evidence adapts to regime change.
- Cold start: until a strategy has a minimum number of closed shadow trades, use a neutral prior and the regime-based default mapping (trend strategy preferred in trending regimes, reversion in ranging regimes, none in chaotic).
- Exploration floor: never starve a strategy completely; keep a small chance of selection so evidence continues to accumulate, but exploration never overrides the regime stand-aside or the risk gate.
- Regime override: in a stand-aside regime, the allocator returns "none" regardless of sampled values.
- Output includes the sampled values and the reason it chose what it chose, in plain words.
Acceptance: deterministic given a fixed random seed; unit tests cover cold start, forgetting, stand-aside override and starvation prevention; allocator output always carries a human-readable reason.

### 9.5 Risk gate (Red zone policy; primitives reused from riskkit)
The gate is mandatory and single. Nothing reaches the exchange without passing it. Rules are evaluated in a fixed documented order; the first hard failure rejects; sizing rules then resize.

**Hard rejections**
- Engine not in Running state; environment guard failing; clock drift flagged.
- Market data stale, gapped, or degraded beyond tolerance.
- Product not fully operational; maintenance or degraded system status active.
- Spread wider than a configured limit; top-of-book depth too thin for the intended size; expected slippage above a limit.
- Daily loss limit reached; drawdown ladder at its halt rung; consecutive-loss cooldown active.
- Maximum concurrent positions or maximum notional exposure would be exceeded; correlation-group cap (if more than one instrument).
- Intent has no valid protective stop; stop distance below the minimum (too tight to survive noise) or implying a loss larger than the per-trade risk budget at minimum size.

**Sizing (when not rejected)**
- Start from a fixed-fraction risk budget per trade (a small fraction of current equity), divided by the stop distance, to get a position size.
- Scale by volatility (the research emphasises that volatility scaling drives much of the benefit of trend strategies): when volatility rises, size falls proportionally.
- Apply the allocator's weight and the drawdown ladder's multiplier.
- Cap by a fractional-Kelly ceiling **only as a ceiling, never as a target**, and only if the shadow statistics are trustworthy (enough trades); otherwise ignore Kelly entirely. Never exceed full Kelly; prefer a quarter to a half.
- Cap by leverage limit: **explicitly set leverage** to a small configured value before entry; never rely on the exchange's default, which can be very high.
- Round **down** to integer contracts; reject if the result is below the minimum tradable size.

**Always-on guards (independent of intents)**
- Kill switch triggers: daily loss limit breach; drawdown halt rung; reconciliation mismatch that cannot be resolved; repeated order failures; unprotected position detected (a position without an exchange-side bracket); manual API call; dead-man heartbeat failure.
- Kill switch actions in order: stop accepting intents; cancel all working orders; close all positions with reduce-only actions; verify flat via exchange state; write a kill record; enter Halted.
- Unprotected-position watchdog: if a position exists without an active bracket for longer than a grace period, re-attach protection or close.
- Data-freshness and WebSocket-health watchdogs with auto-pause and auto-resume (resume requires fresh, contiguous data again).

Default parameters (starting points only — **humans own final values** and must record them in `docs/risk.md` with rationale): risk per trade around half to one percent of equity; daily loss limit a few percent; leverage cap in the low single digits; maximum concurrent positions one or two; stop distance expressed in multiples of recent average true range; cooldown after a short run of consecutive losses.

Acceptance: a table-driven test suite covers every rule with pass and fail cases; sizing is property-tested (never exceeds budget, always integer contracts, monotonic in volatility); the chaos suite (13.4) demonstrates each kill-switch trigger.

### 9.6 Execution manager (Red zone logic; Amber helpers)
**Order policy**
- Entries: prefer marketable limit orders with IOC at a bounded distance from the touch so that slippage is capped by construction; if unfilled, one limited re-attempt then abandon (and journal the abandonment). Use post-only only for strategies that are explicitly passive (for example an optional market-making strategy).
- Immediately after an entry fills (or as an attached bracket if the exchange supports it on the entry), ensure an exchange-side stop-loss and take-profit exist. The bracket's protection is the primary exit; strategy-driven exits (signal flip, time stop) are executed as reduce-only orders that also cancel the bracket as needed.
- Never open a position while a previous order for the same instrument is in an unknown state.
- One active position per instrument per strategy-owner in v1 (no pyramiding, no hedging between strategies).

**Idempotency**
- Every order carries a unique client order ID composed of: project prefix, strategy code, decision ID (shortened), role, and attempt number. Before any retry, query by client ID.
- Duplicate intents for the same decision ID are ignored.

**Lifecycle tracking**
- States: intent created → risk approved → submitted → open → partially filled → filled | cancelled | rejected | expired | unknown.
- "Unknown" (timeouts, ambiguous responses) triggers immediate reconciliation by client ID before any further action; if unresolved within a short window, escalate to the kill-switch conditions.

**Reconciliation**
- On startup: pull positions, open orders and balances; rebuild the internal view; refuse to open new risk until reconciled; adopt orphaned positions and ensure they are protected, or close them.
- Continuously: private WebSocket events are applied as they arrive; periodically (low frequency, within the rate-limit budget) compare the internal view with REST truth; on mismatch, trust the exchange, journal the discrepancy, and raise an engine event.

**Fill quality feedback**
- For every real fill, record expected price (from the top-of-book at decision time), actual average fill price, realised slippage in basis points, fees, and latency from decision to fill. Maintain rolling statistics and expose them; the shadow cost model consumes the median realised slippage.

**Error handling**
- Margin-related rejection: reduce size once if the risk gate allows; otherwise abandon and journal.
- Rate-limit response: back off per exchange header; if sustained, pause entries.
- Authentication or signature errors: halt entries, run the clock and key diagnostics, alert.
- Exchange-side partial outage or disrupted trading status: pause entries; allow only cancel/close actions.

Acceptance: integration tests against the fake exchange for partial fills, rejects, timeouts, duplicate responses and restarts with open positions; one testnet end-to-end run places, protects, reconciles and closes a real testnet position.

### 9.7 Decision journal (Red zone for narrative; Amber for persistence)
Purpose: make the system's reasoning auditable and demo-able. One record per candle-close decision (including "no trade"), plus engine events.
Each record contains: decision ID, timestamps (candle close, decision, order submit, final state), instrument, timeframe, data freshness and the candle values used, regime reading and metrics, every strategy's signal with reason codes and numbers, shadow statistics snapshot, allocator samples and selection reason, risk verdict with every rule and compared numbers and the binding rule, order intent, order records and outcomes, realised slippage and latency, and a **plain-language narrative** (two to five sentences, written by deterministic templates from the structured fields, not by a language model, so it is reproducible and explainable).
Storage: SQLite tables for decisions, orders, fills, shadow trades, shadow statistics snapshots, engine events and configuration snapshots (a snapshot of the active configuration is stored with each session so any decision can be traced to the exact parameters).
Retention: whole session; export as a file on demand.
Acceptance: given a decision ID, a person unfamiliar with the code can explain why the system acted or did not act using only the record.

### 9.8 Control plane (Green zone shells; handlers call Red-zone modules)
Read-only endpoints (open on the demo network):
- Health (process, event loop, tasks, database, exchange connectivity, clock drift, data freshness, WebSocket state).
- Status (engine state, active configuration summary, current regime, allocator choice, today's PnL and drawdown rung, kill-switch state).
- Positions and orders (exchange-reconciled), recent fills, fill-quality statistics.
- Strategies (shadow account performance, labelled hypothetical).
- Decisions (paged list) and a single-decision explanation view that renders the narrative plus the structured breakdown.
- Configuration (read-only, secrets redacted).
State-changing endpoints (shared-secret header required): start, pause, resume, kill, reset-from-halt (requires explicit confirmation field and a reconciled flat state), chaos injection (13.4), manual flatten.
All state-changing calls are journalled as engine events with the caller identity (token label), never the secret.

### 9.9 Dashboard (Green zone; optional)
A single static page served by the app, polling the read-only endpoints. Shows: engine state and health lights, live price and regime, current positions with their brackets, today's PnL and drawdown, shadow account comparison (clearly labelled hypothetical), the latest decisions with a click-through explanation, and a prominent kill button guarded by the secret. No build toolchain required.

---

## 10. Strategy specifications (Red zone: human-authored; this section defines intent, not code)

### 10.1 Common conventions
- Primary instrument: BTC perpetual; optional second instrument only after everything else works.
- Base timeframe is configurable. The research evidence is strongest at multi-hour to multi-day horizons for trend and at one-to-four-hour horizons for reversal; a one-day hackathon cannot wait days. Therefore: default to an hourly (or similar) base timeframe for the written strategy rationale, and provide a **clearly labelled demo profile** with a shorter timeframe so a trade can plausibly occur during the demo slot. The demo profile is disclosed in the README and in the on-screen banner; it is never presented as the researched configuration.
- Every strategy declares: purpose, market assumption, entry rule, exit rule, stop logic, time stop, minimum history, parameters with allowed ranges.
- Costs are always included in any evaluation.

### 10.2 Strategy A — Trend following (volatility-scaled)
- **Idea:** persistence of recent returns in crypto is documented at weekly and shorter horizons for the major coins, and the benefit of trend strategies depends heavily on volatility-scaled sizing.
- **Signal concept:** direction from a slow-versus-fast average relationship or breakout of a recent range, confirmed by a trend-strength measure; exit on reverse signal, trailing stop, or time stop.
- **Stop:** a multiple of recent average true range; proposed to the risk gate, which sizes inversely to it.
- **Stand-aside:** produces no signal when the regime filter says ranging or chaotic.
- **Why it might fail (document this):** whipsaw in range-bound markets; trend profits are regime-dependent and have faded in some periods in other asset classes; costs erode frequent flips.

### 10.3 Strategy B — Short-horizon mean reversion
- **Idea:** studies of Bitcoin find negative autocorrelation (reversal) at one-to-four-hour horizons, with larger moves reversing more, attributed to overreaction and leverage-driven liquidation cascades.
- **Signal concept:** fade statistically large deviations from a short-term mean (standardised distance), only when a stationarity/half-life check indicates the series is currently mean-reverting; exit at partial reversion to the mean, at a protective stop, or at a time stop proportional to the estimated half-life.
- **Stop:** a multiple of recent average true range, wider than the entry deviation would suggest, plus a hard time stop.
- **Why it might fail:** catching falling knives in genuine trend breaks; liquidation cascades can extend; costs are material on short horizons.

### 10.4 Regime filter (meta-layer)
- **Purpose:** decide whether the market is trending, ranging, or chaotic, and enforce stand-aside.
- **Inputs:** a trend-strength measure, a volatility ratio (short versus long realised volatility), and an efficiency/choppiness measure.
- **Properties:** hysteresis (enter and exit thresholds differ) to prevent flickering; a minimum dwell time in a regime; a documented mapping from regime to the default strategy preference; the chaotic/stand-aside regime triggers a "none" allocation.
- **Rationale:** strategies fail when regimes change; staying out of chop is a legitimate decision and is journalled as such.

### 10.5 Parameter discipline (prevents backtest overfitting)
- Each parameter has a small, pre-declared set of candidate values chosen from theory and common practice, not from searching.
- Maintain `docs/trials.md`: a running count of every configuration ever evaluated for each strategy, with the date and why. The README states the total. Research shows that trying many configurations nearly guarantees a flattering result that will not hold out of sample.
- No tuning on the demo-day testnet session. Parameters are frozen before the demo; any change after freeze is logged.
- Any sanity replay uses data the parameters were not chosen on, includes costs, and is labelled as a sanity check, not evidence of profitability.

### 10.6 Optional stretch — Market making (inventory-aware quoting)
Only if everything else is done. Reference: the classic optimal market-making model in which the fair quote shifts away from the side where inventory is accumulating and the spread widens with volatility and narrows with liquidity. Operates with tiny size, strict inventory caps, post-only quotes, and an automatic stop in trending conditions. It is tied to the thin-testnet-book risk and must not run in the same account balance budget as the directional strategies without separate caps.

### 10.7 Explicitly out of scope
Funding/basis carry (needs a spot leg and verified funding data; carry also historically precedes crashes), cross-pair statistical arbitrage (slow, two-legged, cost-sensitive in the evidence reviewed), options strategies, machine-learning price prediction as a primary driver. A learned regime classifier is a possible later enhancement, not part of v1.

---

## 11. Configuration

Principles: all tunable values live in a typed configuration object with documented defaults; environment variables supply secrets and the environment selector; a versioned configuration file supplies parameters; the active configuration is snapshotted into the database for every session.

Environment variables (names only): exchange API key; exchange API secret; environment selector (testnet only accepted); control-plane shared secret; database path; log level.

Configuration groups: instruments and timeframes; warm-up (enabled flag, candle counts); each strategy's parameters; regime thresholds and hysteresis; shadow cost model (fee source, default slippage, calibration minimum fills); allocator (prior strength, window, exploration floor, minimum trades); risk (all limits in 9.5); execution (entry style, abandonment timing, reconciliation period); data freshness thresholds; rate-limit budget fraction; demo profile overrides (clearly flagged); control-plane settings.

Freeze rule: a "freeze" command locks strategy and risk parameters for the demo; changing them afterwards requires an explicit unfreeze that is journalled.

---

## 12. Repository layout (project-specific; same tech stack)

Root files: this agent.md; README; dependency manifest with pinned versions; example environment file; git-ignore; licence.

- **app** — application package
  - **api** — control-plane routers, request/response schemas, auth dependency
  - **core** — configuration, typed contracts (section 8), event definitions, engine state machine, supervisor, clock abstraction
  - **exchange** — environment guard, signing helper, REST wrapper, WebSocket wrapper, rate-limit accountant, error taxonomy, normalisers
  - **data** — candle store, warm-up, live candle builder, snapshot service, freshness tracker
  - **signals** — indicator adapters, regime filter, strategy modules (trend, reversion, optional market-making)
  - **shadow** — shadow accounts, cost model, allocator
  - **risk** — policy (rule order and thresholds), sizing, guards, kill switch, watchdogs
  - **execution** — intent builder, order manager, lifecycle, reconciliation, fill-quality tracker
  - **journal** — schema, writer, narrative templates, export
  - **dashboard** — static page assets
- **config** — default parameter file and the demo-profile overrides
- **tests** — unit (pure logic), integration (against the fake exchange), chaos (scenario scripts), fakes (the fake exchange and scripted feeds), fixtures
- **scripts** — connectivity smoke script, warm-up verification, session export, environment diagnostics
- **docs** — architecture, strategy rationale, risk policy, runbook, demo script, decisions log, third-party register, ai-usage log, ownership, trials log, qa-prep, limitations

If the organisers' template filenames (main entry, strategy module, client module) must appear at the repository root for judging, provide thin re-export shims at the root that point to the modules above; do not duplicate logic.

---

## 13. Testing and chaos

### 13.1 Principles
- Pure logic gets unit tests; everything with I/O gets integration tests against the fake exchange; the real testnet is used only by the smoke script and a small number of end-to-end rehearsals.
- Tests encode the research-derived pitfalls: no look-ahead, costs always applied, sizing never exceeds budget, stale data never trades.

### 13.2 Unit and property tests (examples of required coverage)
- Indicators/regime: warm-up boundaries, hysteresis, gap handling.
- Strategies: deterministic outputs on fixed candle fixtures; no signal before minimum history; no look-ahead (changing future candles never changes past decisions).
- Shadow accounting: costs applied, next-candle fills, stop/target precedence rules for candles that touch both.
- Allocator: cold start, forgetting, override, exploration floor, determinism with a seed.
- Risk: every rule pass/fail; sizing properties; ordering of rules.
- Narrative templates: every structured case produces a non-empty, consistent narrative.

### 13.3 Integration tests (fake exchange)
Partial fills; rejected orders; timeouts with unknown state; duplicate responses; WebSocket drop and backfill; restart with open position and orphan order; rate-limit responses; margin rejection; disrupted trading status; clock drift error.

### 13.4 Chaos scenarios (also exposed through the chaos endpoint for the demo)
Each scenario is defined by humans (Red) and executed by the harness (Green):
1. **Price shock:** a sudden large adverse move replayed through the risk gate — expected: bracket/stop logic and loss-limit rungs behave; kill switch triggers when thresholds are crossed.
2. **Stale feed:** data stops — expected: auto-pause, no entries, journal event, resume only after fresh contiguous data.
3. **WebSocket loss:** expected: degrade to polling within budget, backfill on return.
4. **Order uncertainty:** an ambiguous order response — expected: reconcile by client ID, never double-send.
5. **Unprotected position:** a position appears without a bracket — expected: watchdog re-protects or flattens.
6. **Rate-limit storm:** expected: backoff, pause entries, no ban-style behaviour.
7. **Restart with open position:** expected: adopt, protect, continue.
Chaos injections in the demo operate on the fake/simulated layer or on the decision pipeline's inputs; they must never send harmful traffic to the exchange, and they are visibly labelled on screen.

### 13.5 Acceptance checklist (release gate)
- Environment guard refuses production hosts.
- Smoke test passes on testnet (read, tiny order, cancel).
- Full cycle on testnet: signal → shadow → allocator → risk → order → bracket → reconcile → close, with a complete journal record.
- Every chaos scenario passes.
- Secrets scan clean; third-party register complete; AI-usage log current and under budget.
- README and demo script match the actual behaviour.

---

## 14. Phased plan and exit criteria

Time-box to the event day. Humans decide the clock; agents report progress against these exits.

**Phase 0 — Connectivity and ground truth.**
Tasks: environment and keys per 6.1–6.2; clock check; smoke script (signed balance read, tiny far-from-market order, cancel); resolve the BTC product and record its contract value, tick size, limits and fee rates; confirm WebSocket public and private connectivity; verify the items in section 16 that block later phases (IP whitelisting, candle resolutions and limits, bracket support in the client, dead-man switch).
Exit: smoke test green; `docs/decisions.md` records every verified fact and every discrepancy.

**Phase 1 — Data and first strategy in shadow.**
Tasks: warm-up and live candle pipeline; indicator adapters; trend strategy (human-authored) running in a shadow account; journal skeleton writing no-trade and shadow records; control-plane health and status.
Exit: one hour of live running with correct candles, shadow trades with costs, journal records readable.

**Phase 2 — Risk and execution (first real orders).**
Tasks: risk gate with sizing and guards; execution manager with brackets, idempotency, reconciliation; kill switch; first real testnet position opened, protected and closed by the system.
Exit: end-to-end cycle passes; kill switch and watchdog demonstrated on the fake exchange.

**Phase 3 — Second strategy, regime, allocator.**
Tasks: mean-reversion strategy; regime filter; shadow comparison; allocator; fill-quality feedback into the cost model.
Exit: allocator decisions explained in the journal; cost model calibrated from real fills.

**Phase 4 — Proof and polish.**
Tasks: chaos endpoint and scenarios; dashboard; parameter freeze; README (strategy rationale, risk explanation, setup, API usage, limitations, parameter-trial count); demo script and rehearsal; Q&A preparation; adversarial review pass with findings addressed.
Exit: acceptance checklist 13.5 complete; two full rehearsals done.

**Cut list if time runs short (in this order):** dashboard; optional market-making; allocator (replace with the fixed regime-based mapping, and say so honestly); second instrument; second strategy. **Never cut:** environment guard, risk gate, brackets, kill switch, journal, README, tests for the risk gate.

---

## 15. Demo and README requirements

### 15.1 Demo script outline (must show everything the judges asked for)
1. Show health: connected to the testnet, clock fine, data fresh (API connectivity).
2. Show current regime, shadow accounts running (always-live activity), and the allocator's choice with its reason.
3. Trigger or wait for an automated decision; open its explanation view; walk the risk verdict.
4. Show the real testnet order, its bracket and the reconciled position (positions display).
5. Run a chaos scenario; show the kill switch or pause behaviour and the journal events.
6. State limitations honestly, including that the demo profile uses a shorter timeframe than the researched configuration, and that all shadow results are hypothetical.
Every team member can answer questions about their owned modules (qa-prep).

### 15.2 README must contain
- Overview and architecture summary in plain language.
- Strategy explanation: the written rationale for each strategy, the regime logic, the allocator, with references to the research basis (section 17) and honest limitations.
- Risk management explanation: every rule, default and why.
- Setup instructions: prerequisites, environment variables, how to create a demo account and key, IP whitelisting note, how to run, how to run tests, how to run the smoke script.
- API usage description: which exchange endpoints and channels are used, authentication approach, rate-limit budget approach; and the control-plane endpoints.
- Parameter-trial count and freeze statement.
- Third-party components and attributions.
- AI-assistance disclosure consistent with the usage log.
- Limitations and known issues.

---

## 16. Open verification items (verify; do not assume)

| # | Item | Why it matters | Owner action |
|---|---|---|---|
| 1 | Whether API candles may be used for warm-up and sanity replay | Event rule says no datasets are provided | Ask organisers; make warm-up switchable |
| 2 | Whether third-party libraries are allowed and how they count toward the AI/originality rule | Affects reuse plan | Ask organisers; log all reuse |
| 3 | IP whitelisting enforcement for testnet keys | Blocks all trading if mishandled | Test in Phase 0 |
| 4 | Licence and maintenance of riskkit-quant, delta-rest-ws, the indicator library, vectorbt | Public repository compliance and stability | Check in Phase 0; record in third-party register |
| 5 | Whether the official REST client wraps bracket orders and other needed endpoints | Determines size of the signing helper | Inspect in Phase 0 |
| 6 | Whether the official REST client is blocking | Determines threading approach | Inspect in Phase 0 |
| 7 | Candle resolutions supported; per-call limits; pagination | Warm-up design | Test in Phase 0 |
| 8 | WebSocket channel names and symbol conventions for candles, mark price, ticker; heartbeat behaviour | Data pipeline correctness | Test in Phase 0 |
| 9 | Dead-man switch availability and semantics on testnet | Risk layer | Read docs; test in Phase 0 |
| 10 | Client order ID format limits | Idempotency scheme | Test in Phase 0 |
| 11 | Testnet order-book depth and fill realism | Slippage and shadow calibration | Measure in Phase 1–2 and document |
| 12 | Funding-rate history availability (sources conflict) | Only matters if carry is ever reconsidered | Leave out of scope unless verified |
| 13 | Whether spot products are tradable on testnet | Only matters for carry | Leave out of scope |
| 14 | Settling asset and units on the testnet BTC product (documentation samples are inconsistent between currencies) | Sizing and PnL units | Read the live product object in Phase 0 |
| 15 | Maximum number of instruments/leverage the organisers allow | Event rules | Ask organisers |

---

## 17. Research basis (cite in README; do not overstate)

- Time-series momentum across asset classes (Moskowitz, Ooi, Pedersen, Journal of Financial Economics, 2012), and the critique that much of the benefit comes from volatility scaling and has been weaker since 2009 (Tse and co-authors).
- Crypto-specific evidence: strong time-series momentum and weak cross-sectional momentum in several studies (Liu and Tsyvinski; Borgards, 2021); intraday predictability by session (Shen, Urquhart, Wang, Financial Review, 2022); negative autocorrelation at one-to-four-hour horizons in Bitcoin, attributed partly to leverage-driven liquidations.
- Backtest overfitting (Bailey, Borwein, López de Prado, Zhu, Notices of the AMS, 2014): the more configurations tried, the more likely a flattering but non-repeatable result; related corrections (deflated Sharpe ratio, minimum backtest length).
- Practitioner book: Ernie Chan, Algorithmic Trading: Winning Strategies and Their Rationale (2013) — mean-reversion and momentum testing, regime changes, risk management and backtest pitfalls.
- Market making: Avellaneda and Stoikov, "High-frequency trading in a limit order book" (2008).
- Perpetual futures and carry: BIS Working Paper 1087 "Crypto Carry" (large average carry, carry predicts crashes); the "Fundamentals of Perpetual Futures" paper (funding-rate arbitrage is not riskless). Used here to justify keeping carry out of scope.
- Position sizing: Kelly criterion with fractional-Kelly practice (Thorp's A Man for All Markets; Van Tharp), systematic sizing (Carver's Systematic Trading).
- Costs: slippage and fees are routinely the reason backtests fail live; paper or simulated environments often lack order-book realism.
Caveat for all of the above: much of the evidence is at daily-to-monthly horizons, on other asset classes or earlier crypto samples, and from working papers and secondary summaries. It supports design principles; it does not promise an edge in a one-day testnet session.

---

## 18. Definition of done (project level)

- A judge can clone the repository, follow the README, run the system against their own testnet key, and see it connect, decide, place protected orders and explain itself.
- Every safety rule in section 2 is enforced by code and covered by a test.
- The decision journal can explain any action or inaction.
- Chaos scenarios demonstrate the safeguards.
- Humans can explain every Red-zone module without notes; the AI-usage log shows the project remains within the event's AI-code limit.
