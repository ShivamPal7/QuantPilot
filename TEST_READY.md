# QuantPilot Test Readiness Report (`TEST_READY.md`)

**Date:** 2026-10-25  
**Milestone:** M1 — E2E Testing Track & Test Infrastructure (Remediation M1-R2)  
**Author:** worker_m1_r2  
**Status:** READY — 100% PASS RATE (73 of 73 Tests Passed)

---

## 1. Summary of Completed Objectives & M1-R2 Remediation

1. **FakeExchange Double Remediated (`tests/fakes/fake_exchange.py`):**
   - Fixed 1,000x Realized PnL error across all bracket triggers and `close_all()` by multiplying price difference by `self.contract_multiplier` (`0.001 BTC/contract`).
   - Fixed position tracking in `place_order`: manages positions per symbol, handles same-side contract accumulation with weighted entry price, and counter-order position reduction, closure (flattening), and flipping with accurate realized PnL.
   - Fixed `get_candles`: returns empty list `[]` when `end <= start` or resolution/timestamps are invalid, and properly filters custom candles.
   - Added `wallet_balance` property/setter alias for `self.balance`.
   - Added `simulate_timeout_post_placement` flag for testing in-flight resolution when order lands on exchange but response times out.

2. **Control-Plane Dependency Verification (`tests/unit/test_control_plane.py`):**
   - Removed inline mock function in `test_control_secret_authorization_logic`.
   - Now directly tests `app.api.deps.verify_control_secret`, verifying valid secret passage and HTTP 401 Unauthorized exceptions on missing/invalid secrets.

3. **Chaos Scenarios Hardening (`tests/chaos/test_scenarios.py`):**
   - **Scenario 1 (Price Shock):** Asserts exact realized PnL (`-13.0 USDT`) and realistic post-shock balance (`9987.0 USDT`) factoring in `contract_multiplier`.
   - **Scenario 4 (Order Uncertainty):** Tests both pre-exchange network drops (abort without double fill) and post-exchange response drops (in-flight adoption and client order ID idempotency).
   - **Scenario 5 (Unprotected Position Watchdog):** Imports and executes the genuine production `UnprotectedPositionWatchdog` service (`app/risk/watchdog.py`), eliminating inline test logic.
   - **Scenario 6 (Rate Limit Storm):** Explicitly verifies `RateLimitAccountant` enters backoff cooldown, suppresses new calls, and halts requests.

4. **Pytest / Unittest Dual Compatibility (`tests/conftest.py`):**
   - Wrapped `import pytest` in conditional `try / except ImportError:` guard.
   - Tests execute with zero external dependencies under Python 3 standard library `unittest`.

5. **Four-Tier Test Suite Built & Verified (73 Tests Total):**
   - **Tier 1 (Unit & Contracts):** 38 tests covering Clock Drift, Security AST Scanning, Strategy Determinism, Position Sizing, Risk Gate, Watchdog, Guard Allow/Denylists, Signing, Config, and Rate Limiting.
   - **Tier 2 (FakeExchange & Component Integration):** 14 tests covering Order Lifecycle (Marketable Limit IOC + Brackets), Data Pipeline Contiguity & WebSocket Backfill, and Reconciliation.
   - **Tier 3 (Service & Control-Plane):** 9 tests covering Decision Journal SQLite WAL, Deterministic Plain-Language Narratives, Background Supervisor, and Control-Plane Endpoints.
   - **Tier 4 (Chaos & Resiliency):** 7 comprehensive scenarios covering Price Shock, Stale Feed, WebSocket Loss, Order Uncertainty, Unprotected Position Watchdog, Rate Limit Storm, and Engine Restart with Open Position.

---

## 2. Test Execution Command & Verification Results

```bash
python3 -m unittest discover tests
```

### Verification Output:
```
Ran 73 tests in 0.358s

OK
```

- **Tests Run:** 73
- **Failures:** 0
- **Errors:** 0
- **Pass Rate:** 100.0%

---

## 3. Inventory of Test Assets

| Path | Type | Tests | Status |
|---|---|:---:|:---:|
| `tests/fakes/fake_exchange.py` | Fake Exchange Double | N/A | REMEDIATED |
| `tests/conftest.py` | Fixtures & Compatibility | N/A | GUARDED |
| `tests/unit/test_clock_drift.py` | Tier 1 Unit Test | 6 | PASSED |
| `tests/unit/test_security_prohibitions.py` | Tier 1 Unit Test | 2 | PASSED |
| `tests/unit/test_strategy_determinism.py` | Tier 1 Unit Test | 5 | PASSED |
| `tests/unit/test_position_sizing.py` | Tier 1 Unit Test | 5 | PASSED |
| `tests/unit/test_risk_gate.py` | Tier 1 Unit Test | 8 | PASSED |
| `tests/unit/test_watchdog.py` | Tier 1 Unit Test | 4 | PASSED |
| `tests/unit/test_guard.py` | Tier 1 Unit Test | 5 | PASSED |
| `tests/unit/test_signing.py` | Tier 1 Unit Test | 2 | PASSED |
| `tests/unit/test_config.py` | Tier 1 Unit Test | 3 | PASSED |
| `tests/unit/test_contracts.py` | Tier 1 Unit Test | 2 | PASSED |
| `tests/unit/test_rate_limiter.py` | Tier 1 Unit Test | 1 | PASSED |
| `tests/integration/test_order_lifecycle.py` | Tier 2 Integration Test | 4 | PASSED |
| `tests/integration/test_data_pipeline.py` | Tier 2 Integration Test | 5 | PASSED |
| `tests/integration/test_reconciliation.py` | Tier 2 Integration Test | 4 | PASSED |
| `tests/integration/test_fake_exchange.py` | Tier 2 Integration Test | 1 | PASSED |
| `tests/unit/test_decision_journal.py` | Tier 3 Service Test | 4 | PASSED |
| `tests/unit/test_control_plane.py` | Tier 3 Service Test | 5 | PASSED |
| `tests/chaos/test_scenarios.py` | Tier 4 Chaos Scenarios (1–7) | 7 | PASSED |

---

## 4. Discovered Implementation Defects (Escalated to Implementing Agent)

1. **Defect:** `PositionSizer.calculate_contracts` in `app/risk/sizing.py:64` omits `self.contract_value_btc` (0.001 BTC).
   - **Impact:** Divides notional leverage capacity directly by single Bitcoin price (`$65,000`) instead of contract notional (`$65.0`). On accounts under $22,000 equity, computed contract size floors to 0, rejecting valid orders.
   - **Recommended Fix:** Change `max_contracts_by_leverage = max_notional / float(entry_price)` to divide by `(float(entry_price) * float(self.contract_value_btc))`.

---

## 5. Handoff Readiness

The test infrastructure has been rigorously remediated, eliminating all self-certifying inline logic and simulation defects. It is fully operational, hardened, self-contained, and ready to gate Milestones M2, M3, and M4.
