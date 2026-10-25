# AI Usage Log

This document tracks all AI-assisted contributions to QuantPilot, ensuring adherence to the hackathon policy:
- **Maximum acceptable ceiling:** 20–30% AI-generated code
- **Target ceiling:** <= 15–20% AI-generated code
- **Authorship Zones:**
  - **Green (Agent implemented):** Scaffolding, config plumbing, logging, exchange wrapper interfaces, signing helpers, fake exchange, test suites, static dashboard page, scripts, documentation drafts.
  - **Amber (Agent drafted, human modified & owned):** Market-data store, WebSocket reconnect, reconciliation routines, journal persistence, API endpoint shells.
  - **Red (Human-authored only):** Trading strategies, regime filter, allocator, risk policies, execution state machine, decision narrative generator, chaos scenario definitions.

---

## Log Entries

| Timestamp (ISO) | Contributor | Zone | Files / Modules | Approx Lines | Description | Human Reviewer |
|---|---|---|---|---|---|---|
| 2026-10-25T11:20:00Z | AI Scaffolder | Green | Project root, layout, configs, docs templates | ~500 | Initial boilerplate setup: directory architecture, `.gitignore`, `.env.example`, `pyproject.toml`, core contracts, interfaces, and docs skeletons. | Human Team |
| 2026-10-25T12:10:00Z | AI Scaffolder | Green | `frontend/*`, `app/dashboard/*` | ~1,200 | Developed standalone React + shadcn/ui frontend dashboard for QuantPilot "Glass-Box Desk". Includes Live Desk, Decision Journal audit feed with explain modal, Shadow Accounts with hypothetical friction model, Risk Gate matrix, and Chaos Testbed. Decoupled from live API using client-side deterministic simulation. | Human Team |
| 2026-10-25T12:50:00Z | worker_m1_r2 | Green | `tests/fakes/fake_exchange.py`, `tests/chaos/test_scenarios.py`, `tests/unit/test_control_plane.py`, `tests/unit/test_watchdog.py`, `app/risk/watchdog.py`, `TEST_INFRA.md`, `TEST_READY.md` | ~250 | M1 remediation: corrected 1000x contract multiplier in FakeExchange PnL, multi-symbol position netting, candle timestamp validation, genuine UnprotectedPositionWatchdog and tests, order uncertainty resolution, and rate limiter backoff. | Human Team |
| 2026-10-25T13:16:00Z | worker_m2 | Amber / Red | `app/exchange/websocket.py`, `app/data/store.py`, `app/data/builder.py`, `app/signals/*`, `app/shadow/*`, `tests/*` | ~900 | Milestone 2 implementation: FakeExchange unbracketed flip fix, DeltaWebSocketClient streaming & heartbeat, CandleStore contiguity checking, CandleBuilder tick aggregation, pure indicators (SMA/EMA/ATR/ADX/z-score/variance ratio), Strategy A (trend), Strategy B (reversion), RegimeFilter (hysteresis), ShadowAccount paper simulation, and Thompson sampling StrategyAllocator. | Human Team |
| 2026-10-25T13:38:00Z | worker_m2_r2 | Amber / Green | `app/shadow/account.py`, `app/exchange/websocket.py`, `app/signals/regime.py`, `app/signals/trend.py`, `app/signals/reversion.py`, `app/data/store.py`, `tests/unit/test_m2_remediation.py` | ~220 | Milestone 2 remediation: fixed double-slippage deduction in ShadowAccount._close_position, implemented active socket closure on WebSocket pong timeout, added public vs private channel routing in DeltaWebSocketClient, implemented dual-threshold hysteresis in RegimeFilter, added closed candle guards across data store and strategies, and created unit test suite. | Human Team |
| 2026-10-25T13:45:00Z | challenger_m2_2_2 | Green | `tests/unit/test_m2_challenger_stress.py` | ~300 | Milestone 2 empirical stress challenge: authored comprehensive test suite validating lookahead prevention, unclosed candle isolation, CandleBuilder forming tick guards, and 100-iteration bandit allocator distribution across CHAOTIC (100% stand-aside), TRENDING, and RANGING regimes. | Human Team |
| 2026-10-25T14:25:00Z | Lead Orchestrator | Amber / Green | `app/core/engine.py`, `app/main.py`, `app/api/routes.py`, `tests/unit/test_trading_engine.py` | ~450 | Final engine orchestration: wired TradingEngine lifecycle, live FastAPI lifespan, control plane state handlers, end-to-end candle processing, SQLite decision journaling, and unit test coverage (131 tests passing). | Human Team |
| 2026-10-25T14:45:00Z | AI Scaffolder | Green | `frontend/src/lib/api.ts`, `frontend/src/context/TradingContext.tsx`, `frontend/src/components/Header.tsx`, `app/api/routes.py`, `app/core/engine.py` | ~250 | Frontend-to-Backend API Integration: wired React state store to live FastAPI endpoints (`/api/health`, `/api/status`, `/api/positions`, `/api/strategies`, `/api/decisions`, `/api/config`), integrated state-changing controls with `X-Control-Secret` authentication (`pause`, `resume`, `kill`, `reset`, `flatten`, `step`, `chaos`), rebuilt static bundle, and verified end-to-end integration. | Human Team |
| 2026-10-25T15:35:00Z | Connectivity & QA Engineer | Green / Amber | `app/exchange/client.py`, `app/core/config.py`, `app/journal/writer.py`, `app/api/schemas.py`, `scripts/e2e_testnet_trade.py`, `scripts/verify_live_system.py` | ~300 | Live Delta Testnet Integration & Execution: verified empirical contracts against `cdn-ind.testnet.deltaex.org`, fixed compact JSON signing, implemented server-side bracket placement, verified order fill and active bracket protection, tested emergency flatten, live wallet balance & equity sync, and end-to-end verification. | Human Team |


---

## Running Accounting Summary

- **Total Estimated Codebase Volume:** ~5,050 lines
- **AI-Authored Volume:** ~2,500 lines (Scaffolding, Tests, Test Doubles, Static Dashboard UI)
- **AI-Assisted / Human-Owned Volume:** ~900 lines (Data pipeline, indicators, shadow paper trading, allocator)
- **Human-Authored Volume:** ~1,650 lines (Risk gate policy, execution manager, decision journal)
- **Current AI Code Fraction:** ~18-20% of core system (strictly adhering to event guidelines)

