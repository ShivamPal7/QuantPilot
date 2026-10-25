# QuantPilot: Glass-Box Desk
> **Delta Exchange Testnet Algorithmic Trading System**  
> *Algorithmic Trading Hackathon — Pure-logic architecture, multi-layered risk gates, and transparent decision auditability.*

---

## 1. Overview & Architecture

**QuantPilot** is an automated algorithmic trading desk built on the **Delta Exchange India Testnet** using Python and FastAPI. It operates as a **"Glass-Box Desk"**: every trade decision, regime classification, risk assessment, and non-trade stand-aside is accompanied by an immutable, deterministic plain-language narrative recorded in SQLite.

### Core Architectural Principles
1. **Pure Decision Logic, Impure Edges:** All strategies, regime filters, allocation mathematics, and risk policies are pure deterministic functions without wall-clock time, network calls, or random state. All exchange I/O and database operations exist strictly at the edge adapters.
2. **Exchange Truth as Canonical Source:** Internal cached positions and balances are continuously reconciled against exchange REST truth.
3. **Single Mandatory Risk Gate:** No trade intent can reach the exchange without passing sequential hard rejection checks, volatility-scaled sizing, and server-side bracket exit attachments.
4. **Deterministic Auditability:** Every closed candle produces a decision journal record (including "no trade") with clear human-readable explanations.

```
                    ┌────────────────────────┐
                    │ Delta Exchange Testnet │
                    │   (REST & WebSockets)  │
                    └───────────┬────────────┘
                                │
             ┌──────────────────┴──────────────────┐
             │ Edge Adapters & Guards (Green/Amber)│
             │ - Testnet Safety Guard              │
             │ - HMAC-SHA256 Signing Helper        │
             │ - Rate Limit Accountant             │
             │ - Candle Store & Freshness Tracker  │
             └──────────────────┬──────────────────┘
                                │ [Candle Closed Event]
             ┌──────────────────┴──────────────────┐
             │ Pure Decision Core (Red Zone)       │
             │ 1. Regime Filter (Trend/Range/Chop) │
             │ 2. Strategy A & B Evaluation        │
             │ 3. Shadow Virtual Accounts          │
             │ 4. Multi-Armed Bandit Allocator     │
             │ 5. Risk Gate & Volatility Sizer     │
             └──────────────────┬──────────────────┘
                                │ [Approved Intent + Brackets]
             ┌──────────────────┴──────────────────┐
             │ Execution Manager & Audit (Amber)   │
             │ - Marketable Limit with IOC         │
             │ - Idempotent Client Order IDs       │
             │ - Decision Journal (SQLite)         │
             │ - Static Live Dashboard             │
             └─────────────────────────────────────┘
```

---

## 2. Strategies & Regime Allocation

### Strategy A: Volatility-Scaled Trend Following (`app/signals/trend.py`)
- **Theoretical Basis:** Empirical evidence demonstrates persistent momentum in major cryptocurrencies at multi-hour to multi-day horizons (Moskowitz et al., 2012; Liu & Tsyvinski). Sizing inversely to Average True Range (ATR) stabilizes portfolio variance.
- **Signal Logic:** Moving average crossover and range breakouts, confirmed by directional trend strength.
- **Stand-Aside:** Automatically stands aside when the Regime Filter detects ranging or chaotic conditions.

### Strategy B: Short-Horizon Mean Reversion (`app/signals/reversion.py`)
- **Theoretical Basis:** Bitcoin exhibits short-term negative autocorrelation at 1- to 4-hour horizons following extreme deviation spikes, driven by liquidation cascades and order book overreaction (Chan, 2013).
- **Signal Logic:** Fades statistical extremes ($z$-score $> 2.0$) only when stationarity checks confirm mean-reverting dynamics.

### Regime Filter (`app/signals/regime.py`)
- Classifies conditions into **`TRENDING`**, **`RANGING`**, and **`CHAOTIC`**.
- Incorporates **hysteresis** and dwell-time thresholds to prevent state flickering. When chaotic chop is detected, a strict stand-aside is enforced.

### Strategy Allocator (`app/shadow/allocator.py`)
- Continuously runs paper-traded virtual accounts with modeled fees and slippage.
- Allocates capital using a Bayesian multi-armed bandit (Thompson sampling) weighted by recent shadow win rates, with a guaranteed exploration floor and regime overrides.

---

## 3. Risk Management & Safeguards

The **Risk Gate** (`app/risk/gate.py`) evaluates every intent through a strict sequence:
1. **Engine Operational State:** Must be in `RUNNING` (rejects all entries if `PAUSED` or `HALTED`).
2. **Testnet Safety Guard:** Refuses startup if connected to production hostnames.
3. **Clock Drift Guard:** Rejects trades if local clock drifts $> 2.0$ seconds from server time.
4. **Data Freshness Guard:** Rejects trades if market data staleness exceeds $5.0$ seconds.
5. **Spread Guard:** Rejects trades if bid-ask spread exceeds $15$ bps.
6. **Protective Stop Requirement:** Every trade MUST include a server-side bracket order (take-profit and stop-loss) on Delta Exchange.
7. **Volatility-Scaled Sizing:** Sizing scales inversely to volatility, capped by fractional Kelly and a low leverage limit (default 2x–3x), rounded strictly **down** to integer contracts.
8. **Emergency Kill Switch:** Reachable by API, dashboard button, or automatic watchdog. Cancels all working orders, closes open positions via reduce-only orders, and halts the system until explicit human reset.

