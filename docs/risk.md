# Risk Management Policy & Parameters

Per `agent.md` Section 9.5, this document defines the risk rules, thresholds, execution order, and mathematical rationale.

---

## 1. Single Mandatory Risk Gate Architecture
No order reaches the exchange without traversing the single, centralized Risk Gate (`app.risk.gate`). The gate enforces a two-stage evaluation:
1. **Hard Rejection Checks:** Binary pass/fail conditions. If any condition fails, the intent is immediately rejected with explicit numeric reasons.
2. **Sizing & Volatility Scaling:** If hard checks pass, calculate safe contract quantity scaled inversely to volatility, capped by fractional Kelly and leverage limits, rounded down to integer contracts.

---

## 2. Hard Rejection Rules (Order of Evaluation)
1. **Engine Operational State:** Engine must be in `RUNNING`. (`PAUSED` or `HALTED` rejects all new entries).
2. **Environment & Security Guard:** Hostname must match allowed testnet endpoints; no production hostnames.
3. **Clock Drift Guard:** Local system clock must not drift by more than 2 seconds from Delta exchange server time.
4. **Data Freshness Guard:** Latest market snapshot must be fresher than `max_staleness_seconds` (default: 5.0s), with no un-backfilled candle gaps.
5. **Product Operational Status:** Target instrument trading status must be operational (`trading_status == 'operational'`).
6. **Market Quality Guard:**
   - Bid-ask spread must be <= `max_spread_bps` (e.g. 15 bps).
   - Top-of-book depth must accommodate intent size without excessive expected market impact.
7. **Loss & Drawdown Limits:**
   - Daily loss limit: system halts new entries if cumulative realized losses exceed `max_daily_loss_pct` (default: 3.0%).
   - Drawdown ladder: reduce sizing at defined drawdown rungs; halt at max drawdown.
   - Consecutive loss cooldown: pause new entries after `max_consecutive_losses` (default: 3) consecutive losing trades.
8. **Exposure & Position Limits:**
   - Maximum concurrent open positions (default: 1 in v1).
   - Maximum notional position exposure limit.
9. **Protection Guarantee:**
   - Intent must specify a valid protective stop distance.
   - Stop distance must exceed the minimum survival distance (to avoid noise execution) while staying within per-trade risk budget.

---

## 3. Position Sizing Policy
- **Fixed Fraction Risk Budget:** Each trade risks $R = \text{Equity} \times f_{risk}$ (default: 0.5% – 1.0% of equity).
- **Stop-Loss Distance ($D_{stop}$):** Proposed in price units from ATR or strategy logic.
- **Base Sizing:** $\text{Quantity} = \frac{R}{D_{stop} \times \text{ContractValue}}$.
- **Volatility Scaling:** Sizing scales inversely to short-term realized volatility ($\sigma_{realized} / \sigma_{target}$).
- **Ceilings Applied:**
  - Fractional Kelly ceiling (maximum 0.25x – 0.5x Kelly), used strictly as an upper bound.
  - Hard leverage ceiling (default: 2x – 3x leverage, explicitly set on the exchange; never default exchange leverage).
- **Rounding:** Strictly rounded **down** to integer contracts. If size < 1 contract, the intent is rejected.

---

## 4. Kill Switch & Auto-Watchdogs
- **Watchdog Triggers:**
  - Unprotected position detected for > 10 seconds.
  - WebSocket connection dead for > 15 seconds.
  - Daily loss or drawdown threshold breach.
  - Reconciliation mismatch between internal view and exchange truth that cannot be auto-resolved.
- **Actions:**
  1. Transition engine state to `HALTED`.
  2. Cancel all working/pending orders on exchange.
  3. Close all open positions with `reduce_only` market orders.
  4. Verify account is flat via exchange REST reconciliation.
  5. Require human reset via authenticated control-plane API with explicit confirmation.
