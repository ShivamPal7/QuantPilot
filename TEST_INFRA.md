# QuantPilot Test Infrastructure & Architecture (`TEST_INFRA.md`)

**Project:** Delta Exchange Testnet Algorithmic Trading System ("Glass-Box Desk")  
**Milestone:** M1 — E2E Testing Track & Test Infrastructure (Remediation M1-R2)  
**Verification Date:** 2026-10-25  
**Test Suite Status:** 73 Tests, 100% Passing (0 failures, 0 errors)  
**Execution Runtime:** Python 3.9+ / 3.14+ standard library `unittest` (Zero External Dependencies Required)

---

## 1. Architecture & Design Principles

The test infrastructure is constructed under strict adherence to `agent.md` charter rules:
1. **Zero External Dependency Guarantee:**
   The test harness executes using Python's standard library `unittest` and `unittest.IsolatedAsyncioTestCase`. Tests run cleanly in sandboxed environments without external packages.
2. **Dual Test Runner Compatibility:**
   `tests/conftest.py` is conditionally guarded. Running `python3 -m unittest discover tests` or `pytest tests/` both execute seamlessly.
3. **Pure Logic vs. Impure Boundary Verification:**
   Strategies, indicators, risk gate rules, and sizing calculations are evaluated as pure deterministic functions without side effects or look-ahead bias.
4. **Exchange Double (`FakeExchange`):**
   Full in-memory test double of Delta Exchange with realistic order lifecycle transitions, synthetic OHLC candles, price-triggered brackets, and chaos simulation toggles.

---

## 2. In-Memory Test Double: `FakeExchange`

`tests/fakes/fake_exchange.py` implements `ExchangeClientProtocol`:

### Key Capabilities & Remediated Behavior:
- **Accurate Financial PnL Modeling (`contract_multiplier`):**
  Realized PnL across bracket stop-loss/take-profit triggers and `close_all()` strictly incorporates `self.contract_multiplier = Decimal("0.001")` (0.001 BTC per contract). For Long: `(exit - entry) * size * 0.001`; for Short: `(entry - exit) * size * 0.001`. Fixes the prior 1,000x overstatement bug.
- **Multi-Symbol & Netting Position Tracking:**
  Positions are managed per symbol in `self.positions`. Same-side orders accumulate contracts and compute weighted average entry prices. Counter orders correctly reduce, close (flatten), or flip positions, realizing PnL on closed contracts and updating `self.balance`. Other symbols in `self.positions` are fully preserved.
- **Strict Candlestick Query Validation:**
  `get_candles(symbol, resolution, start_time_s, end_time_s)` returns empty list `[]` when `end_time_s <= start_time_s` or timestamps/resolutions are invalid. Custom candles are properly filtered by query window.
- **Accurate Order State Tracking:**
  Tracks `OPEN`, `FILLED`, `CANCELLED`, and `REJECTED` states across `active_orders` and `order_history`.
- **Client Order ID Idempotency:**
  Duplicate submissions with identical `client_order_id` return the existing order without creating duplicate positions.
- **Price-Triggered Brackets:**
  `set_market_price(new_bid, new_ask)` updates the exchange price touch and evaluates all active positions against bracket parameters:
  - Long position: `current_bid <= stop_loss` triggers `BRACKET_STOP`; `current_bid >= take_profit` triggers `BRACKET_TAKE_PROFIT`.
  - Short position: `current_ask >= stop_loss` triggers `BRACKET_STOP`; `current_ask <= take_profit` triggers `BRACKET_TAKE_PROFIT`.
  - Triggered brackets close positions, credit/debit realized PnL to balance, and log filled bracket orders.
- **Chaos & Fault Injection:**
  - `simulate_rate_limit = True`: raises HTTP 429 `RateLimitExceededError` on REST calls.
  - `simulate_rejection = True`: logs rejected order and raises `InsufficientMarginError`.
  - `simulated_drift_seconds`: introduces clock drift between local system and Delta server time.
  - `simulate_timeout = True`: raises `TimeoutError` prior to order placement.
  - `simulate_timeout_post_placement = True`: simulates timeout on HTTP response after order lands on matching engine.

---

## 3. Four-Tier Test Suite Catalog (73 Tests)

### Tier 1: Unit & Contract Tests (38 Tests)
| Test Module | Coverage & Verification Scope | Test Count |
|---|---|:---:|
| `tests/unit/test_clock_drift.py` | Clock drift tolerance (<= 2.0s valid, > 2.0s invalid), boundary conditions, `SimulatedClock` protocol, and safety watchdog halt trigger. | 6 |
| `tests/unit/test_security_prohibitions.py` | AST scanner traversing all Python modules under `app/` asserting 0 withdrawal, transfer, or fund drain functions, methods, or endpoints. | 2 |
| `tests/unit/test_strategy_determinism.py` | Purity, determinism, input immutability, insufficient history handling, and zero look-ahead bias resistance for Strategy A & B and RegimeFilter. | 5 |
| `tests/unit/test_position_sizing.py` | Volatility scaling, strict floor integer contract rounding, leverage ceiling <= 3x, and safe invalid-input handling (0 contracts). | 5 |
| `tests/unit/test_risk_gate.py` | Mandatory ordered evaluation (Engine State -> Freshness -> Spread -> Protective Stop -> Sizing), early exit on first failure, and drawdown ladder. | 8 |
| `tests/unit/test_watchdog.py` | Unprotected position detection, kill switch trigger, engine halt, emergency flatten, zero-contract position safety, and loop lifecycle. | 4 |
| `tests/unit/test_guard.py` | Testnet allowlist enforcement, production denylist rejection, and URL hostname extraction. | 5 |
| `tests/unit/test_signing.py` | HMAC-SHA256 signature generation, timestamp in seconds, User-Agent header inclusion. | 2 |
| `tests/unit/test_config.py` | Configuration loading, environment overrides, fallback AppSettings. | 3 |
| `tests/unit/test_contracts.py` | Domain contracts, state transitions, spread bps calculations. | 2 |
| `tests/unit/test_rate_limiter.py` | Rate limit budget tracking (20k weight/5 min quota). | 1 |