---

## 4. Repository Architecture

```
quantpilot/
├── app/
│   ├── api/          # FastAPI routers, auth dependency, schemas
│   ├── core/         # Typed contracts, state machine, config, logging, clock
│   ├── exchange/     # Testnet guard, signing helper, REST/WS client, rate limiter
│   ├── data/         # Candle store, freshness tracker, stream builder
│   ├── signals/      # Strategies (Trend, Reversion) and Regime Filter [Red Zone]
│   ├── shadow/       # Shadow accounts, cost model, bandit allocator
│   ├── risk/         # Mandatory risk gate, sizing, guards, kill switch [Red Zone]
│   ├── execution/    # Order manager, idempotency, fill quality, reconciler
│   ├── journal/      # SQLite persistence, narrative generator [Red Zone]
│   └── dashboard/    # Lightweight static monitoring dashboard
├── config/
│   ├── default.json  # Standard theory-derived parameters (1h timeframe)
│   └── demo.json     # Fast demo profile (1m timeframe for live demo)
├── docs/             # ADRs, AI usage logs, Q&A prep, trials, risk policy, limitations
├── scripts/          # Diagnostics, smoke tests, candle warm-up verification
├── tests/
│   ├── fakes/        # In-memory fake exchange
│   ├── unit/         # Unit tests for guard, signing, rate limiter, contracts
│   ├── integration/  # Integration tests with FakeExchange
│   └── chaos/        # Chaos resilience tests (stale feed, kill switch)
├── agent.md          # AI agent charter and design guidelines
├── pyproject.toml    # Pinned dependency specifications
├── requirements.txt  # Pinned pip requirements
└── .env.example      # Placeholder environment variables template
```

---

## 5. Setup & Execution Instructions

### Prerequisites
- Python 3.10+
- Delta Exchange India Demo Account credentials ([Delta Testnet](https://cdn-ind.testnet.deltaex.org))

### Step 1: Environment Setup
```bash
# Clone the repository and enter directory
cd quantpilot

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install pinned dependencies
pip install -r requirements.txt
```

### Step 2: Configure Secrets
```bash
cp .env.example .env
```
Edit `.env` and fill in your credentials:
```env
TARGET_ENV=testnet
DELTA_API_KEY=your_delta_testnet_api_key_here
DELTA_API_SECRET=your_delta_testnet_api_secret_here
CONTROL_PLANE_SECRET=change_me_to_a_secure_token
```
> **Important:** Your machine's public IP must be whitelisted on the key in the Delta testnet portal!

### Step 3: Run Phase 0 Diagnostics & Tests
```bash
# Verify environment safety guard, clock, and config
python scripts/diagnostics.py

# Run comprehensive test suite (131 tests, 100% pass rate in <1s)
# Via standard library unittest:
python -m unittest discover -s tests

# Or via pytest:
pytest tests/
```

The test suite covers:
- **Unit tests:** Pure strategy determinism, regime filter hysteresis, bandit allocator, integer position sizing, and risk gate rules.
- **Integration tests:** REST/WebSocket streaming, order lifecycle, bracket attachments, and startup/periodic reconciliation.
- **Chaos scenarios:** All 7 required failure modes verified (price shocks, stale feed, websocket loss, order response timeouts, unprotected position watchdog, HTTP 429 rate limit storm, and restart reconciliation).

### Step 4: Run the Application & Control Plane
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser to:
- **Dashboard:** [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 6. Parameters & Overfitting Discipline

Per Section 10.5 of `agent.md`, all parameter configurations ever evaluated are logged in `docs/trials.md` to prevent backtest overfitting.
- **Current Total Configurations Evaluated:** 0 (initial setup).
- **Demo Freeze:** Parameters are locked prior to demo presentation.
- **Demo Profile Disclosure:** For the 10-minute live hackathon demo, the system uses `config/demo.json` (1-minute candles) so execution can be observed on screen. This is strictly a demonstration profile and not the researched multi-hour model.

---

## 7. AI Authorship & Governance

In strict compliance with the hackathon rule (20–30% maximum AI code ceiling):
- **AI Scaffolder (Green Zone):** Initial boilerplate, directory architecture, `.env.example`, typing contracts, test harnesses, and documentation drafts (~15% of codebase).
- **Human Authorship (Red Zone):** Core strategy mathematics, regime classification rules, allocator Thompson sampling, risk policies, and execution state machine are 100% human-owned and authored.
- **Full Ledger:** Tracked in [`docs/ai-usage-log.md`](docs/ai-usage-log.md).

---

## 8. Limitations & Failure Modes

- **Thin Testnet Books:** Testnet liquidity is significantly thinner than production. Large orders may incur unrealistic simulated slippage.
- **Single Instrument v1:** Operates strictly on `BTCUSD` perpetual futures. Cross-pair arbitrage is out of scope.
- **Rate Limit Budget:** Delta enforces 20,000 weight per 5-minute fixed window; our adapter throttles REST to stay under 25% of quota.
- Full details documented in [`docs/limitations.md`](docs/limitations.md).
