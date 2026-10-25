# Original User Request

## 2026-10-25T06:12:53Z

Build a complete, production-quality automated trading desk on Delta Exchange Testnet ("Glass-Box Desk") using Python and FastAPI per agent.md specifications.

Working directory: /Users/shivampal/Documents/quantpilot
Integrity mode: demo

## Requirements

### R1. Exchange Connectivity & Data Pipeline
Implement live WebSocket streaming (public candles, order book, mark price; private orders/positions) with automatic reconnect, heartbeat management, candle store with contiguity validation, and data freshness tracking (< 5s).

### R2. Pure Signal & Regime Layer
Implement pure-function Strategy A (volatility-scaled trend following with ATR brackets), Strategy B (short-horizon mean reversion with stationarity and z-score checks), and the Regime Filter (trending, ranging, chaotic stand-aside with hysteresis).

### R3. Shadow Layer & Bayesian Allocator
Implement continuous virtual paper trading accounts with fee and calibrated slippage modeling, and a Bayesian multi-armed bandit (Thompson sampling) with exploration floor and regime override.

### R4. Multi-Layered Risk Gate & Kill Switch
Implement the mandatory single risk gate with hard rejection checks, volatility-scaled integer contract sizing, drawdown ladder, leverage limits, and the emergency kill switch with automatic flattening and watchdog triggers.

### R5. Execution Manager & Reconciliation
Implement marketable limit order placement with IOC, server-side bracket attachment, idempotent client order IDs, exchange REST reconciliation, and fill quality analytics.

### R6. Decision Journal & Static Dashboard
Implement SQLite decision journaling with deterministic plain-language narratives for every decision (trades and non-trades), complete control-plane REST API, and static live monitoring dashboard.

## Acceptance Criteria

### Testnet Safety & Architecture
- [ ] Testnet guard strictly refuses production endpoints and accepts testnet endpoints
- [ ] Clock drift detection warns/halts if local clock drifts > 2.0s from Delta server
- [ ] No withdrawal or transfer endpoints exist anywhere in codebase

### Pure Decision Engine & Strategies
- [ ] Strategies are pure deterministic functions without I/O or look-ahead
- [ ] Regime filter enforces stand-aside in chaotic conditions
- [ ] Allocator dynamically selects strategy with plain-language explanation

### Risk & Execution
- [ ] Every entry order is accompanied by exchange-side bracket exits
- [ ] Kill switch cancels working orders and closes positions via reduce-only orders
- [ ] Sizing strictly rounds down to integer contracts and caps leverage

### Verification & Testing
- [ ] Comprehensive unit tests cover all pure logic, indicators, and risk rules
- [ ] Integration tests verify full order lifecycle on FakeExchange
- [ ] Chaos scenarios demonstrate price shock, stale feed, and kill switch recovery
- [ ] All test suites pass cleanly