### Tier 2: FakeExchange & Component Integration (14 Tests)
| Test Module | Coverage & Verification Scope | Test Count |
|---|---|:---:|
| `tests/integration/test_order_lifecycle.py` | Marketable limit IOC order execution, bracket attachment (SL/TP), fill tracking, and client order ID idempotency. | 4 |
| `tests/integration/test_data_pipeline.py` | `CandleStore` contiguity validation, forming candle updates, capacity limits, freshness tracking, and WebSocket reconnect backfill. | 5 |
| `tests/integration/test_reconciliation.py` | Continuous reconciliation loop, orphan position adoption, position closure synchronization after bracket execution, and network error resilience. | 4 |
| `tests/integration/test_fake_exchange.py` | Baseline execution manager interaction with FakeExchange. | 1 |

### Tier 3: Service-Level & Control-Plane Tests (9 Tests)
| Test Module | Coverage & Verification Scope | Test Count |
|---|---|:---:|
| `tests/unit/test_decision_journal.py` | SQLite WAL database schema creation, DecisionRecord insertion and roundtrip retrieval, engine event persistence, and deterministic plain-language narrative generation. | 4 |
| `tests/unit/test_control_plane.py` | Background task `Supervisor` lifecycle, restart loop with exponential backoff, max retry limits, engine state machine transitions, kill switch reset token validation (`CONFIRM_RESET`), and shared secret authorization via `app.api.deps.verify_control_secret`. | 5 |

### Tier 4: Chaos & Resiliency Scenarios (7 Tests in `tests/chaos/test_scenarios.py`)
All 7 required scenarios from Section 13.4 of `agent.md`:
1. **Scenario 1: Price Shock:** Sudden 10% flash crash wick against long position; bracket stop-loss executes, realized PnL correctly scaled by contract multiplier (`0.001 BTC`), bounding loss to realistic financial levels (`-13.0 USDT`).
2. **Scenario 2: Stale Market Data Feed:** Data age > 5.0s strictly rejected by Risk Gate with binding rule `DATA_FRESHNESS`.
3. **Scenario 3: WebSocket Stream Loss:** Stream ceases updating; `FreshnessTracker` detects feed stall and pauses new order execution.
4. **Scenario 4: Order Uncertainty:** Network timeout during `place_order`; `ExecutionManager` queries exchange truth by `client_order_id`, verifies pre-exchange drops and post-exchange execution adoption, ensuring zero double fills under retry.
5. **Scenario 5: Unprotected Position Watchdog:** Naked position detected on exchange; production `UnprotectedPositionWatchdog` class immediately halts engine and triggers emergency flatten.
6. **Scenario 6: Rate Limit Storm:** HTTP 429 `RateLimitExceededError` handled; `RateLimitAccountant` enters backoff cooldown, suppresses new calls and preserves system health.
7. **Scenario 7: Engine Restart with Open Position:** Cold start with open exchange position; reconciliation adopts position, verifies bracket protection, and aligns engine state cleanly.

---

## 4. How to Execute Tests

```bash
# Standard library test discovery (zero external dependencies)
python3 -m unittest discover tests

# Verbose execution
python3 -m unittest discover -v -s tests

# Running specific test tiers
python3 -m unittest tests/unit/test_clock_drift.py
python3 -m unittest tests/unit/test_security_prohibitions.py
python3 -m unittest tests/unit/test_strategy_determinism.py
python3 -m unittest tests/unit/test_position_sizing.py
python3 -m unittest tests/unit/test_risk_gate.py
python3 -m unittest tests/unit/test_watchdog.py
python3 -m unittest tests/integration/test_order_lifecycle.py
python3 -m unittest tests/integration/test_data_pipeline.py
python3 -m unittest tests/integration/test_reconciliation.py
python3 -m unittest tests/unit/test_decision_journal.py
python3 -m unittest tests/unit/test_control_plane.py
python3 -m unittest tests/chaos/test_scenarios.py

# When pytest is installed in the environment
pytest tests/
```

---

## 5. Escalated Implementation Defect (For M2 / M3 Implementing Agents)

- **Module:** `app/risk/sizing.py:63-65` (`PositionSizer.calculate_contracts`)
- **Observation:**
  ```python
  max_notional = float(current_equity) * float(self.max_leverage)
  max_contracts_by_leverage = max_notional / float(entry_price)
  ```
  At a BTC price of $65,000 and equity of $10,000, 3x leverage allows $30,000 notional.
  Because Delta Exchange contracts are valued at `contract_value_btc = Decimal("0.001")` (1 contract = 0.001 BTC = $65), 461 contracts should be permitted under 3x leverage.
  However, `sizing.py` divides directly by the single-coin price (`$65,000`) instead of the contract value (`$65.0`), computing `30000 / 65000 = 0.4615` contracts. Floor integer rounding truncates this to `0` contracts, falsely triggering `MIN_CONTRACT_SIZE` rejection on normal-sized accounts.
- **Recommended Fix (for Implementing Agent):**
  Factor in `self.contract_value_btc`:
  ```python
  contract_notional = float(entry_price) * float(self.contract_value_btc)
  max_contracts_by_leverage = max_notional / max(0.0001, contract_notional)
  ```
